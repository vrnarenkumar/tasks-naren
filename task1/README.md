# Task 1 — Local LLM Chatbot

## Objective

Develop a chatbot system powered by large language model (LLM) inference on
your local machine, taking advantage of GPU acceleration to optimize
performance, and including machine details in the submission documentation.

## What's actually done

- FastAPI backend (`main.py`) with:

  - `GET /health` — returns status and the active model name.
  - `WS /ws/chat` — websocket endpoint. Keeps per-connection message history
    and streams the model's reply back token by token as it's generated.

- Backend talks to a local Ollama server (`http://localhost:11434`) over its
  REST API, not a Python SDK.

- Config pulled out into `config.py`, values loaded from `.env`
  (`.env` itself is gitignored, not committed).

- Tested manually: `/health` via curl, `/ws/chat` via a small script,
  both against the actual model. No automated tests yet.


## Why FastAPI with websocket

FastAPI was picked because it's easy to plug into any UI or interface.

## Why Ollama + llama3.2:3b

Ollama wraps llama.cpp and automatically accelerates GPU with no manual 
setup 
The alternative considered was vLLM, but vLLM targets CUDA GPUs and 
hardware support is limited

`llama3.2:3b` was chosen over larger models because this machine has only
8GB of RAM total. Can be used for deployment too.

## What can be upgraded

- vLLM, if this were deployed to a machine with an NVIDIA GPU instead of
  running locally — it's built for that and would give better throughput 
  under concurrent load.
- A real frontend, connected to the existing `/ws/chat` for streaming
  responses.

## Running the backend

```bash
cd tasks-naren
source .venv/bin/activate
pip install -r task1/requirements.txt
cd task1
uvicorn main:app --port 8000
```
