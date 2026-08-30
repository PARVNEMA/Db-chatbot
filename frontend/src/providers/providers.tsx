"use client";

import React from "react";
import { AuthProvider } from "./auth-provider";
import { Toaster } from "sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      {children}
      <Toaster richColors position="top-right" theme="dark" closeButton />
    </AuthProvider>
  );
}
