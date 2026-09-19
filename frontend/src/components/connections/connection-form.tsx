"use client";

import React, { useState, useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import {
  Plug,
  Loader2,
  Trash2,
  Lock,
  Sparkles,
  RefreshCw,
  Database,
  ShieldCheck,
  ShieldAlert,
  Sliders,
} from "lucide-react";

import type { Connection } from "@/types/connection";
import { useAuth } from "@/providers/auth-provider";
import { useProject } from "@/providers/project-provider";
import { connectionsApi } from "@/lib/api/connections";
import { connectionSchema, type ConnectionFormData } from "@/lib/validations";
import { DialectSelect, DIALECT_TEMPLATES } from "./dialect-select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ConfirmDialog } from "@/components/common/confirm-dialog";

interface ConnectionFormProps {
  projectId: string;
  connection: Connection | null;
  onSaved?: () => void;
  onDeleted?: () => void;
}

export function ConnectionForm({
  projectId,
  connection,
  onSaved,
  onDeleted,
}: ConnectionFormProps): React.JSX.Element {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const { user } = useAuth();
  const { project } = useProject();
  const isOwner = !project || user?.id === project.owner_id || !!user?.is_superuser;

  const isEditing = !!connection;

  const {
    register,
    handleSubmit,
    control,
    setValue,
    watch,
    getValues,
    reset,
    formState: { errors },
  } = useForm<ConnectionFormData>({
    resolver: zodResolver(connectionSchema),
    defaultValues: {
      name: connection?.name || "Production Database",
      dialect: (connection?.dialect as "postgresql" | "mysql" | "mssql" | "snowflake" | "sqlite") || "postgresql",
      connection_string: "",
      writes_enabled: connection?.writes_enabled ?? false,
      max_tables_per_changeset: connection?.max_tables_per_changeset ?? 1,
      max_total_rows_per_changeset: connection?.max_total_rows_per_changeset ?? 10,
      max_insert_rows_per_table: connection?.max_insert_rows_per_table ?? 5,
      max_patch_rows_per_table: connection?.max_patch_rows_per_table ?? 1,
      approval_timeout_minutes: connection?.approval_timeout_minutes ?? 15,
      undo_window_minutes: connection?.undo_window_minutes ?? 0,
      blocked_tables: connection?.blocked_tables ? connection.blocked_tables.join(", ") : "",
    },
  });

  const selectedDialect = watch("dialect");
  const writesEnabled = watch("writes_enabled");

  useEffect(() => {
    if (connection) {
      reset({
        name: connection.name,
        dialect: (connection.dialect as "postgresql" | "mysql" | "mssql" | "snowflake" | "sqlite") || "postgresql",
        connection_string: "",
        writes_enabled: connection.writes_enabled ?? false,
        max_tables_per_changeset: connection.max_tables_per_changeset ?? 1,
        max_total_rows_per_changeset: connection.max_total_rows_per_changeset ?? 10,
        max_insert_rows_per_table: connection.max_insert_rows_per_table ?? 5,
        max_patch_rows_per_table: connection.max_patch_rows_per_table ?? 1,
        approval_timeout_minutes: connection.approval_timeout_minutes ?? 15,
        undo_window_minutes: connection.undo_window_minutes ?? 0,
        blocked_tables: connection.blocked_tables ? connection.blocked_tables.join(", ") : "",
      });
    }
  }, [connection, reset]);

  const handleApplyTemplate = () => {
    const template = DIALECT_TEMPLATES[selectedDialect] || "";
    setValue("connection_string", template, { shouldValidate: true });
    toast.info(`Inserted sample template for ${selectedDialect.toUpperCase()}`);
  };

  const handleTestCredentials = async () => {
    const rawForm = getValues();
    if (!rawForm.connection_string) {
      toast.error("Please enter a connection string to test connectivity.");
      return;
    }

    setIsTesting(true);
    try {
      const res = await connectionsApi.test(projectId, {
        dialect: rawForm.dialect,
        connection_string: rawForm.connection_string,
      });

      if (res.success && res.data) {
        if (res.data.success) {
          toast.success(
            `Connection test passed! Latency: ${res.data.latency_ms ?? 0}ms`
          );
        } else {
          toast.error(res.data.message || "Connection test failed");
        }
      } else {
        throw new Error(res.message || "Connection test failed");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Connection test failed";
      toast.error(msg);
    } finally {
      setIsTesting(false);
    }
  };

  const onSubmit = async (data: ConnectionFormData) => {
    setIsSubmitting(true);
    try {
      const blockedTablesList = data.blocked_tables
        ? data.blocked_tables
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : [];

      if (isEditing) {
        const res = await connectionsApi.update(projectId, {
          name: data.name,
          dialect: data.dialect,
          connection_string: data.connection_string || undefined,
          writes_enabled: data.writes_enabled,
          max_tables_per_changeset: data.max_tables_per_changeset,
          max_total_rows_per_changeset: data.max_total_rows_per_changeset,
          max_insert_rows_per_table: data.max_insert_rows_per_table,
          max_patch_rows_per_table: data.max_patch_rows_per_table,
          approval_timeout_minutes: data.approval_timeout_minutes,
          undo_window_minutes: data.undo_window_minutes,
          blocked_tables: blockedTablesList,
        });
        if (res.success) {
          toast.success("Database connection & write policy updated successfully!");
          onSaved?.();
        } else {
          throw new Error(res.message || "Failed to update connection");
        }
      } else {
        const res = await connectionsApi.create(projectId, {
          name: data.name,
          dialect: data.dialect,
          connection_string: data.connection_string,
          writes_enabled: data.writes_enabled,
          max_tables_per_changeset: data.max_tables_per_changeset,
          max_total_rows_per_changeset: data.max_total_rows_per_changeset,
          max_insert_rows_per_table: data.max_insert_rows_per_table,
          max_patch_rows_per_table: data.max_patch_rows_per_table,
          approval_timeout_minutes: data.approval_timeout_minutes,
          undo_window_minutes: data.undo_window_minutes,
          blocked_tables: blockedTablesList,
        });
        if (res.success) {
          toast.success("Database connection established and saved!");
          onSaved?.();
        } else {
          throw new Error(res.message || "Failed to save connection");
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to save connection";
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    try {
      const res = await connectionsApi.delete(projectId);
      if (res.success) {
        toast.success("Database connection deleted and pooled engines closed");
        onDeleted?.();
      } else {
        throw new Error(res.message || "Failed to delete connection");
      }
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to delete connection";
      toast.error(msg);
    }
  };

  return (
    <>
      <Card className="border-zinc-800/80 bg-zinc-900/60 shadow-xl">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Database className="h-5 w-5 text-blue-400" />
                <CardTitle className="text-xl">
                  {isEditing ? "Update Database Connection" : "Connect Database"}
                </CardTitle>
              </div>
              <CardDescription>
                Provide connection credentials for your operational or analytics database.
              </CardDescription>
            </div>

            {isEditing && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setDeleteOpen(true)}
                className="text-zinc-500 hover:text-red-400 hover:bg-red-500/10 text-xs"
              >
                <Trash2 className="h-4 w-4 mr-1.5" />
                Disconnect DB
              </Button>
            )}
          </div>
        </CardHeader>

        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-5">
            {/* Connection Name */}
            <div className="space-y-2">
              <Label htmlFor="conn-name">Connection Name</Label>
              <Input
                id="conn-name"
                placeholder="e.g. Production Analytics, Read Replica"
                disabled={isSubmitting}
                {...register("name")}
              />
              {errors.name && (
                <p className="text-xs text-red-400">{errors.name.message}</p>
              )}
            </div>

            {/* Dialect Selector */}
            <div className="space-y-2">
              <Label>SQL Engine / Dialect</Label>
              <Controller
                name="dialect"
                control={control}
                render={({ field }) => (
                  <DialectSelect
                    value={field.value}
                    onValueChange={field.onChange}
                    disabled={isSubmitting}
                  />
                )}
              />
              {errors.dialect && (
                <p className="text-xs text-red-400">{errors.dialect.message}</p>
              )}
            </div>

            {/* Connection String */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="conn-string">
                  Connection String URI{" "}
                  {isEditing && (
                    <span className="text-zinc-500 font-normal">
                      (Leave blank to keep existing encrypted credentials)
                    </span>
                  )}
                </Label>
                <button
                  type="button"
                  onClick={handleApplyTemplate}
                  className="text-xs text-blue-400 hover:text-blue-300 transition flex items-center gap-1"
                >
                  <Sparkles className="h-3 w-3" />
                  Insert sample URI
                </button>
              </div>

              <Textarea
                id="conn-string"
                rows={3}
                placeholder={
                  isEditing
                    ? "••••••••••••••••••••••••••••••••••••••••••••"
                    : DIALECT_TEMPLATES[selectedDialect] ||
                      "postgresql://user:password@host:5432/dbname"
                }
                className="font-mono text-xs"
                disabled={isSubmitting}
                {...register("connection_string")}
              />
              {errors.connection_string && (
                <p className="text-xs text-red-400">
                  {errors.connection_string.message}
                </p>
              )}
            </div>

            {/* Safe Write Policy & Guardrails Section */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-950/50 p-4 space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-2.5">
                  <div className={`p-2 rounded-lg border ${writesEnabled ? "bg-amber-500/10 border-amber-500/30 text-amber-400" : "bg-zinc-800/80 border-zinc-700 text-zinc-400"}`}>
                    <Sliders className="h-4 w-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                      Safe Write Policy & Guardrails
                      {writesEnabled ? (
                        <span className="text-[10px] px-2 py-0.5 rounded-full font-mono font-medium bg-amber-500/20 text-amber-300 border border-amber-500/30">
                          Writes Enabled
                        </span>
                      ) : (
                        <span className="text-[10px] px-2 py-0.5 rounded-full font-mono font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
                          Read-Only
                        </span>
                      )}
                    </h4>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Configure safety limits and human-in-the-loop approval thresholds for database writes.
                    </p>
                  </div>
                </div>

                {/* Enable Writes Checkbox / Toggle */}
                <label className="relative flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-zinc-700 bg-zinc-900 text-blue-600 focus:ring-blue-500 focus:ring-offset-zinc-950"
                    disabled={isSubmitting || !isOwner}
                    {...register("writes_enabled")}
                  />
                  <span className="text-xs font-medium text-zinc-300">
                    Enable Writes
                  </span>
                </label>
              </div>

              {!isOwner && (
                <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 shrink-0" />
                  <span>Only the Project Owner can enable writes and adjust guardrail limits.</span>
                </div>
              )}

              {writesEnabled && (
                <div className="pt-2 border-t border-zinc-800/80 space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                    {/* Max Tables */}
                    <div className="space-y-1">
                      <Label htmlFor="max_tables" className="text-[11px] text-zinc-400">
                        Max Tables per Change-Set
                      </Label>
                      <Input
                        id="max_tables"
                        type="number"
                        min={1}
                        max={5}
                        disabled={isSubmitting || !isOwner}
                        className="h-8 text-xs font-mono"
                        {...register("max_tables_per_changeset")}
                      />
                      <span className="text-[10px] text-zinc-500">Between 1 and 5 tables</span>
                      {errors.max_tables_per_changeset && (
                        <p className="text-[10px] text-red-400">{errors.max_tables_per_changeset.message}</p>
                      )}
                    </div>

                    {/* Max Total Rows */}
                    <div className="space-y-1">
                      <Label htmlFor="max_total_rows" className="text-[11px] text-zinc-400">
                        Max Total Rows per Change-Set
                      </Label>
                      <Input
                        id="max_total_rows"
                        type="number"
                        min={1}
                        max={100}
                        disabled={isSubmitting || !isOwner}
                        className="h-8 text-xs font-mono"
                        {...register("max_total_rows_per_changeset")}
                      />
                      <span className="text-[10px] text-zinc-500">Between 1 and 100 total rows</span>
                      {errors.max_total_rows_per_changeset && (
                        <p className="text-[10px] text-red-400">{errors.max_total_rows_per_changeset.message}</p>
                      )}
                    </div>

                    {/* Max Insert Rows per Table */}
                    <div className="space-y-1">
                      <Label htmlFor="max_insert" className="text-[11px] text-zinc-400">
                        Max INSERT Rows / Table
                      </Label>
                      <Input
                        id="max_insert"
                        type="number"
                        min={1}
                        max={50}
                        disabled={isSubmitting || !isOwner}
                        className="h-8 text-xs font-mono"
                        {...register("max_insert_rows_per_table")}
                      />
                      <span className="text-[10px] text-zinc-500">Between 1 and 50 rows</span>
                      {errors.max_insert_rows_per_table && (
                        <p className="text-[10px] text-red-400">{errors.max_insert_rows_per_table.message}</p>
                      )}
                    </div>

                    {/* Max Patch Rows per Table */}
                    <div className="space-y-1">
                      <Label htmlFor="max_patch" className="text-[11px] text-zinc-400">
                        Max PATCH Rows / Table
                      </Label>
                      <Input
                        id="max_patch"
                        type="number"
                        min={1}
                        max={20}
                        disabled={isSubmitting || !isOwner}
                        className="h-8 text-xs font-mono"
                        {...register("max_patch_rows_per_table")}
                      />
                      <span className="text-[10px] text-zinc-500">Between 1 and 20 rows</span>
                      {errors.max_patch_rows_per_table && (
                        <p className="text-[10px] text-red-400">{errors.max_patch_rows_per_table.message}</p>
                      )}
                    </div>

                    {/* Approval Expiry Timeout */}
                    <div className="space-y-1">
                      <Label htmlFor="timeout" className="text-[11px] text-zinc-400">
                        Approval Expiry (Minutes)
                      </Label>
                      <Input
                        id="timeout"
                        type="number"
                        min={1}
                        max={120}
                        disabled={isSubmitting || !isOwner}
                        className="h-8 text-xs font-mono"
                        {...register("approval_timeout_minutes")}
                      />
                      <span className="text-[10px] text-zinc-500">1 to 120 mins (default 15)</span>
                      {errors.approval_timeout_minutes && (
                        <p className="text-[10px] text-red-400">{errors.approval_timeout_minutes.message}</p>
                      )}
                    </div>

                    {/* Soft-Undo Retention Window */}
                    <div className="space-y-1">
                      <Label htmlFor="undo_window" className="text-[11px] text-zinc-400">
                        Soft-Undo Window (Minutes)
                      </Label>
                      <Input
                        id="undo_window"
                        type="number"
                        min={0}
                        max={1440}
                        disabled={isSubmitting || !isOwner}
                        className="h-8 text-xs font-mono"
                        {...register("undo_window_minutes")}
                      />
                      <span className="text-[10px] text-zinc-500">0 = disabled, up to 1440 mins</span>
                      {errors.undo_window_minutes && (
                        <p className="text-[10px] text-red-400">{errors.undo_window_minutes.message}</p>
                      )}
                    </div>
                  </div>

                  {/* Blocked / Denylisted Tables */}
                  <div className="space-y-1 pt-1">
                    <Label htmlFor="blocked_tables" className="text-[11px] text-zinc-400">
                      Blocked / Denylisted Tables
                    </Label>
                    <Input
                      id="blocked_tables"
                      placeholder="audit_log, migrations, credentials, auth_tokens"
                      disabled={isSubmitting || !isOwner}
                      className="h-8 text-xs font-mono"
                      {...register("blocked_tables")}
                    />
                    <span className="text-[10px] text-zinc-500">
                      Comma-separated list of sensitive tables that are strictly forbidden from any write operations.
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Security Notice */}
            <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-start gap-3 text-xs text-zinc-300 leading-relaxed">
              <Lock className="h-4 w-4 text-blue-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-white block mb-0.5">
                  End-to-End Encryption & Read-Only Safety
                </strong>
                Connection strings are encrypted with Fernet keys before saving to our platform metadata database. Credentials are never logged, decrypted only during query execution, and protected by 3-tier read-only guardrails.
              </div>
            </div>
          </CardContent>

          <CardFooter className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-zinc-800/80 pt-5">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleTestCredentials}
              disabled={isTesting || isSubmitting}
              className="w-full sm:w-auto border-zinc-700 hover:bg-zinc-800 text-zinc-200 text-xs"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 mr-1.5 ${isTesting ? "animate-spin" : ""}`}
              />
              {isTesting ? "Testing Credentials..." : "Test Connectivity"}
            </Button>

            <Button
              type="submit"
              size="sm"
              disabled={isSubmitting}
              className="w-full sm:w-auto bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs px-5 shadow-md shadow-blue-600/20"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  Saving...
                </>
              ) : isEditing ? (
                "Save Changes"
              ) : (
                <>
                  <Plug className="mr-1.5 h-3.5 w-3.5" />
                  Connect Database
                </>
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Disconnect Database?"
        description={`Are you sure you want to disconnect "${connection?.name}"? All cached schema metadata will remain in read-only mode until a new database is linked.`}
        confirmLabel="Disconnect"
        variant="destructive"
        onConfirm={handleDelete}
      />
    </>
  );
}
