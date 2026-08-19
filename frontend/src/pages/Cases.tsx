// frontend/src/pages/Cases.tsx
import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, Search, FolderOpen, ChevronRight } from "lucide-react";
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
      c.case_number.toLowerCase().includes(search.toLowerCase())
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
    <div className="p-6 lg:p-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Investigation Cases</h1>
          <p className="text-sm text-slate-500 mt-1">{cases.length} case{cases.length !== 1 ? "s" : ""} total</p>
        </div>
        <Button icon={<Plus />} onClick={() => setShowModal(true)}>New Case</Button>
      </div>

      {/* Search */}
      <div className="relative mb-6 max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="search"
          placeholder="Search cases..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search cases"
          className="w-full h-10 pl-9 pr-4 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {filtered.length === 0 && !loading ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <FolderOpen className="w-12 h-12 text-slate-200 mb-3" />
            <h3 className="text-sm font-semibold text-slate-600">
              {search ? "No matching cases" : "No cases yet"}
            </h3>
            <p className="text-xs text-slate-400 mt-1 mb-4">
              {search ? "Try a different search term." : "Create your first case to begin."}
            </p>
            {!search && (
              <Button size="sm" icon={<Plus />} onClick={() => setShowModal(true)}>Create Case</Button>
            )}
          </div>
        ) : (
          <table className="w-full text-sm" aria-label="Cases list">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100">
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Case #</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Title</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Investigator</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Evidence</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Created</th>
                <th className="sr-only">Open</th>
              </tr>
            </thead>
            <tbody>
              {(loading ? Array(5).fill(null) : filtered).map((c, i) => (
                <tr
                  key={c?.id ?? i}
                  onClick={() => c && navigate(`/cases/${c.id}`)}
                  className="border-b border-slate-50 hover:bg-blue-50/30 cursor-pointer transition-colors"
                >
                  <td className="px-6 py-4">
                    {c ? <span className="font-mono text-xs text-slate-500">{c.case_number}</span>
                       : <div className="h-4 w-24 bg-slate-100 rounded animate-pulse" />}
                  </td>
                  <td className="px-6 py-4">
                    {c ? <span className="font-medium text-slate-800">{c.title}</span>
                       : <div className="h-4 w-48 bg-slate-100 rounded animate-pulse" />}
                  </td>
                  <td className="px-6 py-4">
                    {c ? <Badge variant={statusToVariant(c.status)} />
                       : <div className="h-5 w-20 bg-slate-100 rounded-full animate-pulse" />}
                  </td>
                  <td className="px-6 py-4">
                    {c ? <span className="text-slate-600">{c.created_by_name}</span>
                       : <div className="h-4 w-28 bg-slate-100 rounded animate-pulse" />}
                  </td>
                  <td className="px-6 py-4">
                    {c ? <span className="text-slate-600">{c.evidence_count ?? 0}</span>
                       : <div className="h-4 w-8 bg-slate-100 rounded animate-pulse" />}
                  </td>
                  <td className="px-6 py-4">
                    {c ? <span className="font-mono text-xs text-slate-400">{formatDate(c.created_at)}</span>
                       : <div className="h-4 w-20 bg-slate-100 rounded animate-pulse" />}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {c && <ChevronRight className="w-4 h-4 text-slate-300" />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create Case Modal */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="Create new case"
        >
          <div className="card w-full max-w-lg mx-4 animate-fade-in">
            <div className="px-6 py-5 border-b border-slate-100">
              <h2 className="text-base font-semibold text-slate-900">Create Investigation Case</h2>
            </div>
            <form onSubmit={handleCreate} className="p-6 space-y-4">
              <div>
                <label htmlFor="case-title" className="block text-sm font-medium text-slate-700 mb-1">
                  Case Title <span className="text-red-500" aria-hidden="true">*</span>
                </label>
                <input
                  id="case-title"
                  type="text"
                  placeholder="e.g. Downtown Robbery 2026-08"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  required
                  className="w-full h-11 px-3 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label htmlFor="case-desc" className="block text-sm font-medium text-slate-700 mb-1">
                  Description
                </label>
                <textarea
                  id="case-desc"
                  rows={3}
                  placeholder="Brief case summary..."
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  className="w-full px-3 py-2.5 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>
              <div>
                <label htmlFor="investigator-name" className="block text-sm font-medium text-slate-700 mb-1">
                  Lead Investigator
                </label>
                <input
                  id="investigator-name"
                  type="text"
                  value={form.created_by_name}
                  onChange={(e) => setForm({ ...form, created_by_name: e.target.value })}
                  className="w-full h-11 px-3 text-sm border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              {formError && (
                <p className="text-sm text-red-600">{formError}</p>
              )}
              <div className="flex justify-end gap-3 pt-2">
                <Button type="button" variant="secondary" onClick={() => setShowModal(false)}>Cancel</Button>
                <Button type="submit" loading={creating} icon={<Plus />}>Create Case</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
