// frontend/src/components/layout/AppLayout.tsx
import React, { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { StatusToastContainer } from "../ui/StatusToast";
import { useSocketStore } from "../../store/socketStore";

export function AppLayout() {
  const initSocket = useSocketStore((s) => s.initSocket);

  useEffect(() => {
    initSocket();
  }, [initSocket]);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
      <StatusToastContainer />
    </div>
  );
}
