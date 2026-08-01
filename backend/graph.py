import logging
import re
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from config import OLLAMA_MODEL, OLLAMA_URL
from prompts import CATALOG_SYSTEM_PROMPT, GENERAL_SYSTEM_PROMPT, UNSUPPORTED_MESSAGE

# Business questions the catalog has no data for at all (stock/pricing/availability) -
# a guardrail so the model is never even asked to answer these, let alone tempted to guess.
UNSUPPORTED_KEYWORDS = re.compile(
    r"\b(stock|price|pricing|cost|availability|available|lead\s*time)\b", re.IGNORECASE
)

# Letters followed by digits (optionally trailing alnum), e.g. "A1", "ABC999" - shaped
# like this catalog's part IDs, as opposed to ordinary words.
ID_SHAPE = re.compile(r"^[A-Za-z]+[0-9]+[A-Za-z0-9]*$")

# Below this, a "match" shares essentially no vocabulary and shouldn't be presented
# as a confident result.
CONFIDENCE_THRESHOLD = 0.1

CATALOGISH_LABELS = {"catalog_exact_id", "low_confidence", "catalog_search", "not_found"}

logger = logging.getLogger(__name__)


def looks_like_id(token: str) -> bool:
    return bool(ID_SHAPE.match(token))


def is_unsupported(message: str) -> bool:
    return bool(UNSUPPORTED_KEYWORDS.search(message))


def extract_known_id(message: str, catalog) -> str | None:
    known_ids = catalog.known_ids()
    lookup = {known_id.upper(): known_id for known_id in known_ids}
    for token in re.findall(r"\w+", message):
        if looks_like_id(token) and token.upper() in lookup:
            return lookup[token.upper()]
    return None


def _has_id_shaped_token(message: str) -> bool:
    return any(looks_like_id(token) for token in re.findall(r"\w+", message))


def classify_message(message: str, catalog):
    if is_unsupported(message):
        return "unsupported", None

    known_id = extract_known_id(message, catalog)
    if known_id is not None:
        result = catalog.find_alternatives(known_id)
        top_score = result["alternatives"][0]["score"] if result["alternatives"] else 0.0
        label = "catalog_exact_id" if top_score >= CONFIDENCE_THRESHOLD else "low_confidence"
        return label, result

    if _has_id_shaped_token(message):
        return "not_found", None

    result = catalog.search_by_text(message)
    top_score = result["matches"][0]["score"] if result["matches"] else 0.0
    if top_score >= CONFIDENCE_THRESHOLD:
        return "catalog_search", result
    return "general", None


def to_lc_messages(history: list[dict]):
    messages = []
    for turn in history:
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        else:
            messages.append(AIMessage(content=turn["content"]))
    return messages


def _format_entries(entries: list[dict]) -> str:
    if not entries:
        return "  (none)"
    return "\n".join(
        f"  - {entry['id']} (score {entry['score']:.2f}): {entry['description']}"
        for entry in entries
    )


def _format_context(label: str, result: dict | None) -> str:
    """Plain, readable text instead of a Python dict repr - a small model is prone to
    echoing a dict-shaped context back verbatim rather than answering from it."""
    if result is None:
        return "No catalog lookup applies to this message."

    if "alternatives" in result:
        lines = [f"Looked up part: {result['query_id']}", "Alternatives found:"]
        lines.append(_format_entries(result["alternatives"]))
        for warning in result["warnings"]:
            lines.append(f"Warning: {warning}")
        return "\n".join(lines)

    lines = [f"Text search for: {result['query']!r}", "Matches found:"]
    lines.append(_format_entries(result["matches"]))
    return "\n".join(lines)


def _extract_ids(text: str) -> set[str]:
    return {token.upper() for token in re.findall(r"\w+", text) if looks_like_id(token)}


def _unverified_ids(reply: str, context: str) -> list[str]:
    """IDs the model mentioned that never appeared in the context it was given -
    a red flag for hallucination (e.g. leaking an ID from a few-shot example)."""
    return sorted(_extract_ids(reply) - _extract_ids(context))


class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    label: str
    context: str


def build_graph(catalog):
    # temperature=0: same question -> same answer, not a different roll each time -
    # important for a grounded catalog assistant where creativity is a liability
    llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_URL, streaming=True, temperature=0)

    def classify(state: GraphState) -> dict:
        last_human = next(
            msg for msg in reversed(state["messages"]) if isinstance(msg, HumanMessage)
        )
        label, result = classify_message(last_human.content, catalog)
        return {"label": label, "context": _format_context(label, result)}

    def catalog_node(state: GraphState) -> dict:
        # plain substitution, not str.format(): the few-shot examples contain literal
        # JSON braces that str.format() would misparse as format fields
        prompt = SystemMessage(
            content=CATALOG_SYSTEM_PROMPT.replace("{context}", state["context"])
        )
        reply = llm.invoke([prompt, *state["messages"]])
        unverified = _unverified_ids(reply.content, state["context"])
        if unverified:
            # logged only, never blocks the reply already streamed to the user - this
            # is a visibility guardrail (catch prompt/model drift) rather than a filter
            logger.warning(
                "catalog node mentioned IDs absent from its own context (likely "
                "hallucinated): %s",
                unverified,
            )
        return {"messages": [reply]}

    def general_node(state: GraphState) -> dict:
        prompt = SystemMessage(content=GENERAL_SYSTEM_PROMPT)
        reply = llm.invoke([prompt, *state["messages"]])
        return {"messages": [reply]}

    def unsupported_node(state: GraphState) -> dict:
        return {"messages": [AIMessage(content=UNSUPPORTED_MESSAGE)]}

    def route(state: GraphState) -> str:
        if state["label"] == "unsupported":
            return "unsupported"
        if state["label"] in CATALOGISH_LABELS:
            return "catalog"
        return "general"

    graph = StateGraph(GraphState)
    graph.add_node("classify", classify)
    graph.add_node("catalog", catalog_node)
    graph.add_node("general", general_node)
    graph.add_node("unsupported", unsupported_node)

    graph.set_entry_point("classify")
    graph.add_conditional_edges(
        "classify", route, {"catalog": "catalog", "general": "general", "unsupported": "unsupported"}
    )
    graph.add_edge("catalog", END)
    graph.add_edge("general", END)
    graph.add_edge("unsupported", END)

    return graph.compile()
