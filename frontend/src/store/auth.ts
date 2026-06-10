import { create } from "zustand";
import { persist } from "zustand/middleware";

interface Employee {
  id: number;
  name_ar: string;
  name_en: string;
  email: string;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  employee: Employee | null;
  isAuthenticated: boolean;
  login: (tokens: { access_token: string; refresh_token: string }, employee: Employee) => void;
  logout: () => void;
  updateAccessToken: (token: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      employee: null,
      isAuthenticated: false,

      login: (tokens, employee) =>
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          employee,
          isAuthenticated: true,
        }),

      logout: () =>
        set({
          accessToken: null,
          refreshToken: null,
          employee: null,
          isAuthenticated: false,
        }),

      updateAccessToken: (token) => set({ accessToken: token }),
    }),
    {
      name: "hr-auth",
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        employee: state.employee,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
