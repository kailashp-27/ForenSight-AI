// frontend/src/components/layout/FocusCanvas.tsx
import React from "react";
import { Outlet } from "react-router-dom";
import { FloatingActionOrb } from "./FloatingActionOrb";

export function FocusCanvas() {
  return (
    <div
      className="hub-canvas"
      id="focus-canvas"
      aria-label="Focus canvas"
      role="main"
    >
      <Outlet />
      <FloatingActionOrb />
    </div>
  );
}
