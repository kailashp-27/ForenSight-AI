// frontend/src/components/layout/AppLayout.tsx
import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useSocketStore } from "../../store/socketStore";
import { GlobalContextBar } from "./GlobalContextBar";
import { FocusCanvas } from "./FocusCanvas";
import { IntelligenceStrip } from "./IntelligenceStrip";
import { ContextPanel, type ContextPanelItem } from "./ContextPanel";
import { StatusToastContainer } from "../ui/StatusToast";

export function AppLayout() {
  const initSocket = useSocketStore((s) => s.initSocket);
  const location = useLocation();
  const isDashboard = location.pathname === "/";
  
  const [contextState, setContextState] = useState<{
    item: ContextPanelItem;
    list: ContextPanelItem[];
    currentIndex: number;
  } | null>(null);

  // Clear context item on route change
  useEffect(() => {
    setContextState(null);
  }, [location.pathname]);

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
        {isDashboard && contextState && (
          <ContextPanel
            item={contextState.item}
            hasPrev={contextState.currentIndex > 0}
            hasNext={contextState.currentIndex < contextState.list.length - 1}
            onPrev={() => setContextState(s => s ? { ...s, currentIndex: s.currentIndex - 1, item: s.list[s.currentIndex - 1] } : null)}
            onNext={() => setContextState(s => s ? { ...s, currentIndex: s.currentIndex + 1, item: s.list[s.currentIndex + 1] } : null)}
            onClose={() => setContextState(null)}
          />
        )}
      </div>

      {/* Bottom: Intelligence Strip */}
      {isDashboard && (
        <IntelligenceStrip
          contextItem={contextState?.item ?? null}
          onContextSelect={(item, list) => {
            const index = list.findIndex(i => i.id === item.id);
            setContextState({ item, list, currentIndex: index !== -1 ? index : 0 });
          }}
          onContextClose={() => setContextState(null)}
        />
      )}

      {/* Toast container — top-right, above strip */}
      <StatusToastContainer />
    </div>
  );
}
