FROM ollama/ollama:latest

ENV PYTHONUNBUFFERED=1 \
    OLLAMA_MODEL=llama3.2:3b \
    ENABLE_TRACING=false

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r backend/requirements.txt
ENV PATH="/opt/venv/bin:$PATH"

COPY backend backend
COPY tasks tasks
COPY docs docs
COPY start.sh start.sh
RUN chmod +x start.sh

# Bake the model into the image at build time so a cold start doesn't have
# to pull it (~2GB) before it can serve a single request.
RUN ollama serve & \
    sleep 5 && \
    ollama pull ${OLLAMA_MODEL} && \
    pkill ollama

EXPOSE 8080
ENTRYPOINT []
CMD ["./start.sh"]
