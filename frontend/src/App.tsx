import { useEffect, useRef, useState } from "react";
import logo from "/logo.png";
import techworksLogo from "/techworkslogo.png";
import "./App.css";

type Message = {
  role: "user" | "assistant";
  content: string;
};

const BACKEND_URL = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws/chat";

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [model, setModel] = useState("");
  const ws = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${BACKEND_URL}/health`)
      .then((res) => res.json())
      .then((data) => setModel(data.model))
      .catch(() => setModel(""));
  }, []);

  useEffect(() => {
    const socket = new WebSocket(WS_URL);
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);

    socket.onmessage = (event) => {
      if (event.data === "[DONE]") return;

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
        return [...prev, { role: "assistant", content: event.data }];
      });
    };

    ws.current = socket;
    return () => socket.close();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = () => {
    const text = input.trim();
    if (!text || !ws.current || ws.current.readyState !== WebSocket.OPEN) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    ws.current.send(text);
    setInput("");
  };

  return (
    <>
      <header className="header">
        <img src={logo} alt="BMW" />
        <img src={techworksLogo} alt="BMW TechWorks" className="techworks-logo" />
        <div className="title-block">
          <h1>Chat</h1>
          <p className="subtitle">
            FastAPI x Websocket : Ollama (llama.cpp) x {model || "..."}
          </p>
        </div>
        <span className="status">{connected ? "Connected" : "Connecting..."}</span>
      </header>

      <div className="messages">
        {messages.length === 0 && (
          <p className="empty-state">Ask something to get started.</p>
        )}
        {messages.map((message, i) => (
          <div key={i} className={`message ${message.role}`}>
            {message.content}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-bar">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendMessage()}
          placeholder="Ask something..."
          disabled={!connected}
        />
        <button onClick={sendMessage} disabled={!connected || !input.trim()}>
          Send
        </button>
      </div>
    </>
  );
}

export default App;
