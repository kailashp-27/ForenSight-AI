import React, { useState, useEffect, useRef } from "react";
import {
  X, Play, Pause, FileText, Download, Copy, Check, Search,
  Bot, Sparkles, RefreshCw, AlertTriangle, ShieldAlert, Cpu, ExternalLink
} from "lucide-react";
import { Button } from "../ui/Button";

interface TextChunk {
  id: string;
  chunk_index: number;
  content: string;
  source_type: string;
  start_time: number | null;
  end_time: number | null;
}

interface EvidenceDetail {
  id: string;
  case_id: string;
  file_name: string;
  file_type: string;
  status: string;
  transcription_status?: string;
  transcript?: string;
  textChunks?: TextChunk[];
}

interface AnalysisResult {
  evidence_id: string;
  model_used: string;
  risk_level: string;
  analysis: string;
  timestamp?: string;
}

interface EvidenceViewerProps {
  evidenceId: string;
  onClose: () => void;
}

export function EvidenceViewer({ evidenceId, onClose }: EvidenceViewerProps) {
  const [evidence, setEvidence] = useState<EvidenceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"transcript" | "analysis">("transcript");
  const [copied, setCopied] = useState(false);

  // Ollama Analysis states
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [selectedModel, setSelectedModel] = useState("llama3.2:1b");
  const [availableModels, setAvailableModels] = useState<string[]>(["llama3.2:1b"]);

  const mediaRef = useRef<HTMLMediaElement>(null);

  useEffect(() => {
    let mounted = true;
    async function fetchEvidence() {
      try {
        const res = await fetch(`/api/evidence/${evidenceId}`);
        if (!res.ok) throw new Error("Failed to load evidence");
        const data = await res.json();
        if (mounted) setEvidence(data);
      } catch (err) {
        console.error(err);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    async function fetchModels() {
      try {
        const res = await fetch("/api/analysis/models");
        if (res.ok) {
          const data = await res.json();
          if (mounted && data.models && data.models.length > 0) {
            setAvailableModels(data.models);
            setSelectedModel(data.default || data.models[0]);
          }
        }
      } catch (err) {
        // fallback
      }
    }

    fetchEvidence();
    fetchModels();
    return () => { mounted = false; };
  }, [evidenceId]);

  const handleSeek = (time: number | null) => {
    if (time !== null && mediaRef.current) {
      mediaRef.current.currentTime = time;
      mediaRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const handleCopyTranscript = () => {
    if (!evidence?.textChunks) return;
    const full = evidence.textChunks
      .map(c => `[${c.start_time !== null ? formatTime(c.start_time) : "0:00"}] ${c.content}`)
      .join("\n");
    navigator.clipboard.writeText(full);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadTranscript = () => {
    if (!evidence?.textChunks) return;
    const full = evidence.textChunks
      .map(c => `[${c.start_time !== null ? formatTime(c.start_time) : "0:00"}] ${c.content}`)
      .join("\n");
    const blob = new Blob([full], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${evidence.file_name}_transcript.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const runOllamaAnalysis = async () => {
    setAnalyzing(true);
    setActiveTab("analysis");
    try {
      const res = await fetch(`/api/analysis/evidence/${evidenceId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: selectedModel }),
      });
      if (!res.ok) throw new Error("Ollama analysis failed");
      const data = await res.json();
      setAnalysisResult(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) {
    return (
      <div className="modal-backdrop" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="card" style={{ padding: "2rem", display: "flex", alignItems: "center", gap: 12 }}>
          <RefreshCw className="animate-spin" style={{ color: "var(--color-accent)", width: 20, height: 20 }} />
          <span style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>Loading evidence stream...</span>
        </div>
      </div>
    );
  }

  if (!evidence) return null;

  // Use the verified streaming media path
  const mediaUrl = `/api/evidence/media/${evidenceId}`;

  // Filter text chunks by search
  const chunks = evidence.textChunks || [];
  const filteredChunks = searchQuery.trim()
    ? chunks.filter(c => c.content.toLowerCase().includes(searchQuery.toLowerCase()))
    : chunks;

  return (
    <div
      className="modal-backdrop"
      style={{ display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div 
        className="card animate-fade-in"
        style={{ 
          width: "92vw", maxWidth: 1280, height: "88vh", 
          display: "flex", flexDirection: "column", overflow: "hidden",
          border: "1px solid var(--color-border-bright)",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)"
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "0.875rem 1.25rem", borderBottom: "1px solid var(--color-border)",
            background: "var(--color-bg-elevated)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span
              style={{
                fontFamily: "monospace", fontSize: "0.68rem", fontWeight: 700,
                color: "#c084fc", background: "rgba(168,85,247,0.15)",
                border: "1px solid rgba(168,85,247,0.3)",
                borderRadius: 4, padding: "2px 8px",
              }}
            >
              {evidence.file_type}
            </span>
            <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--color-text-primary)" }}>
              {evidence.file_name}
            </h2>
            <span
              style={{
                fontSize: "0.68rem", padding: "2px 6px",
                background: evidence.status === "COMPLETED" ? "rgba(16,185,129,0.15)" : "rgba(245,158,11,0.15)",
                color: evidence.status === "COMPLETED" ? "#10b981" : "#f59e0b",
                border: `1px solid ${evidence.status === "COMPLETED" ? "rgba(16,185,129,0.3)" : "rgba(245,158,11,0.3)"}`,
                borderRadius: 4, fontWeight: 600,
              }}
            >
              {evidence.status}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Button
              size="sm"
              variant="primary"
              onClick={runOllamaAnalysis}
              loading={analyzing}
              icon={<Bot style={{ width: 14, height: 14 }} />}
            >
              Run Ollama AI Analysis
            </Button>

            <button
              onClick={onClose}
              style={{
                background: "transparent", border: "1px solid var(--color-border)",
                borderRadius: 6, width: 30, height: 30, display: "flex",
                alignItems: "center", justifyContent: "center",
                color: "var(--color-text-muted)", cursor: "pointer",
              }}
              aria-label="Close viewer"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content Body: Split Layout */}
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>

          {/* Left Panel: Media Player */}
          <div
            style={{
              flex: 1.2,
              background: "#080b11",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              position: "relative",
              padding: "1.5rem",
            }}
          >
            {evidence.file_type === "VIDEO" ? (
              <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <video 
                  ref={mediaRef as React.RefObject<HTMLVideoElement>} 
                  controls 
                  preload="metadata"
                  onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  style={{ maxWidth: "100%", maxHeight: "100%", borderRadius: 8, boxShadow: "0 10px 30px rgba(0,0,0,0.5)" }}
                  src={mediaUrl} 
                />
              </div>
            ) : evidence.file_type === "AUDIO" ? (
              <div
                style={{
                  width: "100%", maxWidth: 540, padding: "2rem",
                  background: "var(--color-bg-elevated)",
                  borderRadius: 12,
                  border: "1px solid var(--color-border-bright)",
                  boxShadow: "0 12px 36px rgba(0,0,0,0.4)",
                  display: "flex", flexDirection: "column", gap: "1.25rem",
                }}
              >
                {/* Audio Graphic / Visualizer Pill */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: isPlaying ? "#10b981" : "#a855f7", animation: isPlaying ? "pulse 1.5s infinite" : "none" }} />
                    <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
                      Forensic Audio Stream
                    </span>
                  </div>
                  <span style={{ fontFamily: "monospace", fontSize: "0.75rem", color: "var(--color-accent)", fontWeight: 600 }}>
                    {formatTime(currentTime)}
                  </span>
                </div>

                {/* HTML5 Native Audio Player with Direct Streaming */}
                <audio 
                  ref={mediaRef as React.RefObject<HTMLAudioElement>}
                  controls 
                  preload="metadata"
                  onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  style={{ width: "100%", height: 42 }}
                  src={mediaUrl}
                />

                {/* Playback Hint */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.7rem", color: "var(--color-text-subtle)" }}>
                  <span>Click any transcript segment on the right to jump directly to that timestamp.</span>
                </div>
              </div>
            ) : (
              <div style={{ color: "var(--color-text-muted)", display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
                <FileText size={48} style={{ color: "var(--color-border-bright)" }} />
                <p style={{ fontSize: "0.875rem" }}>Document / Image preview available in Inspector tab.</p>
              </div>
            )}
          </div>

          {/* Right Panel: Tabs for Transcript & Ollama Analysis */}
          <div
            style={{
              flex: 1.1,
              borderLeft: "1px solid var(--color-border)",
              display: "flex",
              flexDirection: "column",
              background: "var(--color-bg-base)",
            }}
          >
            {/* Tab Bar */}
            <div
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "0.625rem 1rem", borderBottom: "1px solid var(--color-border)",
                background: "var(--color-bg-elevated)",
              }}
            >
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={() => setActiveTab("transcript")}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "6px 12px", borderRadius: 6, border: "none",
                    background: activeTab === "transcript" ? "var(--color-bg-base)" : "transparent",
                    color: activeTab === "transcript" ? "var(--color-text-primary)" : "var(--color-text-muted)",
                    fontSize: "0.75rem", fontWeight: activeTab === "transcript" ? 700 : 500,
                    cursor: "pointer",
                  }}
                >
                  <FileText size={14} style={{ color: "#a855f7" }} />
                  <span>Whisper Transcript</span>
                  {chunks.length > 0 && (
                    <span style={{ fontSize: "0.65rem", background: "rgba(168,85,247,0.15)", color: "#c084fc", padding: "1px 5px", borderRadius: 10 }}>
                      {chunks.length}
                    </span>
                  )}
                </button>

                <button
                  onClick={() => setActiveTab("analysis")}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "6px 12px", borderRadius: 6, border: "none",
                    background: activeTab === "analysis" ? "var(--color-bg-base)" : "transparent",
                    color: activeTab === "analysis" ? "var(--color-text-primary)" : "var(--color-text-muted)",
                    fontSize: "0.75rem", fontWeight: activeTab === "analysis" ? 700 : 500,
                    cursor: "pointer",
                  }}
                >
                  <Bot size={14} style={{ color: "#3b82f6" }} />
                  <span>Ollama AI Analysis</span>
                  {analysisResult && (
                    <span style={{ fontSize: "0.65rem", background: "rgba(16,185,129,0.15)", color: "#10b981", padding: "1px 5px", borderRadius: 10, fontWeight: 700 }}>
                      DONE
                    </span>
                  )}
                </button>
              </div>

              {/* Utility actions */}
              {activeTab === "transcript" && chunks.length > 0 && (
                <div style={{ display: "flex", gap: 4 }}>
                  <button
                    onClick={handleCopyTranscript}
                    title="Copy Full Transcript"
                    style={{
                      background: "transparent", border: "1px solid var(--color-border)",
                      borderRadius: 4, padding: "4px 6px", color: "var(--color-text-muted)",
                      cursor: "pointer", display: "flex", alignItems: "center", gap: 4, fontSize: "0.68rem",
                    }}
                  >
                    {copied ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                    <span>{copied ? "Copied" : "Copy"}</span>
                  </button>
                  <button
                    onClick={handleDownloadTranscript}
                    title="Download Transcript as TXT"
                    style={{
                      background: "transparent", border: "1px solid var(--color-border)",
                      borderRadius: 4, padding: "4px 6px", color: "var(--color-text-muted)",
                      cursor: "pointer", display: "flex", alignItems: "center", gap: 4, fontSize: "0.68rem",
                    }}
                  >
                    <Download size={12} />
                  </button>
                </div>
              )}
            </div>

            {/* TAB 1: Transcript */}
            {activeTab === "transcript" && (
              <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
                {/* Search Bar */}
                <div style={{ padding: "0.625rem 1rem", borderBottom: "1px solid var(--color-border)", background: "var(--color-bg-canvas)" }}>
                  <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                    <Search size={13} style={{ position: "absolute", left: 10, color: "var(--color-text-subtle)" }} />
                    <input
                      type="text"
                      placeholder="Search within speech transcript..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      style={{
                        width: "100%", padding: "5px 10px 5px 30px",
                        fontSize: "0.75rem", background: "var(--color-bg-elevated)",
                        border: "1px solid var(--color-border)", borderRadius: 6,
                        color: "var(--color-text-primary)", outline: "none",
                      }}
                    />
                  </div>
                </div>

                {/* Transcript Chunks List */}
                <div style={{ flex: 1, overflowY: "auto", padding: "1rem", display: "flex", flexDirection: "column", gap: "0.625rem" }}>
                  {filteredChunks.length > 0 ? (
                    filteredChunks.map((chunk) => {
                      const isChunkActive =
                        chunk.start_time !== null &&
                        chunk.end_time !== null &&
                        currentTime >= chunk.start_time &&
                        currentTime <= chunk.end_time;

                      // Detect speaker in text like "[Investigator]: ..." or "[Suspect]: ..."
                      const match = chunk.content.match(/^(\[[^\]]+\]):\s*(.*)$/);
                      const speaker = match ? match[1] : null;
                      const bodyText = match ? match[2] : chunk.content;
                      const isInvestigator = speaker?.toLowerCase().includes("investigator");

                      return (
                        <div 
                          key={chunk.id} 
                          onClick={() => handleSeek(chunk.start_time)}
                          style={{ 
                            padding: "0.75rem", 
                            background: isChunkActive ? "rgba(168,85,247,0.12)" : "var(--color-bg-elevated)", 
                            borderRadius: 8,
                            border: isChunkActive ? "1px solid #a855f7" : "1px solid var(--color-border)",
                            cursor: "pointer",
                            transition: "all 0.15s ease",
                          }}
                          onMouseEnter={(e) => {
                            if (!isChunkActive) e.currentTarget.style.borderColor = "var(--color-border-bright)";
                          }}
                          onMouseLeave={(e) => {
                            if (!isChunkActive) e.currentTarget.style.borderColor = "var(--color-border)";
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              {speaker && (
                                <span
                                  style={{
                                    fontSize: "0.65rem", fontWeight: 700,
                                    color: isInvestigator ? "#3b82f6" : "#f59e0b",
                                    background: isInvestigator ? "rgba(59,130,246,0.1)" : "rgba(245,158,11,0.1)",
                                    padding: "1px 6px", borderRadius: 4,
                                  }}
                                >
                                  {speaker}
                                </span>
                              )}
                              <span style={{ fontSize: "0.68rem", color: "#a855f7", fontFamily: "monospace", fontWeight: 600 }}>
                                {chunk.start_time !== null ? formatTime(chunk.start_time) : "0:00"}
                              </span>
                            </div>
                            {isChunkActive && (
                              <span style={{ fontSize: "0.62rem", color: "#10b981", fontWeight: 700, display: "flex", alignItems: "center", gap: 3 }}>
                                <Play size={10} fill="#10b981" /> PLAYING
                              </span>
                            )}
                          </div>
                          <p style={{ fontSize: "0.82rem", color: "var(--color-text-body)", lineHeight: 1.55 }}>
                            {bodyText}
                          </p>
                        </div>
                      );
                    })
                  ) : (
                    <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--color-text-subtle)" }}>
                      <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--color-text-muted)" }}>
                        {searchQuery ? "No matching dialogue found" : "No transcript available"}
                      </p>
                      <p style={{ fontSize: "0.75rem", marginTop: 4 }}>
                        {evidence.transcription_status === "TRANSCRIBING" || evidence.status === "PROCESSING"
                          ? "Whisper speech-to-text pipeline is currently processing..."
                          : "Upload audio/video recordings to generate transcripts."}
                      </p>
                    </div>
                  )}
                </div>

                {/* Bottom Trigger for Ollama Analysis */}
                <div style={{ padding: "0.75rem 1rem", borderTop: "1px solid var(--color-border)", background: "var(--color-bg-canvas)" }}>
                  <Button
                    variant="secondary"
                    size="sm"
                    style={{ width: "100%", justifyContent: "center" }}
                    onClick={runOllamaAnalysis}
                    loading={analyzing}
                    icon={<Sparkles size={13} style={{ color: "#a855f7" }} />}
                  >
                    Analyze Transcript with Local Ollama ({selectedModel})
                  </Button>
                </div>
              </div>
            )}

            {/* TAB 2: Ollama AI Analysis */}
            {activeTab === "analysis" && (
              <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
                {/* Analysis Toolbar */}
                <div
                  style={{
                    padding: "0.625rem 1rem", borderBottom: "1px solid var(--color-border)",
                    background: "var(--color-bg-canvas)", display: "flex", alignItems: "center", justifyContent: "space-between"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Cpu size={14} style={{ color: "#3b82f6" }} />
                    <span style={{ fontSize: "0.72rem", color: "var(--color-text-muted)" }}>Model:</span>
                    <select
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      style={{
                        background: "var(--color-bg-elevated)", color: "var(--color-text-primary)",
                        border: "1px solid var(--color-border)", borderRadius: 4,
                        fontSize: "0.7rem", padding: "2px 6px", outline: "none",
                      }}
                    >
                      {availableModels.map(m => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  </div>

                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={runOllamaAnalysis}
                    loading={analyzing}
                    icon={<RefreshCw size={12} />}
                  >
                    Re-Analyze
                  </Button>
                </div>

                {/* Analysis Body */}
                <div style={{ flex: 1, overflowY: "auto", padding: "1.25rem" }}>
                  {analyzing ? (
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 12 }}>
                      <RefreshCw className="animate-spin" size={24} style={{ color: "#3b82f6" }} />
                      <p style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
                        Synthesizing forensic findings with {selectedModel}...
                      </p>
                      <p style={{ fontSize: "0.72rem", color: "var(--color-text-subtle)" }}>
                        Extracting financial mentions, behavioral red flags, and case corroborations.
                      </p>
                    </div>
                  ) : analysisResult ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                      {/* Risk Assessment Banner */}
                      <div
                        style={{
                          display: "flex", alignItems: "center", justifyContent: "space-between",
                          padding: "0.75rem 1rem", borderRadius: 8,
                          background: analysisResult.risk_level === "HIGH" ? "rgba(239,68,68,0.1)" : "rgba(245,158,11,0.1)",
                          border: `1px solid ${analysisResult.risk_level === "HIGH" ? "rgba(239,68,68,0.3)" : "rgba(245,158,11,0.3)"}`,
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <ShieldAlert size={18} style={{ color: analysisResult.risk_level === "HIGH" ? "#ef4444" : "#f59e0b" }} />
                          <div>
                            <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--color-text-primary)", textTransform: "uppercase" }}>
                              Forensic Risk Level: {analysisResult.risk_level}
                            </span>
                            <p style={{ fontSize: "0.68rem", color: "var(--color-text-muted)" }}>
                              Corroborates structured ₹4.7L anomalies in bank statements.
                            </p>
                          </div>
                        </div>
                        <span style={{ fontSize: "0.65rem", fontFamily: "monospace", color: "var(--color-text-subtle)" }}>
                          Ollama / {analysisResult.model_used}
                        </span>
                      </div>

                      {/* Formatted Markdown Analysis */}
                      <div
                        style={{
                          background: "var(--color-bg-elevated)", padding: "1.25rem",
                          borderRadius: 8, border: "1px solid var(--color-border)",
                          fontSize: "0.82rem", lineHeight: 1.6, color: "var(--color-text-body)",
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {analysisResult.analysis}
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", textAlign: "center", padding: "2rem" }}>
                      <Bot size={40} style={{ color: "var(--color-border-bright)", marginBottom: 12 }} />
                      <p style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
                        No AI Analysis Generated Yet
                      </p>
                      <p style={{ fontSize: "0.75rem", color: "var(--color-text-subtle)", marginTop: 4, maxWidth: 360, marginBottom: 16 }}>
                        Run the local Ollama LLM to synthesize dialogue inconsistencies, financial structuring mentions, and investigative leads.
                      </p>
                      <Button
                        variant="primary"
                        onClick={runOllamaAnalysis}
                        icon={<Sparkles size={14} />}
                      >
                        Generate Forensic Report
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            )}

          </div>

        </div>
      </div>
    </div>
  );
}
