import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { API_BASE_URL, TOKEN_STORAGE_KEY } from "../constants";
import type { ApiResponse } from "@/types/api";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Helper functions for token management
export const getStoredToken = (): string | null => {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
};

export const setStoredToken = (token: string): void => {
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  }
};

export const clearStoredToken = (): void => {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
};

// Request interceptor to attach JWT Bearer Token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getStoredToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to unwrap ApiResponse and handle auth errors
apiClient.interceptors.response.use(
  (response) => {
    // Return backend standard ApiResponse payload
    return response.data;
  },
  (error: AxiosError<ApiResponse<unknown>>) => {
    if (error.response?.status === 401) {
      clearStoredToken();
      if (
        typeof window !== "undefined" &&
        !window.location.pathname.startsWith("/login") &&
        !window.location.pathname.startsWith("/register")
      ) {
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination
        window.location.href = "/login";
      }
    }

    const apiError = error.response?.data;
    const errorMessage =
      apiError?.error?.message ||
      apiError?.message ||
      error.message ||
      "An unexpected error occurred";

    return Promise.reject(new Error(errorMessage));
  }
);
