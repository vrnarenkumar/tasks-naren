
## 1. Components

| Component | File(s) | Responsibility |
|---|---|---|
| Frontend | `frontend/src/App.tsx` | React chat UI, WebSocket client, CSV upload button |
| API/transport | `backend/task1/main.py` | FastAPI app, WebSocket handler, session lifecycle |
| Orchestration | `backend/graph.py` | LangGraph pipeline: routing, confidence checks, LLM calls |
| Prompts | `backend/prompts.py` | All system prompts and fixed response strings, isolated from logic |
| Config | `backend/config.py` | `OLLAMA_URL` / `OLLAMA_MODEL` from `.env` |
| Retrieval engine | `backend/task3/parts_catalog.py` | `PartsCatalog` — TF-IDF similarity search over the catalogue |
| Observability | Arize Phoenix, wired in `main.py` | Auto-traces every LangGraph node and LLM call |
| Tests | `tests/` | pytest, covers the deterministic core (no LLM required to run) |

## 2. Orchestration

- LangGraph state stores the running message history.
- Three nodes, one per answer type: `catalog`, `general`, `unsupported`.
- A `classify` step picks which of the three runs for a given message.


## 3. Prompts

**`Few shot Prompting techniques`** — each system prompt embeds 2-3 worked examples (input + ideal output) covering the confident, low-confidence/unverified, and not-found cases, using synthetic `SAMPLE-1xx` IDs so the model can't mistake the examples for real catalog data.

**`GENERAL_SYSTEM_PROMPT`** — used by the `general` node.
- No catalog lookup available for this reply.
- If asked about a specific part ID, stock, price, or exact specs, say there's no data rather than guessing — even if phrased casually.
- 2 few-shot examples (plain general-knowledge answer / refusing a stock question), again using a `SAMPLE-1xx` placeholder ID.

**`UNSUPPORTED_MESSAGE`** — static string returned by the `unsupported` node, no LLM call. States the assistant can help with catalog alternatives (by ID or description) or general knowledge, but has no stock/pricing/availability data.

## 4. GuardRails

- Keyword check (`stock`, `price`, `pricing`, `cost`, `availability`, `available`, `lead time`) → fixed refusal message, no LLM call.
- Confidence threshold `0.1` on cosine similarity score → below it, `catalog_exact_id` degrades to `low_confidence` and `catalog_search` degrades to `general`.
- Rated Current exact-match filter applied before ranking alternatives by similarity.
- Missing Rated Current on the query part → skip that filter, attach an "unverified" warning instead.
- Case-insensitive, exact-match ID lookup only — no fuzzy/approximate ID matching.
- `temperature=0` on the LLM.
- Catalog prompt restricted to the given context only — no invented IDs/descriptions/ratings/stock/price.
- General prompt refuses stock/price/exact specs even when phrased casually.
- Few-shot examples use synthetic placeholder IDs (`SAMPLE-1xx`), not realistic-looking ones, to prevent leakage into real answers.
- Post-generation check: IDs in the model's reply are diffed against IDs in its own context; mismatches are logged, not silently accepted.