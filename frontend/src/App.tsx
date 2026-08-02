import { useEffect, useRef, useState } from "react";
import logo from "/logo.png";
import techworksLogo from "/techworkslogo.png";
import "./App.css";

type Message = {
  role: "user" | "assistant";
  content: string;
  node?: string;
};

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";
const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/chat";

const NODE_LABELS: Record<string, string> = {
  unsupported: "Unsupported query",
  catalog_exact_id: "Catalog · exact ID lookup",
  catalog_search: "Catalog · text search",
  low_confidence: "Catalog · low confidence",
  not_found: "Catalog · not found",
  general: "General knowledge",
};

const NODE_MESSAGE_PATTERN = /^\[NODE:(\w+)\]$/;

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [currentNode, setCurrentNode] = useState<string | null>(null);
  const [model, setModel] = useState("");
  const ws = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // mirrors currentNode but readable synchronously inside the onmessage
  // closure, which otherwise only sees state from when the effect first ran
  const pendingNodeRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // the backend can take 15-20s to come up (Phoenix tracing init), so retry
    // instead of leaving the header stuck on "..." if we ask too early
    const fetchHealth = () => {
      fetch(`${BACKEND_URL}/health`)
        .then((res) => res.json())
        .then((data) => {
          if (!cancelled) setModel(data.model);
        })
        .catch(() => {
          if (!cancelled) setTimeout(fetchHealth, 2000);
        });
    };
    fetchHealth();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let retryTimeout: ReturnType<typeof setTimeout>;

    // the initial connection attempt commonly fires before the backend has
    // finished starting up, so without a retry loop the UI is stuck on
    // "Connecting..." forever - reconnect instead of giving up after one try
    const connect = () => {
      const socket = new WebSocket(WS_URL);
      ws.current = socket;

      socket.onopen = () => setConnected(true);

      socket.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          retryTimeout = setTimeout(connect, 2000);
        }
      };

      socket.onmessage = (event) => {
        if (event.data === "[DONE]") {
          setGenerating(false);
          setCurrentNode(null);
          pendingNodeRef.current = null;
          return;
        }

        const nodeMatch = NODE_MESSAGE_PATTERN.exec(event.data);
        if (nodeMatch) {
          pendingNodeRef.current = nodeMatch[1];
          setCurrentNode(nodeMatch[1]);
          return;
        }

        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant") {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...last,
              content: last.content + event.data,
            };
            return updated;
          }
          const node = pendingNodeRef.current ?? undefined;
          return [...prev, { role: "assistant", content: event.data, node }];
        });
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearTimeout(retryTimeout);
      ws.current?.close();
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, generating]);

  const sendMessage = () => {
    const text = input.trim();
    if (!text || !ws.current || ws.current.readyState !== WebSocket.OPEN || generating) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    ws.current.send(JSON.stringify({ type: "message", text }));
    setInput("");
    setGenerating(true);
  };

  // only show the typing indicator before any real content has arrived for
  // this turn — once the assistant message exists, the streaming text
  // itself is the feedback
  const awaitingFirstToken = generating && messages[messages.length - 1]?.role !== "assistant";
  const inputDisabled = !connected || generating;

  return (
    <>
      <header className="header">
        <img src={logo} alt="BMW" />
        <img src={techworksLogo} alt="BMW TechWorks" className="techworks-logo" />
        <div className="title-block">
          <h1>Chat</h1>
          <p className="subtitle">
            FastAPI x Websocket : Ollama (llama.cpp) x {model || "..."} : LangGraph-based agent
            orchestration
          </p>
        </div>
        <span className="status">{connected ? "Connected" : "Connecting..."}</span>
      </header>

      <div className="messages">
        {!connected && (
          <div className="loading-state">
            <span className="spinner" />
            <p>Connecting to the chatbot...</p>
          </div>
        )}
        {connected && messages.length === 0 && (
          <p className="empty-state">Ask something to get started.</p>
        )}
        {messages.map((message, i) => (
          <div key={i} className={`message ${message.role}`}>
            {message.node && (
              <div className="node-badge">{NODE_LABELS[message.node] ?? message.node}</div>
            )}
            {message.content}
          </div>
        ))}
        {awaitingFirstToken && (
          <div className="message assistant typing-indicator">
            {currentNode && (
              <div className="node-badge">{NODE_LABELS[currentNode] ?? currentNode}</div>
            )}
            <span className="typing-dots">
              <span></span>
              <span></span>
              <span></span>
            </span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-bar">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder={generating ? "Waiting for a response..." : "Ask something..."}
          disabled={inputDisabled}
        />
        <button onClick={sendMessage} disabled={inputDisabled || !input.trim()}>
          Send
        </button>
      </div>
    </>
  );
}

export default App;
