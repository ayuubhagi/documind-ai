import { create } from "zustand";

import { fetchMe, getToken, setToken } from "../services/api";
import type { User } from "../types";

interface AuthState {
  user: User | null;
  /** True once we've checked whether a stored token is still valid. */
  initialized: boolean;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
  initialize: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  initialized: false,

  setAuth: (token, user) => {
    setToken(token);
    set({ user });
  },

  logout: () => {
    setToken(null);
    set({ user: null });
  },

  initialize: async () => {
    if (!getToken()) {
      set({ initialized: true });
      return;
    }
    try {
      const user = await fetchMe();
      set({ user, initialized: true });
    } catch {
      setToken(null);
      set({ user: null, initialized: true });
    }
  },
}));
