// frontend/src/pages/Dashboard.tsx
import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import { FolderOpen, FileVideo, Clock, ShieldAlert, ChevronRight, Plus } from "lucide-react";
import { KpiCard } from "../components/ui/KpiCard";
import { Badge, statusToVariant } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { useCaseStore } from "../store/caseStore";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
  });
}

export function Dashboard() {
  const { cases, loading, fetchCases } = useCaseStore();

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

  const totalEvidence = cases.reduce((s, c) => s + (c.evidence_count ?? 0), 0);
  const openCases = cases.filter((c) => c.status === "OPEN").length;
  const flaggedCases = cases.filter((c) => c.status === "UNDER_REVIEW").length;

  return (
    <div className="p-6 lg:p-8 animate-fade-in">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Investigation Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Overview of all active cases and evidence</p>
        </div>
        <Link to="/cases/new">
          <Button icon={<Plus />} size="md">New Case</Button>
        </Link>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard
          icon={<FolderOpen className="w-5 h-5" />}
          value={loading ? "—" : cases.length}
          label="Total Cases"
          loading={loading}
        />
        <KpiCard
          icon={<FileVideo className="w-5 h-5" />}
          value={loading ? "—" : totalEvidence}
          label="Evidence Files"
          loading={loading}
        />
        <KpiCard
          icon={<Clock className="w-5 h-5" />}
          value={loading ? "—" : openCases}
          label="Open Cases"
          variant="default"
          loading={loading}
        />
        <KpiCard
          icon={<ShieldAlert className="w-5 h-5" />}
          value={loading ? "—" : flaggedCases}
          label="Under Review"
          variant={flaggedCases > 0 ? "warning" : "default"}
          loading={loading}
        />
      </div>

      {/* Recent Cases Table */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-800">Recent Cases</h2>
          <Link to="/cases" className="text-xs text-blue-600 hover:text-blue-700 font-medium">
            View all →
          </Link>
        </div>

        {cases.length === 0 && !loading ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <FolderOpen className="w-12 h-12 text-slate-200 mb-3" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-slate-600">No cases yet</h3>
            <p className="text-xs text-slate-400 mt-1 mb-4">Create your first investigation case to get started.</p>
            <Link to="/cases/new">
              <Button size="sm" icon={<Plus />}>Create Case</Button>
            </Link>
          </div>
        ) : (
          <table className="w-full text-sm" aria-label="Recent cases">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100">
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Case #</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Title</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Evidence</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Created</th>
                <th className="sr-only">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(loading ? Array(4).fill(null) : cases.slice(0, 8)).map((c, i) => (
                <tr key={c?.id ?? i} className="border-b border-slate-50 hover:bg-slate-50/70 transition-colors">
                  <td className="px-6 py-4">
                    {c ? (
                      <span className="font-mono text-xs text-slate-500">{c.case_number}</span>
                    ) : (
                      <div className="h-4 w-24 bg-slate-100 rounded animate-pulse" />
                    )}
                  </td>
                  <td className="px-6 py-4">
                    {c ? (
                      <span className="font-medium text-slate-800">{c.title}</span>
                    ) : (
                      <div className="h-4 w-40 bg-slate-100 rounded animate-pulse" />
                    )}
                  </td>
                  <td className="px-6 py-4">
                    {c ? (
                      <Badge variant={statusToVariant(c.status)} />
                    ) : (
                      <div className="h-5 w-16 bg-slate-100 rounded-full animate-pulse" />
                    )}
                  </td>
                  <td className="px-6 py-4">
                    {c ? (
                      <span className="text-slate-600">{c.evidence_count ?? 0}</span>
                    ) : (
                      <div className="h-4 w-8 bg-slate-100 rounded animate-pulse" />
                    )}
                  </td>
                  <td className="px-6 py-4">
                    {c ? (
                      <span className="font-mono text-xs text-slate-400">{formatDate(c.created_at)}</span>
                    ) : (
                      <div className="h-4 w-20 bg-slate-100 rounded animate-pulse" />
                    )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {c && (
                      <Link
                        to={`/cases/${c.id}`}
                        className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
                        aria-label={`Open case ${c.case_number}`}
                      >
                        Open <ChevronRight className="w-3 h-3" />
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
