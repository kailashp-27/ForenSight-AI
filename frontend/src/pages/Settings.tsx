// frontend/src/pages/Settings.tsx
import React, { useState } from "react";
import { Save, Server, Shield, Database, Cpu } from "lucide-react";
import { Button } from "../components/ui/Button";

export function Settings() {
  const [model, setModel] = useState("llama3.2:1b");
  const [visionModel, setVisionModel] = useState("llava:7b");
  const [apiUrl, setApiUrl] = useState("http://localhost:11434");
  const [retention, setRetention] = useState("30");

  const [saving, setSaving] = useState(false);

  const handleSave = () => {
    setSaving(true);
    // Mock save
    setTimeout(() => setSaving(false), 800);
  };

  return (
    <div
      style={{ padding: "1.5rem 2rem", display: "flex", flexDirection: "column", gap: "1.25rem", minHeight: "100%" }}
      className="animate-fade-in"
    >
      <div>
        <h1 style={{ fontSize: "1.375rem", fontWeight: 700, color: "var(--color-text-primary)" }}>
          System Settings
        </h1>
        <p style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginTop: 4 }}>
          Configure API endpoints, AI models, and workspace preferences.
        </p>
      </div>

      <div className="card" style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        
        {/* Local AI Models */}
        <section>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <Cpu size={16} color="var(--color-accent)" />
            <h2 style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--color-text-primary)" }}>Local AI Models (Ollama)</h2>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 6 }}>
                Primary Analysis Model
              </label>
              <select
                className="input-dark"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                <option value="llama3.2:1b">Llama 3.2 (1B)</option>
                <option value="llama3.1:8b">Llama 3.1 (8B)</option>
                <option value="mistral">Mistral (7B)</option>
              </select>
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 6 }}>
                Vision / OCR Model
              </label>
              <select
                className="input-dark"
                value={visionModel}
                onChange={(e) => setVisionModel(e.target.value)}
              >
                <option value="llava:7b">LLaVA (7B)</option>
                <option value="bakllava">BakLLaVA</option>
              </select>
            </div>
          </div>
        </section>

        <hr style={{ border: "none", borderTop: "1px solid var(--color-border)" }} />

        {/* Endpoints */}
        <section>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <Server size={16} color="var(--color-accent)" />
            <h2 style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--color-text-primary)" }}>API Endpoints</h2>
          </div>
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 6 }}>
              Ollama Base URL
            </label>
            <input
              type="text"
              className="input-dark"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="http://localhost:11434"
            />
          </div>
        </section>

        <hr style={{ border: "none", borderTop: "1px solid var(--color-border)" }} />

        {/* Data & Security */}
        <section>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <Shield size={16} color="var(--color-accent)" />
            <h2 style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--color-text-primary)" }}>Data & Security</h2>
          </div>
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 6 }}>
              Audit Log Retention (Days)
            </label>
            <input
              type="number"
              className="input-dark"
              value={retention}
              onChange={(e) => setRetention(e.target.value)}
              style={{ width: 120 }}
            />
          </div>
        </section>
        
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
          <Button icon={<Save size={14} />} onClick={handleSave}>
            {saving ? "Saving..." : "Save Configuration"}
          </Button>
        </div>
      </div>
    </div>
  );
}
