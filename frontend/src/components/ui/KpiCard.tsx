// frontend/src/components/ui/KpiCard.tsx
import React from "react";

interface KpiCardProps {
  icon: React.ReactNode;
  value: string | number;
  label: string;
  trend?: string;
  variant?: "default" | "warning" | "success" | "danger";
  loading?: boolean;
}

const trendColor = {
  default: "text-slate-500",
  warning: "text-amber-600",
  success: "text-emerald-600",
  danger:  "text-red-600",
};

const iconBg = {
  default: "bg-blue-50 text-blue-600",
  warning: "bg-amber-50 text-amber-600",
  success: "bg-emerald-50 text-emerald-600",
  danger:  "bg-red-50 text-red-600",
};

export function KpiCard({
  icon, value, label, trend, variant = "default", loading = false,
}: KpiCardProps) {
  return (
    <div className="card p-6 animate-fade-in">
      <div className="flex items-start justify-between">
        <div className={`flex items-center justify-center w-10 h-10 rounded-xl ${iconBg[variant]}`}>
          {icon}
        </div>
        {trend && (
          <span className={`text-xs font-medium ${trendColor[variant]}`}>{trend}</span>
        )}
      </div>
      <div className="mt-4">
        {loading ? (
          <div className="h-8 w-16 bg-slate-100 rounded animate-pulse" />
        ) : (
          <p className="text-3xl font-bold text-slate-900">{value}</p>
        )}
        <p className="text-sm text-slate-500 mt-1">{label}</p>
      </div>
    </div>
  );
}
