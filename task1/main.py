import json

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import OLLAMA_MODEL, OLLAMA_URL

app = FastAPI()

# for a browser-based frontend running on a different port during local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "model": OLLAMA_MODEL}


@app.websocket("/ws/chat")
async def chat(websocket: WebSocket):
    await websocket.accept()
    history = []

    try:
        while True:
            user_message = await websocket.receive_text()
            history.append({"role": "user", "content": user_message})

            reply = ""
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{OLLAMA_URL}/api/chat",
                    json={"model": OLLAMA_MODEL, "messages": history, "stream": True},
                ) as response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            reply += token
                            await websocket.send_text(token)
                        if chunk.get("done"):
                            break

            history.append({"role": "assistant", "content": reply})
            await websocket.send_text("[DONE]")

    except WebSocketDisconnect:
        pass
