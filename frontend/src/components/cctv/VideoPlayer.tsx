// frontend/src/components/cctv/VideoPlayer.tsx
// Frame-accurate player: scrubber, single-frame stepping, HH:MM:SS:MS readout.
// The overlay slot hosts <ReticleCanvas/> exactly on top of the video pixels.

import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Pause, Play, SkipBack, SkipForward } from "lucide-react";

/** Milliseconds → "HH:MM:SS:MS" (same notation the backend stores). */
export function formatTimestamp(ms: number): string {
  const total = Math.max(0, Math.round(ms));
  const h = Math.floor(total / 3_600_000);
  const m = Math.floor((total % 3_600_000) / 60_000);
  const s = Math.floor((total % 60_000) / 1_000);
  const msPart = total % 1_000;
  const p = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${p(h)}:${p(m)}:${p(s)}:${p(msPart, 3)}`;
}

export interface VideoPlayerHandle {
  seekToMs: (ms: number) => void;
  pause: () => void;
  getVideo: () => HTMLVideoElement | null;
  getFrameIndex: () => number;
}

interface VideoPlayerProps {
  src: string;
  /** Frames per second from the backend probe; falls back to 25 until known. */
  fps?: number;
  durationMs?: number;
  onFrameChange?: (frameIndex: number, timeMs: number) => void;
  /** Render prop: drawn on top of the video, same box (for the ROI reticle). */
  overlay?: (videoRef: React.RefObject<HTMLVideoElement | null>) => React.ReactNode;
}

const SPEEDS = [0.25, 0.5, 1, 2];

export const VideoPlayer = forwardRef<VideoPlayerHandle, VideoPlayerProps>(function VideoPlayer(
  { src, fps, durationMs, onFrameChange, overlay },
  ref
) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [timeMs, setTimeMs] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [loadedDurationMs, setLoadedDurationMs] = useState(0);

  const effectiveFps = fps && fps > 0 ? fps : 25;
  const totalMs = durationMs && durationMs > 0 ? durationMs : loadedDurationMs;
  const frameIndex = Math.max(0, Math.round((timeMs / 1000) * effectiveFps));
  // Display the frame's nominal time (matches what the backend stores for the
  // same frame) rather than the raw seek position, which carries a tiny epsilon.
  const displayMs = Math.round((frameIndex / effectiveFps) * 1000);

  // Report the current frame upward (drives ROI reset + scan requests).
  useEffect(() => {
    onFrameChange?.(frameIndex, timeMs);
  }, [frameIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  const seekToMs = useCallback((ms: number) => {
    const v = videoRef.current;
    if (!v) return;
    const max = Number.isFinite(v.duration) ? v.duration * 1000 : ms;
    const clamped = Math.min(Math.max(0, ms), max);
    v.currentTime = clamped / 1000;
    setTimeMs(clamped);
  }, []);

  // Step to an exact frame boundary (+0.01 frame so float error can't land on the previous frame).
  const stepFrames = useCallback(
    (delta: number) => {
      const v = videoRef.current;
      if (!v) return;
      v.pause();
      const target = Math.max(0, Math.round(v.currentTime * effectiveFps) + delta);
      seekToMs(((target + 0.01) / effectiveFps) * 1000);
    },
    [effectiveFps, seekToMs]
  );

  useImperativeHandle(
    ref,
    () => ({
      seekToMs,
      pause: () => videoRef.current?.pause(),
      getVideo: () => videoRef.current,
      getFrameIndex: () => Math.max(0, Math.round((videoRef.current?.currentTime ?? 0) * effectiveFps)),
    }),
    [seekToMs, effectiveFps]
  );

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) void v.play().catch(() => undefined);
    else v.pause();
  };

  // Keyboard: ←/→ one frame, Shift+←/→ one second, Space play/pause.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        if (e.shiftKey) seekToMs((videoRef.current?.currentTime ?? 0) * 1000 + 1000);
        else stepFrames(1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        if (e.shiftKey) seekToMs((videoRef.current?.currentTime ?? 0) * 1000 - 1000);
        else stepFrames(-1);
      } else if (e.key === " ") {
        e.preventDefault();
        togglePlay();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [seekToMs, stepFrames]);

  const btn: React.CSSProperties = {
    background: "var(--color-bg-elevated)",
    border: "1px solid var(--color-border-bright)",
    borderRadius: 6,
    width: 34,
    height: 34,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "var(--color-text-body)",
    cursor: "pointer",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%" }}>
      {/* Video + overlay share one positioned box so canvas pixels == video pixels */}
      <div style={{ display: "flex", justifyContent: "center", background: "#05070c", borderRadius: 8, padding: 8 }}>
        <div style={{ position: "relative", display: "inline-block", lineHeight: 0 }}>
          <video
            ref={videoRef}
            src={src}
            preload="auto"
            muted
            playsInline
            style={{ display: "block", maxWidth: "100%", maxHeight: "52vh", borderRadius: 4 }}
            onLoadedMetadata={(e) => setLoadedDurationMs(e.currentTarget.duration * 1000)}
            onTimeUpdate={(e) => setTimeMs(e.currentTarget.currentTime * 1000)}
            onSeeked={(e) => setTimeMs(e.currentTarget.currentTime * 1000)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
          />
          {overlay?.(videoRef)}
        </div>
      </div>

      {/* Scrubber */}
      <input
        type="range"
        aria-label="Video position"
        min={0}
        max={Math.max(1, Math.round(totalMs))}
        step={1}
        value={Math.min(Math.round(timeMs), Math.max(1, Math.round(totalMs)))}
        onChange={(e) => {
          videoRef.current?.pause();
          seekToMs(Number(e.target.value));
        }}
        style={{ width: "100%", accentColor: "var(--color-accent)" }}
      />

      {/* Transport + readout */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <button style={btn} aria-label="Back 1 second" onClick={() => seekToMs(timeMs - 1000)}>
          <SkipBack size={15} />
        </button>
        <button style={btn} aria-label="Previous frame" onClick={() => stepFrames(-1)}>
          <ChevronLeft size={17} />
        </button>
        <button
          style={{ ...btn, width: 42, background: "var(--color-accent)", borderColor: "var(--color-accent)", color: "#fff" }}
          aria-label={playing ? "Pause" : "Play"}
          onClick={togglePlay}
        >
          {playing ? <Pause size={17} /> : <Play size={17} />}
        </button>
        <button style={btn} aria-label="Next frame" onClick={() => stepFrames(1)}>
          <ChevronRight size={17} />
        </button>
        <button style={btn} aria-label="Forward 1 second" onClick={() => seekToMs(timeMs + 1000)}>
          <SkipForward size={15} />
        </button>

        <div
          style={{
            marginLeft: 8,
            fontFamily: "'Geist Mono', 'Courier New', monospace",
            fontSize: "0.95rem",
            fontWeight: 600,
            color: "#22d3ee",
            letterSpacing: "0.04em",
          }}
          aria-live="off"
          data-testid="timecode"
        >
          {formatTimestamp(displayMs)}
        </div>
        <div style={{ fontFamily: "monospace", fontSize: "0.72rem", color: "var(--color-text-muted)" }}>
          F{frameIndex} · {effectiveFps.toFixed(2)} fps · / {formatTimestamp(totalMs)}
        </div>

        <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => {
                setSpeed(s);
                if (videoRef.current) videoRef.current.playbackRate = s;
              }}
              style={{
                ...btn,
                width: "auto",
                padding: "0 8px",
                fontSize: "0.7rem",
                background: speed === s ? "var(--color-accent-light)" : "var(--color-bg-elevated)",
                borderColor: speed === s ? "var(--color-accent)" : "var(--color-border-bright)",
              }}
              aria-pressed={speed === s}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>
      <p style={{ fontSize: "0.68rem", color: "var(--color-text-subtle)" }}>
        ← / → step one frame · Shift + ← / → ±1 s · Space play/pause · drag on the frame to select a region
      </p>
    </div>
  );
});
