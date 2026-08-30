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
} from "lucide-react";

import type { Connection } from "@/types/connection";
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
    },
  });

  const selectedDialect = watch("dialect");

  useEffect(() => {
    if (connection) {
      reset({
        name: connection.name,
        dialect: (connection.dialect as "postgresql" | "mysql" | "mssql" | "snowflake" | "sqlite") || "postgresql",
        connection_string: "",
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
      if (isEditing) {
        const res = await connectionsApi.update(projectId, {
          name: data.name,
          dialect: data.dialect,
          connection_string: data.connection_string || undefined,
        });
        if (res.success) {
          toast.success("Database connection updated successfully!");
          onSaved?.();
        } else {
          throw new Error(res.message || "Failed to update connection");
        }
      } else {
        const res = await connectionsApi.create(projectId, {
          name: data.name,
          dialect: data.dialect,
          connection_string: data.connection_string,
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
