import { apiClient, getStoredToken } from "./client";
import { API_BASE_URL } from "../constants";
import type { ApiResponse } from "@/types/api";
import type {
  AutoSuggestResponse,
  EmbeddingGenerateResponse,
  EmbeddingSSEEvent,
  SchemaSearchRequest,
  SchemaSearchResult,
} from "@/types/embedding";

export const embeddingsApi = {
  search: (
    projectId: string,
    data: SchemaSearchRequest
  ): Promise<ApiResponse<SchemaSearchResult[]>> =>
    apiClient.post(`/projects/${projectId}/schema/search`, data),

  generate: (
    projectId: string
  ): Promise<ApiResponse<EmbeddingGenerateResponse>> =>
    apiClient.post(`/projects/${projectId}/schema/embeddings/generate`),

  autoSuggest: (
    projectId: string,
    tableId: string
  ): Promise<ApiResponse<AutoSuggestResponse>> =>
    apiClient.post(`/projects/${projectId}/schema/auto-suggest`, { table_id: tableId }),
};

/**
 * Stream embedding generation via SSE using native fetch + ReadableStream.
 */
export function streamEmbeddingGeneration(
  projectId: string,
  callbacks: {
    onEvent: (event: EmbeddingSSEEvent) => void;
    onError?: (error: Error) => void;
    onComplete?: () => void;
  }
): AbortController {
  const controller = new AbortController();
  const token = getStoredToken();
  const url = `${API_BASE_URL}/projects/${projectId}/schema/embeddings/generate?stream=true`;

  fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`SSE request failed with status ${response.status}`);
      }
      if (!response.body) {
        throw new Error("No readable stream body returned");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const parsed: EmbeddingSSEEvent = JSON.parse(line.slice(6));
              callbacks.onEvent(parsed);
            } catch {
              // ignore parse errors for partial/heartbeat lines
            }
          }
        }
      }
      callbacks.onComplete?.();
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError?.(err instanceof Error ? err : new Error(String(err)));
      }
    });

  return controller;
}
