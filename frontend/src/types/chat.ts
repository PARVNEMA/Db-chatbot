export interface ChatSession {
  id: string;
  project_id: string;
  connection_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionCreate {
  title?: string;
}

export interface ChatSessionUpdate {
  title: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  project_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  token_count: number | null;
  metadata?: Record<string, unknown> | null;
  metadata_json?: Record<string, unknown> | null;
  query_run_id: string | null;
  selected_query_run?: QueryRun | null;
  stream_events?: ChatSSEEvent[];
  created_at: string;
}

export interface ChatMessageRequest {
  content: string;
}

export interface QueryRun {
  id: string;
  chat_message_id: string;
  project_id: string;
  connection_id: string;
  attempt_number: number;
  parent_run_id: string | null;
  nl_prompt: string;
  generated_sql: string | null;
  status: string;
  error_message: string | null;
  result_summary: string | null;
  result_row_count: number | null;
  latency_ms: number | null;
  created_at: string;
  updated_at: string;
}

export interface ChatSSEEvent {
  event:
    | "message_received"
    | "intent_classified"
    | "sql_generated"
    | "sql_executed"
    | "sql_error"
    | "summary_ready"
    | "result_formatted"
    | "final_result"
    | "error"
    | "done"
    | string;
  message_id?: string;
  assistant_message_id?: string;
  query_run_id?: string;
  role?: string;
  content?: string;
  intent_type?: string;
  extracted_entities?: string[];
  generated_sql?: string;
  sql_dialect?: string;
  execution_result?: Record<string, unknown>[];
  row_count?: number;
  result_row_count?: number;
  sample_rows?: Record<string, unknown>[];
  nl_summary?: string;
  error?: string;
  error_message?: string;
  message_text?: string;
  retry_count?: number;
  latency_ms?: number;
  status?: string;
  message?: ChatMessage;
}
