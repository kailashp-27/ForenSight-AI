// frontend/src/components/cctv/ReticleCanvas.tsx
// Transparent canvas laid over the <video>. The operator click-drags a
// cyan reticle; a floating "Regional Scan" button sends the region (as
// 0-1 relative coordinates) to the backend. While the scan runs, the
// reticle animates a scanning sweep.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Crosshair, Loader2 } from "lucide-react";
import type { RelativeBox } from "../../services/forensicApi";

interface ReticleCanvasProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  /** Changes whenever the visible frame changes → clears the selection. */
  frameKey: number;
  loading: boolean;
  disabled?: boolean;
  onScan: (box: RelativeBox) => void;
}

const CYAN = "#22d3ee";
const MIN_PX = 10; // ignore accidental clicks

interface PxBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export function ReticleCanvas({ videoRef, frameKey, loading, disabled, onScan }: ReticleCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dragStart = useRef<{ x: number; y: number } | null>(null);
  // Committed selection is stored RELATIVE (0-1) so it stays glued to the same
  // video content if the player is resized after drawing.
  const [box, setBox] = useState<PxBox | null>(null);
  const [dragBox, setDragBox] = useState<PxBox | null>(null); // live while dragging
  const [size, setSize] = useState({ w: 0, h: 0 });

  // Keep the canvas pixel-matched to the video's rendered box.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const sync = () => setSize({ w: video.clientWidth, h: video.clientHeight });
    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(video);
    video.addEventListener("loadedmetadata", sync);
    return () => {
      ro.disconnect();
      video.removeEventListener("loadedmetadata", sync);
    };
  }, [videoRef]);

  // A selection belongs to one frame — drop it when the frame changes.
  useEffect(() => {
    setBox(null);
    setDragBox(null);
    dragStart.current = null;
  }, [frameKey]);

  const toPx = useCallback(
    (b: PxBox): PxBox => ({ x1: b.x1 * size.w, y1: b.y1 * size.h, x2: b.x2 * size.w, y2: b.y2 * size.h }),
    [size]
  );

  const draw = useCallback(
    (t: number) => {
      const canvas = canvasRef.current;
      if (!canvas || size.w === 0) return;
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== Math.round(size.w * dpr) || canvas.height !== Math.round(size.h * dpr)) {
        canvas.width = Math.round(size.w * dpr);
        canvas.height = Math.round(size.h * dpr);
      }
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, size.w, size.h);

      const b = dragBox ?? (box ? toPx(box) : null);
      if (!b) return;
      const x = Math.min(b.x1, b.x2);
      const y = Math.min(b.y1, b.y2);
      const w = Math.abs(b.x2 - b.x1);
      const h = Math.abs(b.y2 - b.y1);

      // Dim everything outside the reticle.
      ctx.fillStyle = "rgba(2, 6, 12, 0.45)";
      ctx.fillRect(0, 0, size.w, size.h);
      ctx.clearRect(x, y, w, h);

      // Frame + translucent fill
      ctx.fillStyle = "rgba(34, 211, 238, 0.07)";
      ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = CYAN;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(x + 0.5, y + 0.5, w, h);

      // Crosshairs through the centre
      const cx = x + w / 2;
      const cy = y + h / 2;
      ctx.strokeStyle = "rgba(34, 211, 238, 0.55)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(cx, y);
      ctx.lineTo(cx, y + h);
      ctx.moveTo(x, cy);
      ctx.lineTo(x + w, cy);
      ctx.stroke();
      ctx.setLineDash([]);

      // Corner brackets
      const L = Math.min(14, w / 3, h / 3);
      ctx.strokeStyle = CYAN;
      ctx.lineWidth = 3;
      ctx.beginPath();
      for (const [px, py, sx, sy] of [
        [x, y, 1, 1],
        [x + w, y, -1, 1],
        [x, y + h, 1, -1],
        [x + w, y + h, -1, -1],
      ] as const) {
        ctx.moveTo(px + sx * L, py);
        ctx.lineTo(px, py);
        ctx.lineTo(px, py + sy * L);
      }
      ctx.stroke();

      // Scanning sweep while the VLM is working
      if (loading) {
        const phase = (Math.sin(t / 380) + 1) / 2;
        const sy = y + phase * h;
        const grad = ctx.createLinearGradient(0, sy - 18, 0, sy + 2);
        grad.addColorStop(0, "rgba(34, 211, 238, 0)");
        grad.addColorStop(1, "rgba(34, 211, 238, 0.55)");
        ctx.fillStyle = grad;
        ctx.fillRect(x, sy - 18, w, 20);
        ctx.strokeStyle = "#a5f3fc";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, sy);
        ctx.lineTo(x + w, sy);
        ctx.stroke();

        const pulse = 5 + 4 * Math.abs(Math.sin(t / 250));
        ctx.strokeStyle = "rgba(165, 243, 252, 0.9)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(cx, cy, pulse + 6, 0, Math.PI * 2);
        ctx.stroke();
      }
    },
    [box, dragBox, loading, size, toPx]
  );

  // Redraw on state change; run an animation loop only while loading.
  useEffect(() => {
    let raf = 0;
    if (loading) {
      const loop = (t: number) => {
        draw(t);
        raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);
    } else {
      draw(0);
    }
    return () => cancelAnimationFrame(raf);
  }, [draw, loading]);

  const localPoint = (e: React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return {
      x: Math.min(Math.max(0, e.clientX - rect.left), rect.width),
      y: Math.min(Math.max(0, e.clientY - rect.top), rect.height),
    };
  };

  const onMouseDown = (e: React.MouseEvent) => {
    if (disabled || loading || e.button !== 0) return;
    videoRef.current?.pause(); // the region must belong to a single, still frame
    const p = localPoint(e);
    dragStart.current = p;
    setBox(null);
    setDragBox({ x1: p.x, y1: p.y, x2: p.x, y2: p.y });
  };

  const onMouseMove = (e: React.MouseEvent) => {
    if (!dragStart.current) return;
    const p = localPoint(e);
    setDragBox({ x1: dragStart.current.x, y1: dragStart.current.y, x2: p.x, y2: p.y });
  };

  const finishDrag = (e: React.MouseEvent) => {
    if (!dragStart.current) return;
    const p = localPoint(e);
    const start = dragStart.current;
    dragStart.current = null;
    setDragBox(null);
    if (size.w > 0 && size.h > 0 && Math.abs(p.x - start.x) >= MIN_PX && Math.abs(p.y - start.y) >= MIN_PX) {
      setBox({
        x1: Math.min(start.x, p.x) / size.w,
        y1: Math.min(start.y, p.y) / size.h,
        x2: Math.max(start.x, p.x) / size.w,
        y2: Math.max(start.y, p.y) / size.h,
      });
    }
  };

  const submit = () => {
    if (!box) return;
    onScan({ x1: box.x1, y1: box.y1, x2: box.x2, y2: box.y2 });
  };

  // Place the floating button just below the box (or above if there's no room).
  const pxBox = box ? toPx(box) : null;
  const btnTop = pxBox ? (pxBox.y2 + 44 < size.h ? pxBox.y2 + 8 : Math.max(4, pxBox.y1 - 40)) : 0;
  const btnLeft = pxBox ? Math.min(Math.max(4, pxBox.x1), Math.max(4, size.w - 170)) : 0;

  return (
    <>
      <canvas
        ref={canvasRef}
        aria-label="Region selection overlay"
        data-testid="reticle-canvas"
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={finishDrag}
        onMouseLeave={finishDrag}
        style={{
          position: "absolute",
          inset: 0,
          width: size.w,
          height: size.h,
          cursor: disabled ? "not-allowed" : "crosshair",
        }}
      />
      {box && !dragBox && (
        <button
          onClick={submit}
          disabled={loading || disabled}
          style={{
            position: "absolute",
            top: btnTop,
            left: btnLeft,
            display: "flex",
            alignItems: "center",
            gap: 6,
            height: 32,
            padding: "0 12px",
            borderRadius: 6,
            border: `1px solid ${CYAN}`,
            background: "rgba(8, 47, 73, 0.92)",
            color: "#a5f3fc",
            fontSize: "0.75rem",
            fontWeight: 700,
            letterSpacing: "0.03em",
            cursor: loading ? "wait" : "pointer",
            lineHeight: 1,
            boxShadow: "0 4px 14px rgba(0,0,0,0.5)",
          }}
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Crosshair size={14} />}
          {loading ? "Scanning…" : "Regional Scan"}
        </button>
      )}
    </>
  );
}
