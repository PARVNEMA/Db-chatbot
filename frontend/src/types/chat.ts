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
  dry_run?: boolean;
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

export type WebSocketInboundMessage =
  | { type: "message"; content: string; dry_run?: boolean }
  | { type: "field_response"; session_id?: string; fields: Record<string, unknown> }
  | { type: "approve"; mutation_id: string; idempotency_key: string }
  | { type: "reject"; mutation_id: string; reason?: string }
  | { type: "undo"; mutation_id: string; reason?: string }
  | { type: "ping" };

export interface WebSocketOutboundFrame {
  type: string;
  sequence?: number;
  data?: Record<string, unknown>;
  timestamp?: string;
}

export interface MissingFieldItem {
  table: string;
  row_index: number;
  column: string;
  data_type: string;
  field_key: string;
  description: string;
}

export interface MutationFieldRequiredData {
  session_id: string;
  missing_fields: MissingFieldItem[];
  message: string;
}

export interface MutationChangeSetItem {
  operation: string;
  table: string;
  rows?: Array<Record<string, unknown>>;
  filter?: Record<string, unknown>;
  values?: Record<string, unknown>;
}

export interface MutationPreviewData {
  mutation_id?: string | null;
  dry_run?: boolean;
  change_set?: {
    summary?: string;
    mutations?: MutationChangeSetItem[];
  };
  preview_row_counts?: Record<string, number>;
  candidate_rows?: Record<string, Array<Record<string, unknown>>>;
  total_rows_affected?: number;
  expires_at?: string;
  approval_timeout_minutes?: number;
  summary?: string;
}

export interface MutationApprovalRequiredData {
  mutation_id: string;
  summary: string;
  total_rows_affected: number;
  expires_at: string;
  approval_timeout_minutes: number;
}

export interface MutationExecutingData {
  mutation_id: string;
  status: "EXECUTING";
}

export interface MutationExecutedData {
  mutation_id: string;
  status: "EXECUTED";
  total_rows_affected: number;
  tables_affected: Array<Record<string, unknown>>;
  latency_ms: number;
  summary?: string;
}

export interface PendingMutation {
  id: string;
  project_id: string;
  session_id: string;
  connection_id: string;
  proposer_id: string;
  approver_id?: string | null;
  status:
    | "PENDING_APPROVAL"
    | "APPROVED"
    | "EXECUTING"
    | "EXECUTED"
    | "REJECTED"
    | "FAILED"
    | "EXPIRED"
    | "UNDONE"
    | "DRY_RUN"
    | string;
  change_set_hash: string;
  preview_row_counts?: Record<string, number> | null;
  total_rows_affected?: number | null;
  idempotency_key?: string | null;
  expires_at: string;
  approved_at?: string | null;
  executed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MutationAuditLog {
  id: string;
  project_id: string;
  connection_id: string;
  mutation_id?: string | null;
  initiator_id: string;
  approver_id?: string | null;
  operation: string;
  tables_affected?: Array<Record<string, unknown>> | null;
  total_rows_affected: number;
  change_set_hash: string;
  status: string;
  error_details?: string | null;
  latency_ms?: number | null;
  created_at: string;
}

export interface MutationApproveRequest {
  idempotency_key: string;
}

export interface MutationRejectRequest {
  reason?: string;
}

export interface MutationUndoRequest {
  reason?: string;
}
