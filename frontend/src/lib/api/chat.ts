import { apiClient, getStoredToken } from "./client";
import { API_BASE_URL } from "../constants";
import type { ApiResponse, PaginatedData, PaginationParams } from "@/types/api";
import type {
  ChatMessage,
  ChatMessageRequest,
  ChatSession,
  ChatSessionCreate,
  ChatSessionUpdate,
  ChatSSEEvent,
} from "@/types/chat";

export const chatApi = {
  createSession: (
    projectId: string,
    data?: ChatSessionCreate
  ): Promise<ApiResponse<ChatSession>> =>
    apiClient.post(`/projects/${projectId}/chat/sessions`, data ?? {}),

  listSessions: (
    projectId: string,
    params?: PaginationParams
  ): Promise<ApiResponse<PaginatedData<ChatSession>>> =>
    apiClient.get(`/projects/${projectId}/chat/sessions`, { params }),

  getSession: (
    projectId: string,
    sessionId: string
  ): Promise<ApiResponse<ChatSession>> =>
    apiClient.get(`/projects/${projectId}/chat/sessions/${sessionId}`),

  updateSession: (
    projectId: string,
    sessionId: string,
    data: ChatSessionUpdate
  ): Promise<ApiResponse<ChatSession>> =>
    apiClient.patch(
      `/projects/${projectId}/chat/sessions/${sessionId}`,
      data
    ),

  deleteSession: (
    projectId: string,
    sessionId: string
  ): Promise<ApiResponse<null>> =>
    apiClient.delete(`/projects/${projectId}/chat/sessions/${sessionId}`),

  listMessages: (
    projectId: string,
    sessionId: string,
    params?: PaginationParams
  ): Promise<ApiResponse<PaginatedData<ChatMessage>>> =>
    apiClient.get(
      `/projects/${projectId}/chat/sessions/${sessionId}/messages`,
      { params }
    ),
};

/**
 * Stream chat message execution via SSE using native fetch + ReadableStream.
 */
export function streamChatMessage(
  projectId: string,
  sessionId: string,
  payload: ChatMessageRequest,
  callbacks: {
    onEvent: (event: ChatSSEEvent) => void;
    onError?: (error: Error) => void;
    onComplete?: () => void;
  }
): AbortController {
  const controller = new AbortController();
  const token = getStoredToken();
  const url = `${API_BASE_URL}/projects/${projectId}/chat/sessions/${sessionId}/messages`;

  fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Chat stream failed with status ${response.status}`);
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
              const parsed: ChatSSEEvent = JSON.parse(line.slice(6));
              callbacks.onEvent(parsed);
            } catch {
              // ignore parse errors for partial chunks
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
