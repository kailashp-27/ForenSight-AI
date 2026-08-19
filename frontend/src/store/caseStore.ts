// frontend/src/store/caseStore.ts
import { create } from "zustand";
import { casesApi, type Case } from "../services/api";

interface CaseState {
  cases: Case[];
  selectedCase: Case | null;
  loading: boolean;
  error: string | null;

  fetchCases: () => Promise<void>;
  fetchCase: (id: string) => Promise<void>;
  createCase: (payload: { title: string; description?: string; created_by_name?: string }) => Promise<Case>;
  updateCase: (id: string, payload: Partial<Case>) => Promise<void>;
  deleteCase: (id: string) => Promise<void>;
  clearError: () => void;
}

export const useCaseStore = create<CaseState>((set, get) => ({
  cases: [],
  selectedCase: null,
  loading: false,
  error: null,

  fetchCases: async () => {
    set({ loading: true, error: null });
    try {
      const cases = await casesApi.list();
      set({ cases, loading: false });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },

  fetchCase: async (id) => {
    set({ loading: true, error: null });
    try {
      const c = await casesApi.get(id);
      set({ selectedCase: c, loading: false });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },

  createCase: async (payload) => {
    const c = await casesApi.create(payload);
    set((s) => ({ cases: [c, ...s.cases] }));
    return c;
  },

  updateCase: async (id, payload) => {
    const updated = await casesApi.update(id, payload);
    set((s) => ({
      cases: s.cases.map((c) => (c.id === id ? updated : c)),
      selectedCase: s.selectedCase?.id === id ? updated : s.selectedCase,
    }));
  },

  deleteCase: async (id) => {
    await casesApi.delete(id);
    set((s) => ({ cases: s.cases.filter((c) => c.id !== id) }));
  },

  clearError: () => set({ error: null }),
}));
