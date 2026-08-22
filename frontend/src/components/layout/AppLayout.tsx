// frontend/src/components/layout/AppLayout.tsx
import React, { useEffect, useState } from "react";
import { useSocketStore } from "../../store/socketStore";
import { GlobalContextBar } from "./GlobalContextBar";
import { FocusCanvas } from "./FocusCanvas";
import { IntelligenceStrip } from "./IntelligenceStrip";
import { ContextPanel, type ContextPanelItem } from "./ContextPanel";
import { StatusToastContainer } from "../ui/StatusToast";

export function AppLayout() {
  const initSocket = useSocketStore((s) => s.initSocket);
  const [contextItem, setContextItem] = useState<ContextPanelItem | null>(null);

  useEffect(() => {
    initSocket();
  }, [initSocket]);

  return (
    <div className="hub-shell">
      {/* Top: Global Context Bar */}
      <GlobalContextBar />

      {/* Middle: Canvas + optional Context Panel side-by-side */}
      <div className="hub-body">
        <FocusCanvas />
        {contextItem && (
          <ContextPanel
            item={contextItem}
            onClose={() => setContextItem(null)}
          />
        )}
      </div>

      {/* Bottom: Intelligence Strip */}
      <IntelligenceStrip
        contextItem={contextItem}
        onContextSelect={setContextItem}
        onContextClose={() => setContextItem(null)}
      />

      {/* Toast container — top-right, above strip */}
      <StatusToastContainer />
    </div>
  );
}
