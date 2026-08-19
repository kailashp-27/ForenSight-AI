// frontend/src/store/socketStore.ts
import { create } from "zustand";
import { getSocket } from "../services/socket";

export interface ProcessingToast {
  id: string;
  evidence_id: string;
  file_name: string;
  status: string;
  progress: number;
  message: string;
}

interface SocketState {
  connected: boolean;
  toasts: ProcessingToast[];
  initSocket: () => void;
  dismissToast: (evidence_id: string) => void;
}

export const useSocketStore = create<SocketState>((set, get) => ({
  connected: false,
  toasts: [],

  initSocket: () => {
    const socket = getSocket();

    socket.on("connect", () => set({ connected: true }));
    socket.on("disconnect", () => set({ connected: false }));

    socket.on("evidence:status_update", (data: {
      evidence_id: string;
      status: string;
      progress?: number;
      message?: string;
      file_name?: string;
    }) => {
      set((s) => {
        const existing = s.toasts.find((t) => t.evidence_id === data.evidence_id);
        if (existing) {
          return {
            toasts: s.toasts.map((t) =>
              t.evidence_id === data.evidence_id
                ? { ...t, status: data.status, progress: data.progress ?? t.progress, message: data.message ?? t.message }
                : t
            ),
          };
        }
        return {
          toasts: [
            ...s.toasts,
            {
              id: data.evidence_id,
              evidence_id: data.evidence_id,
              file_name: data.file_name ?? "Unknown file",
              status: data.status,
              progress: data.progress ?? 0,
              message: data.message ?? "",
            },
          ],
        };
      });
    });
  },

  dismissToast: (evidence_id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.evidence_id !== evidence_id) })),
}));
