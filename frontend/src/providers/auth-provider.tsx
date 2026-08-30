"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { authApi } from "@/lib/api/auth";
import {
  clearStoredToken,
  getStoredToken,
  setStoredToken,
} from "@/lib/api/client";
import type { User, UserCreate, UserLogin } from "@/types/auth";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (data: UserLogin) => Promise<void>;
  register: (data: UserCreate) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshUser = useCallback(async () => {
    const currentToken = getStoredToken();
    if (!currentToken) {
      setUser(null);
      setToken(null);
      setIsLoading(false);
      return;
    }

    try {
      const response = await authApi.check();
      if (response.success && response.data) {
        setUser(response.data);
        setToken(currentToken);
      } else {
        clearStoredToken();
        setUser(null);
        setToken(null);
      }
    } catch {
      clearStoredToken();
      setUser(null);
      setToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    const currentToken = getStoredToken();

    if (!currentToken) {
      return;
    }

    authApi
      .check()
      .then((response) => {
        if (!isMounted) return;
        if (response.success && response.data) {
          setUser(response.data);
          setToken(currentToken);
        } else {
          clearStoredToken();
          setUser(null);
          setToken(null);
        }
      })
      .catch(() => {
        if (!isMounted) return;
        clearStoredToken();
        setUser(null);
        setToken(null);
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const login = async (data: UserLogin) => {
    setIsLoading(true);
    try {
      const response = await authApi.login(data);
      if (response.success && response.data) {
        const { access_token, user: userData } = response.data;
        setStoredToken(access_token);
        setToken(access_token);
        setUser(userData);
      } else {
        throw new Error(response.message || "Failed to log in");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (data: UserCreate) => {
    setIsLoading(true);
    try {
      const response = await authApi.register(data);
      if (!response.success) {
        throw new Error(response.message || "Registration failed");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await authApi.logout();
    } catch {
      // Ignore network errors on logout
    } finally {
      clearStoredToken();
      setUser(null);
      setToken(null);
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!user && !!token,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
