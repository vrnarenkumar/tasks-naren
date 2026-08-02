import json
import os
import sys
from pathlib import Path

# config.py, graph.py, prompts.py live in the top-level backend/ folder, and
# parts_catalog.py lives in the sibling tasks/task3/ folder — neither is
# a package, so both need to be added to sys.path before importing
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "backend"))
sys.path.append(str(PROJECT_ROOT / "tasks" / "task3"))

import phoenix as px
from config import OLLAMA_MODEL
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from graph import build_graph, classify_message, to_lc_messages
from langchain_core.messages import HumanMessage
from parts_catalog import PartsCatalog
from phoenix.otel import register

DATA_PATH = Path(__file__).resolve().parents[2] / "docs" / "Parts.csv"

# local trace UI at http://localhost:6006 — shows which graph node ran and
# what each LLM call saw/returned, for every request. Best-effort: tracing
# must never prevent the chatbot itself from starting. Set ENABLE_TRACING=false
# to skip entirely (e.g. in the Cloud Run deployment, where 6006 isn't reachable).
if os.environ.get("ENABLE_TRACING", "true").lower() == "true":
    try:
        px.launch_app()
        register(project_name="parts-catalogue-chatbot", auto_instrument=True)
    except Exception as error:  # noqa: BLE001 - tracing must never block startup
        print(f"Phoenix tracing unavailable, continuing without it: {error}")

app = FastAPI()

# for a browser-based frontend running on a different port during local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_CATALOG = PartsCatalog.from_csv(DATA_PATH)

STREAMABLE_NODES = {"catalog"}


@app.get("/health")
async def health():
    return {"status": "ok", "model": OLLAMA_MODEL, "parts_loaded": len(BASE_CATALOG.df)}


async def handle_chat_message(
    websocket: WebSocket, graph, catalog: PartsCatalog, history: list[dict], user_message: str
) -> None:
    """Run one turn through the graph, streaming the reply back token by token.

    Retrieval/tool context lives only inside this graph run; `history` only
    ever gets the plain user/assistant turns, so nothing from one turn leaks
    into an unrelated later question.
    """
    # classify_message is cheap and deterministic (no LLM), so reporting the
    # node type here — before the graph runs it again to actually branch —
    # costs nothing but lets the client show it immediately, before the
    # (possibly slow) LLM call even starts
    node_label, _ = classify_message(user_message, catalog)
    await websocket.send_text(f"[NODE:{node_label}]")

    input_messages = to_lc_messages(history) + [HumanMessage(content=user_message)]
    history.append({"role": "user", "content": user_message})

    reply = ""
    async for event in graph.astream_events({"messages": input_messages}, version="v2"):
        if event["event"] == "on_chat_model_stream":
            if event["metadata"].get("langgraph_node") not in STREAMABLE_NODES:
                continue
            token = event["data"]["chunk"].content
            if token:
                reply += token
                await websocket.send_text(token)
        elif event["event"] == "on_chain_end" and event.get("name") == "LangGraph":            
            if not reply:
                final_message = event["data"]["output"]["messages"][-1]
                reply = final_message.content
                await websocket.send_text(reply)

    history.append({"role": "assistant", "content": reply})
    await websocket.send_text("[DONE]")


@app.websocket("/ws/chat")
async def chat(websocket: WebSocket):
    await websocket.accept()
    history: list[dict] = []
    graph = build_graph(BASE_CATALOG)

    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                payload = json.loads(raw_message)
            except json.JSONDecodeError:
                payload = {"type": "message", "text": raw_message}

            await handle_chat_message(
                websocket, graph, BASE_CATALOG, history, payload.get("text", "")
            )

    except WebSocketDisconnect:
        pass
