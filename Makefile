VENV := $(CURDIR)/.venv
PYTHON := $(shell command -v python3.12 || command -v python3)
BACKEND := $(CURDIR)/backend
TASK1 := $(CURDIR)/tasks/task1
MODEL := $(shell grep -E '^OLLAMA_MODEL=' $(TASK1)/.env 2>/dev/null | cut -d= -f2)
MODEL := $(if $(MODEL),$(MODEL),llama3.2:3b)

.PHONY: frontend backend venv ollama-check ollama-model kill-port

.PHONY: kill-port
# usage: $(MAKE) kill-port PORT=8000
kill-port:
	@pids=$$(lsof -ti :$(PORT)); \
	if [ -n "$$pids" ]; then echo "Killing process(es) on port $(PORT): $$pids"; kill $$pids; fi

frontend:
	@$(MAKE) kill-port PORT=5173
	cd frontend && npm i && npm run dev

venv:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(VENV)/bin/pip install -q -r $(BACKEND)/requirements.txt

ollama-check:
	@command -v ollama >/dev/null 2>&1 || { echo "Ollama not found, installing via Homebrew..."; brew install ollama; }
	@pgrep -x ollama >/dev/null 2>&1 || { echo "Starting Ollama..."; nohup ollama serve >/tmp/ollama.log 2>&1 & sleep 2; }

ollama-model:
	@ollama list | grep -q "$(MODEL)" || { echo "Pulling $(MODEL)..."; ollama pull $(MODEL); }

backend: venv ollama-check ollama-model
	@$(MAKE) kill-port PORT=8000
	cd $(TASK1) && $(VENV)/bin/uvicorn main:app --port 8000
