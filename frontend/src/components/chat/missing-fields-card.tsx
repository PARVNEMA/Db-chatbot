"use client";

import React, { useState } from "react";
import { AlertCircle, Send, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { MissingFieldItem } from "@/types/chat";

interface MissingFieldsCardProps {
  fields: MissingFieldItem[];
  onSubmit: (values: Record<string, unknown>) => void;
  onCancel?: () => void;
  disabled?: boolean;
}

export function MissingFieldsCard({
  fields,
  onSubmit,
  onCancel,
  disabled = false,
}: MissingFieldsCardProps): React.JSX.Element {
  const [formValues, setFormValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const f of fields) {
      initial[f.field_key] = "";
    }
    return initial;
  });

  const [validationError, setValidationError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (fieldKey: string, val: string) => {
    setFormValues((prev) => ({
      ...prev,
      [fieldKey]: val,
    }));
    if (validationError) setValidationError(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Validate that all fields have values
    const emptyField = fields.find((f) => !formValues[f.field_key]?.trim());
    if (emptyField) {
      setValidationError(
        `Please provide a value for '${emptyField.table}.${emptyField.column}'`
      );
      return;
    }

    setIsSubmitting(true);

    // Coerce values to numbers if needed
    const coerced: Record<string, unknown> = {};
    for (const f of fields) {
      const raw = formValues[f.field_key]?.trim();
      const dt = f.data_type.toLowerCase();
      if (
        dt.includes("int") ||
        dt.includes("serial") ||
        dt.includes("num") ||
        dt.includes("float") ||
        dt.includes("double")
      ) {
        const num = Number(raw);
        coerced[f.field_key] = isNaN(num) ? raw : num;
      } else if (dt.includes("bool")) {
        coerced[f.field_key] = raw.toLowerCase() === "true" || raw === "1";
      } else {
        coerced[f.field_key] = raw;
      }
    }

    onSubmit(coerced);
  };

  return (
    <div className="my-3 rounded-2xl border border-amber-500/30 bg-amber-950/20 p-4 shadow-lg animate-in fade-in-0 duration-200">
      <div className="flex items-start gap-3 pb-3 border-b border-amber-500/20">
        <div className="p-2 rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/30">
          <AlertCircle className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-amber-200">
              Required Information Needed
            </h4>
            <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-amber-500/20 text-amber-300 border border-amber-500/30">
              {fields.length} {fields.length === 1 ? "field" : "fields"} missing
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5 leading-relaxed">
            The target database requires non-nullable values for the following column(s) before staging this write operation.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="pt-3 space-y-3">
        <div className="space-y-2.5">
          {fields.map((field) => {
            const isNumeric =
              field.data_type.toLowerCase().includes("int") ||
              field.data_type.toLowerCase().includes("num") ||
              field.data_type.toLowerCase().includes("float");

            return (
              <div
                key={field.field_key}
                className="p-2.5 rounded-xl bg-zinc-900/80 border border-zinc-800 space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <Label
                    htmlFor={field.field_key}
                    className="text-xs font-mono text-zinc-200 flex items-center gap-1.5"
                  >
                    <span className="text-blue-400">{field.table}</span>
                    <span className="text-zinc-600">.</span>
                    <span className="text-amber-300 font-semibold">{field.column}</span>
                  </Label>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                    {field.data_type}
                  </span>
                </div>

                <Input
                  id={field.field_key}
                  type={isNumeric ? "number" : "text"}
                  value={formValues[field.field_key] || ""}
                  onChange={(e) => handleChange(field.field_key, e.target.value)}
                  placeholder={`Enter ${field.column} (${field.data_type})...`}
                  disabled={disabled || isSubmitting}
                  className="h-8 text-xs bg-zinc-950/80 border-zinc-800 text-zinc-100 placeholder:text-zinc-600 focus-visible:ring-amber-500/30 focus-visible:border-amber-500/50 font-sans"
                />

                {field.description && (
                  <p className="text-[10px] text-zinc-500 font-mono pl-0.5">
                    {field.description}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {validationError && (
          <p className="text-xs text-red-400 font-medium">{validationError}</p>
        )}

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-amber-500/10">
          {onCancel && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onCancel}
              disabled={disabled || isSubmitting}
              className="h-8 text-xs text-zinc-400 hover:text-zinc-200"
            >
              Cancel
            </Button>
          )}

          <Button
            type="submit"
            size="sm"
            disabled={disabled || isSubmitting}
            className="h-8 px-3.5 bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium gap-1.5 shadow-md shadow-amber-600/20"
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>Submit Values & Continue</span>
          </Button>
        </div>
      </form>
    </div>
  );
}
