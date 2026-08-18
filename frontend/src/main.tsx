import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";

function App() {
  return (
    <div style={{ padding: "2rem", textAlign: "center" }}>
      <h1 style={{ color: "var(--color-accent)", fontSize: "2rem" }}>
        ForenSight AI
      </h1>
      <p style={{ color: "var(--color-muted)" }}>
        Intelligent Evidence Investigation System — scaffold ready ✓
      </p>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
