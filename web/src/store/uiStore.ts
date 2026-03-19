import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIStore {
  selectedAgentId: string | null;
  theme: 'dark' | 'light' | 'system';
  accentColor: string;
  setSelectedAgent: (id: string | null) => void;
  setTheme: (theme: 'dark' | 'light' | 'system') => void;
  setAccentColor: (color: string) => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      selectedAgentId: null,
      theme: 'system',
      accentColor: '#C8FF44',
      setSelectedAgent: (id) => set({ selectedAgentId: id }),
      setTheme: (theme) => set({ theme }),
      setAccentColor: (accentColor) => set({ accentColor }),
    }),
    {
      name: 'ui-storage',
      version: 2,
    }
  )
);
