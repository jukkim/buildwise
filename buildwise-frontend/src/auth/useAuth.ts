/**
 * Unified auth hook — reads from AuthContext provided by AuthProvider.
 */
import { createContext, useContext } from "react";

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
}

export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: AuthUser | null;
  login: () => void;
  logout: () => void;
  getAccessToken: () => Promise<string | null>;
}

export const AuthContext = createContext<AuthState>({
  isAuthenticated: false,
  isLoading: true,
  user: null,
  login: () => {},
  logout: () => {},
  getAccessToken: async () => null,
});

export default function useAuth(): AuthState {
  return useContext(AuthContext);
}
