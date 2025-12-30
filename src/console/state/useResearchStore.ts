import { create } from "zustand"
import { persist } from "zustand/middleware"

type EvidenceCoords = {
  page: number
  bbox: { x1: number; y1: number; x2: number; y2: number }
}

interface ResearchState {
  selectedEvidence: EvidenceCoords | null
  selectedTripleId: string | null
  currentBlockId: string | null
  focusMode: boolean
  librarianSidebarOpen: boolean
  patchSidebarOpen: boolean
  setEvidence: (coords: EvidenceCoords | null, tripleId?: string | null) => void
  setCurrentBlock: (blockId: string | null) => void
  toggleFocusMode: () => void
  setLibrarianSidebarOpen: (open: boolean) => void
  setPatchSidebarOpen: (open: boolean) => void
}

export const useResearchStore = create<ResearchState>()(
  persist(
    (set) => ({
      selectedEvidence: null,
      selectedTripleId: null,
      currentBlockId: null,
      focusMode: false,
      librarianSidebarOpen: false,
      patchSidebarOpen: false,
      setEvidence: (coords, tripleId = null) =>
        set({
          selectedEvidence: coords,
          selectedTripleId: tripleId ?? null,
        }),
      setCurrentBlock: (blockId) =>
        set({
          currentBlockId: blockId,
        }),
      toggleFocusMode: () =>
        set((state) => ({
          focusMode: !state.focusMode,
        })),
      setLibrarianSidebarOpen: (open) =>
        set({
          librarianSidebarOpen: open,
        }),
      setPatchSidebarOpen: (open) =>
        set({
          patchSidebarOpen: open,
        }),
    }),
    {
      name: "research-store",
      partialize: (state) => ({
        focusMode: state.focusMode,
        librarianSidebarOpen: state.librarianSidebarOpen,
        patchSidebarOpen: state.patchSidebarOpen,
      }),
    }
  )
)
