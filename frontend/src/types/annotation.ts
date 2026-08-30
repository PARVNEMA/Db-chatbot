export interface Annotation {
  id: string;
  project_id: string;
  connection_id: string;
  schema_table_id: string | null;
  schema_column_id: string | null;
  target_type: "table" | "column";
  note: string;
  is_auto_generated: boolean;
  created_at: string;
  updated_at: string;
}

export interface AnnotationCreate {
  target_type: "table" | "column";
  schema_table_id?: string | null;
  schema_column_id?: string | null;
  note: string;
  is_auto_generated?: boolean;
}

export interface AnnotationUpdate {
  note: string;
}
