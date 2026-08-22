// frontend/src/components/ui/Button.tsx
import React from "react";
import { Loader2 } from "lucide-react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "destructive" | "ghost";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: React.ReactNode;
}

const VARIANT_STYLE: Record<string, React.CSSProperties> = {
  primary: {
    background: "var(--color-accent)",
    color: "#ffffff",
    border: "1px solid var(--color-accent)",
  },
  secondary: {
    background: "var(--color-bg-elevated)",
    color: "var(--color-text-body)",
    border: "1px solid var(--color-border-bright)",
  },
  destructive: {
    background: "#dc2626",
    color: "#ffffff",
    border: "1px solid #dc2626",
  },
  ghost: {
    background: "transparent",
    color: "var(--color-text-muted)",
    border: "1px solid transparent",
  },
};

const SIZE_STYLE: Record<string, React.CSSProperties> = {
  sm: { height: 32, padding: "0 0.75rem", fontSize: "0.75rem", gap: 6 },
  md: { height: 38, padding: "0 1rem",    fontSize: "0.8125rem", gap: 8 },
  lg: { height: 44, padding: "0 1.25rem", fontSize: "0.875rem", gap: 8 },
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  children,
  className = "",
  disabled,
  style,
  ...props
}: ButtonProps) {
  return (
    <button
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 8,
        fontWeight: 600,
        cursor: disabled || loading ? "not-allowed" : "pointer",
        opacity: disabled || loading ? 0.5 : 1,
        transition: "background 0.15s, border-color 0.15s, transform 0.1s, box-shadow 0.15s",
        outline: "none",
        flexShrink: 0,
        ...VARIANT_STYLE[variant],
        ...SIZE_STYLE[size],
        ...style,
      }}
      disabled={disabled || loading}
      onMouseEnter={(e) => {
        if (disabled || loading) return;
        if (variant === "primary") {
          e.currentTarget.style.background = "var(--color-accent-hover)";
          e.currentTarget.style.boxShadow = "var(--glow-accent)";
        } else if (variant === "secondary") {
          e.currentTarget.style.borderColor = "var(--color-accent)";
          e.currentTarget.style.color = "var(--color-accent)";
        }
      }}
      onMouseLeave={(e) => {
        if (disabled || loading) return;
        e.currentTarget.style.background = VARIANT_STYLE[variant].background as string;
        e.currentTarget.style.boxShadow = "none";
        e.currentTarget.style.color = VARIANT_STYLE[variant].color as string;
        e.currentTarget.style.borderColor = (VARIANT_STYLE[variant].border as string).replace("1px solid ", "");
      }}
      onMouseDown={(e) => { if (!disabled && !loading) e.currentTarget.style.transform = "scale(0.96)"; }}
      onMouseUp={(e) => { e.currentTarget.style.transform = "scale(1)"; }}
      {...props}
    >
      {loading ? (
        <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} />
      ) : icon ? (
        <span style={{ display: "flex", alignItems: "center", width: 14, height: 14, flexShrink: 0 }}>
          {icon}
        </span>
      ) : null}
      {children}
    </button>
  );
}
