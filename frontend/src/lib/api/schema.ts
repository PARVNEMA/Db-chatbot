import { apiClient } from "./client";
import type { ApiResponse } from "@/types/api";
import type {
  IntrospectResponse,
  SchemaOverviewResponse,
  TableDetailResponse,
} from "@/types/schema";

export const schemaApi = {
  introspect: (projectId: string): Promise<ApiResponse<IntrospectResponse>> =>
    apiClient.post(`/projects/${projectId}/schema/introspect`),

  getOverview: (
    projectId: string
  ): Promise<ApiResponse<SchemaOverviewResponse>> =>
    apiClient.get(`/projects/${projectId}/schema`),

  listTables: (
    projectId: string
  ): Promise<ApiResponse<TableDetailResponse[]>> =>
    apiClient.get(`/projects/${projectId}/schema/tables`),

  getTable: (
    projectId: string,
    tableName: string
  ): Promise<ApiResponse<TableDetailResponse>> =>
    apiClient.get(`/projects/${projectId}/schema/tables/${tableName}`),
};
