import { createContext, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getCurrentUser, loginRequest, logoutRequest } from "../lib/api.js";
import {
  clearStoredTokens,
  getStoredTokens,
  setStoredTokens,
} from "../lib/auth-storage.js";

const AuthContext = createContext(null);

export function AuthProvider({ children, queryClient }) {
  const [user, setUser] = useState(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  useEffect(() => {
    async function bootstrap() {
      const { accessToken, refreshToken } = getStoredTokens();
      if (!accessToken && !refreshToken) {
        setIsBootstrapping(false);
        return;
      }

      try {
        const me = await getCurrentUser();
        setUser(me);
      } catch {
        clearStoredTokens();
        setUser(null);
      } finally {
        setIsBootstrapping(false);
      }
    }

    bootstrap();
  }, []);

  async function login({ email, password }) {
    const tokens = await loginRequest({ email, password });
    setStoredTokens({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
    });
    const me = await getCurrentUser();
    setUser(me);
    return me;
  }

  async function logout() {
    try {
      await logoutRequest();
    } catch {
      // Clearing local session is still the safe fallback.
    } finally {
      clearStoredTokens();
      setUser(null);
      queryClient.clear();
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: Boolean(user),
        isBootstrapping,
        login,
        logout,
        setUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
