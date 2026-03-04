import React, { createContext, useContext, useState, useCallback } from "react";
import { loginUser, registerUser } from "../api/client";

const AuthContext = createContext(null);

/**
 * Provides authentication state and actions to the whole component tree.
 * Token is stored in localStorage so it survives page refreshes.
 */
export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [user, setUser] = useState(() => localStorage.getItem("username"));
  const [authError, setAuthError] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);

  const login = useCallback(async (username, password) => {
    setAuthLoading(true);
    setAuthError(null);
    try {
      const data = await loginUser(username, password);
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("username", username);
      setToken(data.access_token);
      setUser(username);
      return true;
    } catch (err) {
      setAuthError(err.message || "Login failed");
      return false;
    } finally {
      setAuthLoading(false);
    }
  }, []);

  const register = useCallback(
    async (username, password) => {
      setAuthLoading(true);
      setAuthError(null);
      try {
        await registerUser(username, password);
        // Auto-login after successful registration
        return await login(username, password);
      } catch (err) {
        setAuthError(err.message || "Registration failed");
        return false;
      } finally {
        setAuthLoading(false);
      }
    },
    [login],
  );

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    setToken(null);
    setUser(null);
  }, []);

  const clearAuthError = useCallback(() => setAuthError(null), []);

  const isAuthenticated = Boolean(token);

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isAuthenticated,
        authLoading,
        authError,
        login,
        register,
        logout,
        clearAuthError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

/** Hook to consume auth context. Must be used inside <AuthProvider>. */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
