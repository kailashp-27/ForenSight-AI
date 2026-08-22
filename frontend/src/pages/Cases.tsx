// frontend/src/pages/Cases.tsx
import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, Search, FolderOpen, ChevronRight, X } from "lucide-react";
import { Badge, statusToVariant } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { useCaseStore } from "../store/caseStore";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
  });
}

export function Cases() {
  const { cases, loading, fetchCases, createCase } = useCaseStore();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", created_by_name: "Investigator" });
  const [formError, setFormError] = useState("");

  useEffect(() => { fetchCases(); }, [fetchCases]);

  const filtered = cases.filter(
    (c) =>
      c.title.toLowerCase().includes(search.toLowerCase()) ||
      c.case_number.toLowerCase().includes(search.toLowerCase()),
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) { setFormError("Title is required"); return; }
    setCreating(true);
    try {
      const c = await createCase(form);
      setShowModal(false);
      setForm({ title: "", description: "", created_by_name: "Investigator" });
      navigate(`/cases/${c.id}`);
    } catch (err: any) {
      setFormError(err.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div
      style={{ padding: "1.5rem 2rem", display: "flex", flexDirection: "column", gap: "1.25rem", minHeight: "100%" }}
      className="animate-fade-in"
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ fontSize: "1.375rem", fontWeight: 700, color: "var(--color-text-primary)" }}>
            Investigation Cases
          </h1>
          <p style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginTop: 4 }}>
            {loading ? "Loading…" : `${cases.length} case${cases.length !== 1 ? "s" : ""} total`}
          </p>
        </div>
        <Button
          icon={<Plus style={{ width: 14, height: 14 }} />}
          onClick={() => setShowModal(true)}
        >
          New Case
        </Button>
      </div>

      {/* Search */}
      <div style={{ position: "relative", maxWidth: 320 }}>
        <Search
          style={{
            position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)",
            width: 14, height: 14, color: "var(--color-text-subtle)", pointerEvents: "none",
          }}
          aria-hidden="true"
        />
        <input
          type="search"
          placeholder="Search cases…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search cases"
          className="input-dark"
          style={{ paddingLeft: "2.25rem" }}
        />
      </div>

      {/* Table */}
      <div className="card" style={{ overflow: "hidden", flex: 1 }}>
        {filtered.length === 0 && !loading ? (
          <div
            style={{
              display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", padding: "4rem 1rem", textAlign: "center",
            }}
          >
            <FolderOpen style={{ width: 40, height: 40, color: "var(--color-border-bright)", marginBottom: 12 }} />
            <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--color-text-muted)" }}>
              {search ? "No matching cases" : "No cases yet"}
            </p>
            <p style={{ fontSize: "0.75rem", color: "var(--color-text-subtle)", marginTop: 4, marginBottom: 16 }}>
              {search ? "Try a different search term." : "Create your first case to begin."}
            </p>
            {!search && (
              <Button size="sm" icon={<Plus style={{ width: 12, height: 12 }} />} onClick={() => setShowModal(true)}>
                Create Case
              </Button>
            )}
          </div>
        ) : (
          <table className="dark-table" style={{ width: "100%", borderCollapse: "collapse" }} aria-label="Cases list">
            <thead>
              <tr>
                <th>Case #</th>
                <th>Title</th>
                <th>Status</th>
                <th>Investigator</th>
                <th>Evidence</th>
                <th>Created</th>
                <th className="sr-only">Open</th>
              </tr>
            </thead>
            <tbody>
              {(loading ? Array(5).fill(null) : filtered).map((c, i) => (
                <tr
                  key={c?.id ?? i}
                  onClick={() => c && navigate(`/cases/${c.id}`)}
                  style={{ cursor: c ? "pointer" : "default" }}
                >
                  <td>
                    {c ? <span style={{ fontFamily: "monospace", fontSize: "0.72rem", color: "var(--color-text-subtle)" }}>{c.case_number}</span>
                       : <div className="skeleton" style={{ height: 14, width: 80 }} />}
                  </td>
                  <td>
                    {c ? <span style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>{c.title}</span>
                       : <div className="skeleton" style={{ height: 14, width: 160 }} />}
                  </td>
                  <td>
                    {c ? <Badge variant={statusToVariant(c.status)} />
                       : <div className="skeleton" style={{ height: 20, width: 80, borderRadius: 999 }} />}
                  </td>
                  <td>
                    {c ? <span style={{ fontSize: "0.8rem", color: "var(--color-text-body)" }}>{c.created_by_name}</span>
                       : <div className="skeleton" style={{ height: 14, width: 100 }} />}
                  </td>
                  <td>
                    {c ? <span style={{ fontSize: "0.8rem", color: "var(--color-text-body)" }}>{c.evidence_count ?? 0}</span>
                       : <div className="skeleton" style={{ height: 14, width: 32 }} />}
                  </td>
                  <td>
                    {c ? <span style={{ fontFamily: "monospace", fontSize: "0.72rem", color: "var(--color-text-subtle)" }}>{formatDate(c.created_at)}</span>
                       : <div className="skeleton" style={{ height: 14, width: 80 }} />}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {c && <ChevronRight style={{ width: 14, height: 14, color: "var(--color-text-subtle)" }} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Bottom padding so FAB orb doesn't overlap */}
      <div style={{ height: "4rem" }} />

      {/* Create Case Modal */}
      {showModal && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Create new case"
          onClick={(e) => e.target === e.currentTarget && setShowModal(false)}
        >
          <div
            className="card animate-fade-in"
            style={{ width: "100%", maxWidth: 480, margin: "0 1rem" }}
          >
            {/* Modal header */}
            <div
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "1rem 1.25rem", borderBottom: "1px solid var(--color-border)",
              }}
            >
              <h2 style={{ fontSize: "0.9375rem", fontWeight: 700, color: "var(--color-text-primary)" }}>
                Create Investigation Case
              </h2>
              <button
                onClick={() => setShowModal(false)}
                style={{
                  width: 28, height: 28, borderRadius: 6, cursor: "pointer",
                  background: "transparent", border: "1px solid var(--color-border)",
                  color: "var(--color-text-muted)", display: "flex",
                  alignItems: "center", justifyContent: "center",
                  transition: "background 0.15s",
                }}
                aria-label="Close modal"
              >
                <X style={{ width: 14, height: 14 }} />
              </button>
            </div>

            <form onSubmit={handleCreate} style={{ padding: "1.25rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label
                  htmlFor="case-title"
                  style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "var(--color-text-body)", marginBottom: 6 }}
                >
                  Case Title <span style={{ color: "#ef4444" }} aria-hidden="true">*</span>
                </label>
                <input
                  id="case-title"
                  type="text"
                  placeholder="e.g. Downtown Fraud Investigation 2026"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  required
                  className="input-dark"
                />
              </div>

              <div>
                <label
                  htmlFor="case-desc"
                  style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "var(--color-text-body)", marginBottom: 6 }}
                >
                  Description
                </label>
                <textarea
                  id="case-desc"
                  rows={3}
                  placeholder="Brief case summary…"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="input-dark"
                />
              </div>

              <div>
                <label
                  htmlFor="investigator-name"
                  style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, color: "var(--color-text-body)", marginBottom: 6 }}
                >
                  Lead Investigator
                </label>
                <input
                  id="investigator-name"
                  type="text"
                  value={form.created_by_name}
                  onChange={(e) => setForm({ ...form, created_by_name: e.target.value })}
                  className="input-dark"
                />
              </div>

              {formError && (
                <p style={{ fontSize: "0.8rem", color: "#ef4444" }}>{formError}</p>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", paddingTop: 4 }}>
                <Button type="button" variant="secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  loading={creating}
                  icon={<Plus style={{ width: 14, height: 14 }} />}
                >
                  Create Case
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
