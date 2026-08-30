import { apiClient } from "./client";
import type { ApiResponse } from "@/types/api";
import type {
  Annotation,
  AnnotationCreate,
  AnnotationUpdate,
} from "@/types/annotation";

export const annotationsApi = {
  create: (
    projectId: string,
    data: AnnotationCreate
  ): Promise<ApiResponse<Annotation>> =>
    apiClient.post(`/projects/${projectId}/annotations`, data),

  list: (
    projectId: string,
    targetType?: "table" | "column"
  ): Promise<ApiResponse<Annotation[]>> =>
    apiClient.get(`/projects/${projectId}/annotations`, {
      params: targetType ? { target_type: targetType } : undefined,
    }),

  get: (
    projectId: string,
    annotationId: string
  ): Promise<ApiResponse<Annotation>> =>
    apiClient.get(`/projects/${projectId}/annotations/${annotationId}`),

  update: (
    projectId: string,
    annotationId: string,
    data: AnnotationUpdate
  ): Promise<ApiResponse<Annotation>> =>
    apiClient.put(`/projects/${projectId}/annotations/${annotationId}`, data),

  delete: (
    projectId: string,
    annotationId: string
  ): Promise<ApiResponse<null>> =>
    apiClient.delete(`/projects/${projectId}/annotations/${annotationId}`),
};
