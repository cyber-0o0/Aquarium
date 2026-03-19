import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface User {
  id: string;
  telegram_id?: string;
  username?: string;
  first_name?: string;
  last_name?: string;
  wallet_address?: string;
  plan: string;
  user_metadata?: any;
  created_at?: string;
}

interface AuthStore {
  accessToken: string | null;
  user: User | null;
  isInitialized: boolean;
  setAuth: (token: string, user: User) => void;
  updateUser: (partial: Partial<User>) => void;
  clearAuth: () => void;
  setInitialized: () => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      accessToken: null,
      user: null,
      isInitialized: false,

      setAuth: (token, user) => {
        set({ accessToken: token, user });
      },

      updateUser: (partial) => {
        const current = get().user;
        if (current) set({ user: { ...current, ...partial } });
      },

      clearAuth: () => {
        set({ accessToken: null, user: null });
      },

      setInitialized: () => set({ isInitialized: true }),
    }),
    {
      name: 'aihubton-auth',
      // persist token + user so username survives reload
      partialize: (state) => ({
        accessToken: state.accessToken,
        user: state.user,
      }),
    }
  )
);
