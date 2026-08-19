// frontend/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./index.css";
import { AppLayout } from "./components/layout/AppLayout";
import { Dashboard } from "./pages/Dashboard";
import { Cases } from "./pages/Cases";
import { CaseDetail } from "./pages/CaseDetail";

function SettingsPage() {
  return (
    <div className="p-8 animate-fade-in">
      <h1 className="text-2xl font-bold text-slate-900 mb-2">Settings</h1>
      <p className="text-sm text-slate-500">System configuration (coming soon).</p>
    </div>
  );
}

function EvidencePage() {
  return (
    <div className="p-8 animate-fade-in">
      <h1 className="text-2xl font-bold text-slate-900 mb-2">Evidence Browser</h1>
      <p className="text-sm text-slate-500">Browse all evidence across cases (coming in Phase 1).</p>
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
          <Route path="/evidence"  element={<EvidencePage />} />
          <Route path="/settings"  element={<SettingsPage />} />
          <Route path="*"          element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
