import { apiClient } from "./client";
import type { ApiResponse } from "@/types/api";
import type {
  Connection,
  ConnectionCreate,
  ConnectionTestRequest,
  ConnectionTestResponse,
  ConnectionUpdate,
} from "@/types/connection";

export const connectionsApi = {
  create: (
    projectId: string,
    data: ConnectionCreate
  ): Promise<ApiResponse<Connection>> =>
    apiClient.post(`/projects/${projectId}/connections`, data),

  get: (projectId: string): Promise<ApiResponse<Connection>> =>
    apiClient.get(`/projects/${projectId}/connections`),

  update: (
    projectId: string,
    data: ConnectionUpdate
  ): Promise<ApiResponse<Connection>> =>
    apiClient.patch(`/projects/${projectId}/connections`, data),

  delete: (projectId: string): Promise<ApiResponse<null>> =>
    apiClient.delete(`/projects/${projectId}/connections`),

  test: (
    projectId: string,
    data?: ConnectionTestRequest
  ): Promise<ApiResponse<ConnectionTestResponse>> =>
    apiClient.post(`/projects/${projectId}/connections/test`, data ?? {}),
};
