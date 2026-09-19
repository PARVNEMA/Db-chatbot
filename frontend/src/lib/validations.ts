import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});

export type LoginFormData = z.infer<typeof loginSchema>;

export const registerSchema = z
  .object({
    email: z.string().email("Please enter a valid email address"),
    password: z.string().min(6, "Password must be at least 6 characters"),
    confirmPassword: z.string().min(6, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

export type RegisterFormData = z.infer<typeof registerSchema>;

export const projectSchema = z.object({
  name: z.string().min(1, "Project name is required").max(255),
  description: z.string().max(1024).optional().nullable(),
});

export type ProjectFormData = z.infer<typeof projectSchema>;

export const connectionSchema = z.object({
  name: z.string().min(1, "Connection name is required").max(255),
  dialect: z.enum(["postgresql", "mysql", "mssql", "snowflake", "sqlite"], {
    errorMap: () => ({ message: "Please select a supported database dialect" }),
  }),
  connection_string: z.string().optional(),
  writes_enabled: z.boolean(),
  max_tables_per_changeset: z.coerce.number().min(1, "Min 1 table").max(5, "Max 5 tables"),
  max_total_rows_per_changeset: z.coerce.number().min(1, "Min 1 row").max(100, "Max 100 rows"),
  max_insert_rows_per_table: z.coerce.number().min(1, "Min 1 row").max(50, "Max 50 rows"),
  max_patch_rows_per_table: z.coerce.number().min(1, "Min 1 row").max(20, "Max 20 rows"),
  approval_timeout_minutes: z.coerce.number().min(1, "Min 1 min").max(120, "Max 120 mins"),
  undo_window_minutes: z.coerce.number().min(0, "Min 0 mins").max(1440, "Max 1440 mins (24 hrs)"),
  blocked_tables: z.string().optional(),
});

export type ConnectionFormData = z.infer<typeof connectionSchema>;

export const annotationSchema = z.object({
  target_type: z.enum(["table", "column"]),
  schema_table_id: z.string().uuid().optional().nullable(),
  schema_column_id: z.string().uuid().optional().nullable(),
  note: z.string().min(1, "Note cannot be empty"),
});

export type AnnotationFormData = z.infer<typeof annotationSchema>;
