import { create } from "zustand";

import { fetchMe, getToken, logoutServerSide, setTokens } from "../services/api";
import type { AuthResponse, User } from "../types";

interface AuthState {
  user: User | null;
  /** True once we've checked whether a stored token is still valid. */
  initialized: boolean;
  setAuth: (auth: AuthResponse) => void;
  logout: () => void;
  initialize: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  initialized: false,

  setAuth: (auth) => {
    setTokens(auth.access_token, auth.refresh_token);
    set({ user: auth.user });
  },

  logout: () => {
    logoutServerSide(); // revoke the refresh token so the session can't be extended
    setTokens(null, null);
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
      setTokens(null, null);
      set({ user: null, initialized: true });
    }
  },
}));
