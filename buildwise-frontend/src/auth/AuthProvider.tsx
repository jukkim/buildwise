/**
 * Dual-mode auth provider:
 * - Auth0 mode: wraps with Auth0Provider, provides JWT-based auth
 * - Dev mode: provides localStorage-based auth (X-User-Id header)
 */
import { Auth0Provider, useAuth0 } from "@auth0/auth0-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import api, { setAccessTokenGetter } from "@/api/client";
import { AuthContext, type AuthState, type AuthUser } from "./useAuth";

interface AuthConfig {
  auth0_enabled: boolean;
  auth0_domain?: string;
  auth0_client_id?: string;
  auth0_audience?: string;
}

// --- Dev Mode Provider ---
function DevAuthProvider({ children }: { children: ReactNode }) {
  const [userId, setUserId] = useState(() => localStorage.getItem("buildwise_user_id"));
  const [userName, setUserName] = useState(() => localStorage.getItem("buildwise_user_name"));

  // Re-read localStorage on storage events (cross-tab) and custom events (same-tab)
  useEffect(() => {
    const sync = () => {
      setUserId(localStorage.getItem("buildwise_user_id"));
      setUserName(localStorage.getItem("buildwise_user_name"));
    };
    window.addEventListener("storage", sync);
    window.addEventListener("buildwise-auth-change", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("buildwise-auth-change", sync);
    };
  }, []);

  const login = useCallback(() => {
    window.location.href = "/login";
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("buildwise_user_id");
    localStorage.removeItem("buildwise_user_name");
    window.dispatchEvent(new Event("buildwise-auth-change"));
    window.location.href = "/login";
  }, []);

  const state: AuthState = useMemo(
    () => ({
      isAuthenticated: !!userId,
      isLoading: false,
      user: userId ? { id: userId, email: "", name: userName } : null,
      login,
      logout,
      getAccessToken: async () => null,
    }),
    [userId, userName, login, logout],
  );

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

// --- Auth0 Mode Inner Provider (must be inside Auth0Provider) ---
function Auth0InnerProvider({ children }: { children: ReactNode }) {
  const {
    isAuthenticated,
    isLoading,
    user: auth0User,
    loginWithRedirect,
    logout: auth0Logout,
    getAccessTokenSilently,
  } = useAuth0();

  const [backendUser, setBackendUser] = useState<AuthUser | null>(null);

  // Register token getter for API interceptor
  useEffect(() => {
    setAccessTokenGetter(async () => {
      try {
        return await getAccessTokenSilently();
      } catch {
        return null;
      }
    });
  }, [getAccessTokenSilently]);

  // Sync Auth0 user with backend on login
  useEffect(() => {
    if (!isAuthenticated || !auth0User) return;

    let cancelled = false;
    (async () => {
      try {
        const token = await getAccessTokenSilently();
        const res = await api.get<AuthUser>("/auth/me", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) {
          setBackendUser(res.data);
          // Store for display purposes
          localStorage.setItem("buildwise_user_name", res.data.name || res.data.email);
        }
      } catch (err) {
        console.error("[Auth0] Failed to sync user with backend:", err);
      }
    })();
    return () => { cancelled = true; };
  }, [isAuthenticated, auth0User, getAccessTokenSilently]);

  const login = useCallback(() => {
    loginWithRedirect();
  }, [loginWithRedirect]);

  const logout = useCallback(() => {
    localStorage.removeItem("buildwise_user_name");
    auth0Logout({ logoutParams: { returnTo: window.location.origin } });
  }, [auth0Logout]);

  const getAccessToken = useCallback(async () => {
    try {
      return await getAccessTokenSilently();
    } catch {
      return null;
    }
  }, [getAccessTokenSilently]);

  const state: AuthState = useMemo(
    () => ({
      isAuthenticated,
      isLoading,
      user: backendUser || (auth0User
        ? { id: auth0User.sub || "", email: auth0User.email || "", name: auth0User.name || null }
        : null),
      login,
      logout,
      getAccessToken,
    }),
    [isAuthenticated, isLoading, backendUser, auth0User, login, logout, getAccessToken],
  );

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

// --- Main AuthProvider ---
export default function AuthProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AuthConfig | null>(null);

  useEffect(() => {
    api
      .get<AuthConfig>("/auth/config")
      .then((res) => setConfig(res.data))
      .catch(() => {
        // Backend unreachable — default to dev mode
        setConfig({ auth0_enabled: false });
      });
  }, []);

  if (!config) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-gray-400 text-sm">Loading...</div>
      </div>
    );
  }

  if (config.auth0_enabled && config.auth0_domain && config.auth0_client_id) {
    return (
      <Auth0Provider
        domain={config.auth0_domain}
        clientId={config.auth0_client_id}
        authorizationParams={{
          redirect_uri: window.location.origin,
          audience: config.auth0_audience || undefined,
        }}
        cacheLocation="memory"
      >
        <Auth0InnerProvider>{children}</Auth0InnerProvider>
      </Auth0Provider>
    );
  }

  return <DevAuthProvider>{children}</DevAuthProvider>;
}
