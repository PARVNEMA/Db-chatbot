"use client";

import React from "react";
import { Select } from "@/components/ui/select";
import { Server } from "lucide-react";
import { SUPPORTED_DIALECTS } from "@/lib/constants";

interface DialectSelectProps {
  value: string;
  onValueChange: (value: string) => void;
  disabled?: boolean;
}

export function DialectSelect({
  value,
  onValueChange,
  disabled,
}: DialectSelectProps): React.JSX.Element {
  const options = SUPPORTED_DIALECTS.map((dialect) => ({
    value: dialect.value,
    label: dialect.label,
    description: dialect.defaultPort
      ? `Standard Port: ${dialect.defaultPort}`
      : "File-based database",
    icon: <Server className="h-4 w-4 text-blue-400 shrink-0" />,
  }));

  return (
    <Select
      value={value}
      onValueChange={onValueChange}
      options={options}
      placeholder="Select database dialect"
      disabled={disabled}
    />
  );
}

export const DIALECT_TEMPLATES: Record<string, string> = {
  postgresql: "postgresql://username:password@localhost:5432/my_database",
  mysql: "mysql+pymysql://username:password@localhost:3306/my_database",
  mssql: "mssql+pyodbc://username:password@localhost:1433/my_database?driver=ODBC+Driver+18+for+SQL+Server",
  snowflake: "snowflake://username:password@account_identifier/my_database/my_schema?warehouse=COMPUTE_WH",
  sqlite: "sqlite:///path/to/my_database.db",
};
