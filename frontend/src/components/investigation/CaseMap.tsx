// frontend/src/components/investigation/CaseMap.tsx
// Leaflet map of located evidence, with lines between evidence that share a
// matching clue. Tiles come from VITE_MAP_TILE_URL (point it at an on-prem
// tile server for air-gapped sites); with no tiles the markers and links
// still render on a plain background.

import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapPin } from "lucide-react";
import type { CaseMapData, MatchStrength } from "../../services/forensicApi";

const TILE_URL: string | undefined = (import.meta as any).env?.VITE_MAP_TILE_URL;
const STRENGTH_COLOR: Record<MatchStrength, string> = { STRONG: "#10b981", MEDIUM: "#f59e0b", WEAK: "#64748b" };
const TYPE_COLOR: Record<string, string> = { VIDEO: "#3b82f6", IMAGE: "#10b981", AUDIO: "#8b5cf6", DOCUMENT: "#f59e0b" };

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}

interface Props {
  data: CaseMapData | null;
  selectedEvidenceIds?: string[];
  onSelectEvidence?: (id: string) => void;
  onSetLocation?: (evidenceId: string, lat: number, lon: number) => Promise<void>;
}

export function CaseMap({ data, selectedEvidenceIds = [], onSelectEvidence, onSetLocation }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const [edit, setEdit] = useState<{ id: string; lat: string; lon: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = L.map(ref.current, { zoomControl: true, attributionControl: true }).setView([20, 0], 2);
    L.tileLayer(TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors",
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer || !data) return;
    layer.clearLayers();
    const byId = new Map(data.points.map((p) => [p.evidence_id, p]));

    for (const link of data.links) {
      const a = byId.get(link.from);
      const b = byId.get(link.to);
      if (!a || !b) continue;
      L.polyline(
        [
          [a.latitude!, a.longitude!],
          [b.latitude!, b.longitude!],
        ],
        { color: STRENGTH_COLOR[link.strength], weight: 3, dashArray: link.strength === "MEDIUM" ? "6 6" : undefined }
      )
        .bindTooltip(`${esc(link.kind)}: ${esc(link.value)} (${link.strength.toLowerCase()})`)
        .addTo(layer);
    }

    const bounds: L.LatLngTuple[] = [];
    for (const p of data.points) {
      const selected = selectedEvidenceIds.includes(p.evidence_id);
      const marker = L.circleMarker([p.latitude!, p.longitude!], {
        radius: selected ? 11 : 8,
        color: selected ? "#22d3ee" : "#0f172a",
        weight: selected ? 3 : 2,
        fillColor: TYPE_COLOR[p.file_type] ?? "#94a3b8",
        fillOpacity: 0.95,
      });
      marker.bindTooltip(
        `<strong>${esc(p.file_name)}</strong><br/>${esc(p.label ?? "")}` +
          (p.match_ids.length ? `<br/>${p.match_ids.length} shared clue(s)` : ""),
        { direction: "top" }
      );
      marker.on("click", () => onSelectEvidence?.(p.evidence_id));
      marker.addTo(layer);
      bounds.push([p.latitude!, p.longitude!]);
    }
    if (bounds.length === 1) map.setView(bounds[0], 14);
    else if (bounds.length > 1) map.fitBounds(bounds, { padding: [40, 40] });
  }, [data, selectedEvidenceIds, onSelectEvidence]);

  const save = async () => {
    if (!edit || !onSetLocation) return;
    const lat = Number(edit.lat);
    const lon = Number(edit.lon);
    if (!edit.lat.trim() || !edit.lon.trim() || !Number.isFinite(lat) || !Number.isFinite(lon) ||
        Math.abs(lat) > 90 || Math.abs(lon) > 180) {
      setErr("Enter a valid latitude (-90..90) and longitude (-180..180).");
      return;
    }
    try {
      await onSetLocation(edit.id, lat, lon);
      setEdit(null);
      setErr(null);
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const input: React.CSSProperties = {
    width: 110, height: 30, background: "var(--color-bg-input)", color: "var(--color-text-primary)",
    border: "1px solid var(--color-border-bright)", borderRadius: 6, padding: "0 8px", fontSize: "0.78rem",
  };

  return (
    <div style={{ display: "flex", gap: 12, height: "100%", minHeight: 420 }}>
      <div style={{ flex: 1, position: "relative", borderRadius: 8, overflow: "hidden", border: "1px solid var(--color-border)" }}>
        <div ref={ref} data-testid="case-map" style={{ position: "absolute", inset: 0, background: "#0b1220" }} />
        {data && data.points.length === 0 && (
          <div
            style={{
              position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
              pointerEvents: "none", zIndex: 500, color: "var(--color-text-muted)", fontSize: "0.85rem",
              textAlign: "center", padding: 24,
            }}
          >
            No evidence has a location yet. Photos with EXIF GPS are placed automatically; set others manually.
          </div>
        )}
      </div>

      <aside style={{ width: 280, flexShrink: 0, overflowY: "auto" }}>
        <h4 style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: 8 }}>
          Evidence locations
        </h4>
        {err && <p role="alert" style={{ color: "#fca5a5", fontSize: "0.72rem", marginBottom: 6 }}>{err}</p>}
        {[...(data?.points ?? []), ...(data?.unlocated ?? [])].map((p) => {
          const located = p.latitude != null;
          return (
            <div key={p.evidence_id} className="card" style={{ padding: "0.5rem 0.65rem", marginBottom: 6 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <MapPin size={13} style={{ color: located ? "#10b981" : "var(--color-text-subtle)" }} />
                <button
                  onClick={() => onSelectEvidence?.(p.evidence_id)}
                  style={{
                    background: "none", border: "none", color: "var(--color-text-primary)", fontSize: "0.78rem",
                    fontWeight: 600, cursor: "pointer", textAlign: "left", padding: 0, flex: 1, minWidth: 0,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}
                >
                  {p.file_name}
                </button>
              </div>
              <div style={{ fontSize: "0.68rem", color: "var(--color-text-muted)", marginTop: 2 }}>
                {located ? `${p.latitude!.toFixed(5)}, ${p.longitude!.toFixed(5)} · ${p.label ?? ""}` : "No location"}
              </div>
              {edit?.id === p.evidence_id ? (
                <div style={{ display: "flex", gap: 4, marginTop: 6, flexWrap: "wrap" }}>
                  <input style={input} placeholder="Latitude" aria-label="Latitude" value={edit.lat}
                         onChange={(e) => setEdit({ ...edit, lat: e.target.value })} />
                  <input style={input} placeholder="Longitude" aria-label="Longitude" value={edit.lon}
                         onChange={(e) => setEdit({ ...edit, lon: e.target.value })} />
                  <button onClick={save}
                          style={{ ...input, width: "auto", background: "var(--color-accent)", color: "#fff", cursor: "pointer", fontWeight: 700 }}>
                    Save
                  </button>
                </div>
              ) : (
                onSetLocation && (
                  <button
                    onClick={() => setEdit({ id: p.evidence_id, lat: p.latitude?.toString() ?? "", lon: p.longitude?.toString() ?? "" })}
                    style={{ marginTop: 4, background: "none", border: "none", color: "var(--color-accent)", fontSize: "0.7rem", cursor: "pointer", padding: 0 }}
                  >
                    {located ? "Edit location" : "Set location"}
                  </button>
                )
              )}
            </div>
          );
        })}
        <div style={{ marginTop: 10, fontSize: "0.65rem", color: "var(--color-text-subtle)", lineHeight: 1.6 }}>
          <div>Green line = strong link, dashed amber = medium link. Lines connect evidence that share a matching clue.</div>
          {!TILE_URL && <div>Base-map tiles need internet; set VITE_MAP_TILE_URL to use an on-prem tile server.</div>}
        </div>
      </aside>
    </div>
  );
}
