// frontend/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./index.css";
import { AppLayout } from "./components/layout/AppLayout";
import { Dashboard } from "./pages/Dashboard";
import { Cases } from "./pages/Cases";
import { CaseDetail } from "./pages/CaseDetail";
import { EvidenceBrowser } from "./pages/EvidenceBrowser";
import { Settings } from "./pages/Settings";

function PlaceholderPage({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div
      style={{
        padding: "2rem",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        textAlign: "center",
      }}
      className="animate-fade-in"
    >
      <div
        style={{
          width: 56, height: 56, borderRadius: 16,
          background: "var(--color-accent-light)",
          border: "1px solid var(--color-border-bright)",
          display: "flex", alignItems: "center", justifyContent: "center",
          marginBottom: 16, fontSize: "1.5rem",
        }}
      >
        🔬
      </div>
      <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: 8 }}>
        {title}
      </h1>
      <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", maxWidth: 320, lineHeight: 1.6 }}>
        {subtitle}
      </p>
      <div
        style={{
          marginTop: 20,
          padding: "0.375rem 0.875rem",
          borderRadius: 6,
          background: "var(--color-bg-elevated)",
          border: "1px solid var(--color-border)",
          fontSize: "0.7rem",
          fontFamily: "monospace",
          color: "var(--color-text-subtle)",
        }}
      >
        Coming in next phase
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/"          element={<Dashboard />} />
          <Route path="/cases"     element={<Cases />} />
          <Route path="/cases/new" element={<Cases />} />
          <Route path="/cases/:id" element={<CaseDetail />} />
          <Route path="/evidence"  element={<EvidenceBrowser />} />
          <Route path="/reports"   element={<PlaceholderPage title="Reports" subtitle="Generate investigation reports with cited evidence and AI summaries." />} />
          <Route path="/settings"  element={<Settings />} />
          <Route path="*"          element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
