# tasks-naren

BMW's assignment. `task1` is a FastAPI + websocket chatbot
running a local LLM via Ollama, `frontend` is the React UI for it.

# Structure
I have the maintained a structure of deploying this code seamlessly. 
 **tasks** folder consists of the tasks that are assigned
 **backend** is for the backend integrated with the Websocket

## Running it

```bash
Please visit this page to install Ollama https://ollama.com/download

make backend    # sets up and runs the API on :8000
make frontend   # installs deps and runs the UI on :5173
```

Run both, in separate terminals, then open http://localhost:5173.

See `backend/task1/README.md` for the details and reasoning behind that
task specifically.
