import { apiClient } from "./client";
import type { ApiResponse } from "@/types/api";
import type { TokenResponse, User, UserCreate, UserLogin } from "@/types/auth";

export const authApi = {
  register: (data: UserCreate): Promise<ApiResponse<User>> =>
    apiClient.post("/auth/register", data),

  login: (data: UserLogin): Promise<ApiResponse<TokenResponse>> =>
    apiClient.post("/auth/login", data),

  logout: (): Promise<ApiResponse<null>> =>
    apiClient.post("/auth/logout"),

  me: (): Promise<ApiResponse<User>> =>
    apiClient.get("/auth/me"),

  check: (): Promise<ApiResponse<User>> =>
    apiClient.get("/auth/check"),
};
