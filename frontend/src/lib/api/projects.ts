import { apiClient } from "./client";
import type { ApiResponse, PaginatedData, PaginationParams } from "@/types/api";
import type { Project, ProjectCreate, ProjectUpdate } from "@/types/project";

export const projectsApi = {
  create: (data: ProjectCreate): Promise<ApiResponse<Project>> =>
    apiClient.post("/projects", data),

  list: (params?: PaginationParams): Promise<ApiResponse<PaginatedData<Project>>> =>
    apiClient.get("/projects", { params }),

  get: (projectId: string): Promise<ApiResponse<Project>> =>
    apiClient.get(`/projects/${projectId}`),

  update: (projectId: string, data: ProjectUpdate): Promise<ApiResponse<Project>> =>
    apiClient.patch(`/projects/${projectId}`, data),

  delete: (projectId: string): Promise<ApiResponse<null>> =>
    apiClient.delete(`/projects/${projectId}`),
};
