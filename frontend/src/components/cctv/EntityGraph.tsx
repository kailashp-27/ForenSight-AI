// frontend/src/components/cctv/EntityGraph.tsx
// Cytoscape.js relationship map built from VERIFIED findings only.

import React, { useEffect, useRef, useState } from "react";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { Network } from "lucide-react";
import type { CaseGraph, GraphEdgeData, GraphNodeData } from "../../services/forensicApi";

const TYPE_COLOR: Record<string, string> = {
  Person: "#3b82f6",
  Vehicle: "#ec4899",
  Item: "#10b981",
  Text: "#f59e0b",
  Evidence: "#64748b",
};

interface EntityGraphProps {
  graph: CaseGraph | null;
  loading?: boolean;
  /** Called with the finding ids behind a clicked entity node. */
  onSelectFindings?: (findingIds: string[]) => void;
}

export function EntityGraph({ graph, loading, onSelectFindings }: EntityGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [selection, setSelection] = useState<
    | { kind: "node"; data: GraphNodeData }
    | { kind: "edge"; data: GraphEdgeData }
    | null
  >(null);

  const empty = !graph || graph.nodes.length === 0;

  useEffect(() => {
    if (!containerRef.current || empty || !graph) return;

    const elements: ElementDefinition[] = [
      ...graph.nodes.map((n) => ({ group: "nodes" as const, data: { ...n.data } })),
      ...graph.edges.map((e) => ({ group: "edges" as const, data: { ...e.data } })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      minZoom: 0.3,
      maxZoom: 2.5,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": (ele) => TYPE_COLOR[ele.data("node_type")] ?? "#94a3b8",
            color: "#e2e8f0",
            "font-size": 10,
            "text-valign": "bottom",
            "text-margin-y": 5,
            "text-wrap": "ellipsis",
            "text-max-width": "110px",
            width: 30,
            height: 30,
            "border-width": 2,
            "border-color": "#0f172a",
          },
        },
        {
          selector: 'node[node_type = "Evidence"]',
          style: { shape: "round-rectangle", width: 44, height: 28, "font-size": 9 },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#475569",
            "curve-style": "bezier",
            "target-arrow-shape": "none",
            label: "data(label)",
            "font-size": 8,
            color: "#94a3b8",
            "text-rotation": "autorotate",
          },
        },
        { selector: 'edge[relation = "co_occurs"]', style: { "line-style": "dashed", "line-color": "#a855f7" } },
        { selector: ":selected", style: { "border-color": "#22d3ee", "border-width": 3, "line-color": "#22d3ee" } },
      ],
      layout: { name: "cose", animate: false, padding: 24, nodeRepulsion: () => 9000 },
    });

    cy.on("tap", "node", (evt) => {
      const data = evt.target.data() as GraphNodeData;
      setSelection({ kind: "node", data });
      if (data.node_type !== "Evidence") onSelectFindings?.(data.finding_ids);
    });
    cy.on("tap", "edge", (evt) => setSelection({ kind: "edge", data: evt.target.data() as GraphEdgeData }));
    cy.on("tap", (evt) => {
      if (evt.target === cy) setSelection(null);
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graph, empty]); // eslint-disable-line react-hooks/exhaustive-deps

  if (empty) {
    return (
      <div
        style={{
          height: "100%", minHeight: 220, display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", textAlign: "center", color: "var(--color-text-subtle)", padding: "1rem",
        }}
      >
        <Network size={34} style={{ opacity: 0.6, marginBottom: 8 }} />
        <p style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--color-text-muted)" }}>
          {loading ? "Building entity graph…" : "No verified entities yet"}
        </p>
        <p style={{ fontSize: "0.72rem", marginTop: 4, maxWidth: 320 }}>
          Entities appear here only after an investigator verifies the corresponding AI draft.
        </p>
      </div>
    );
  }

  return (
    <div style={{ position: "relative", height: "100%", minHeight: 260 }}>
      <div ref={containerRef} data-testid="entity-graph" style={{ position: "absolute", inset: 0 }} />

      {/* legend */}
      <div
        style={{
          position: "absolute", top: 8, right: 8, background: "rgba(10,7,18,0.85)",
          border: "1px solid var(--color-border)", borderRadius: 6, padding: "6px 8px", fontSize: "0.65rem",
        }}
      >
        {Object.entries(TYPE_COLOR).map(([t, c]) => (
          <div key={t} style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--color-text-body)" }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: c, display: "inline-block" }} />
            {t}
          </div>
        ))}
        <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--color-text-body)", marginTop: 2 }}>
          <span style={{ width: 12, borderTop: "2px dashed #a855f7", display: "inline-block" }} /> co-occurs
        </div>
      </div>

      {/* explainability panel */}
      {selection && (
        <div
          style={{
            position: "absolute", left: 8, bottom: 8, maxWidth: 360, background: "rgba(21,15,36,0.95)",
            border: "1px solid var(--color-border-bright)", borderRadius: 8, padding: "8px 10px", fontSize: "0.72rem",
            color: "var(--color-text-body)", lineHeight: 1.5,
          }}
        >
          {selection.kind === "node" ? (
            <>
              <strong style={{ color: "var(--color-text-primary)" }}>{selection.data.label}</strong>{" "}
              <span style={{ color: TYPE_COLOR[selection.data.node_type] }}>({selection.data.node_type})</span>
              {selection.data.readout && <div style={{ fontFamily: "monospace", color: "#22d3ee" }}>“{selection.data.readout}”</div>}
              {selection.data.confidence != null && <div>Confidence: {Math.round(selection.data.confidence * 100)}%</div>}
              {selection.data.first_seen && <div>First seen: <span style={{ fontFamily: "monospace" }}>{selection.data.first_seen}</span></div>}
              <div>{selection.data.finding_ids.length} supporting finding(s)</div>
            </>
          ) : (
            <>
              <strong style={{ color: "var(--color-text-primary)" }}>{selection.data.label}</strong>
              <div>{selection.data.reason}</div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
