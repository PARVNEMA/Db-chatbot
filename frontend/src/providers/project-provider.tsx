"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { projectsApi } from "@/lib/api/projects";
import { connectionsApi } from "@/lib/api/connections";
import { schemaApi } from "@/lib/api/schema";
import type { Project } from "@/types/project";
import type { Connection } from "@/types/connection";
import type { SchemaOverviewResponse } from "@/types/schema";

interface ProjectContextType {
  projectId: string;
  project: Project | null;
  connection: Connection | null;
  schemaOverview: SchemaOverviewResponse | null;
  isLoading: boolean;
  error: string | null;
  refreshProject: () => Promise<void>;
  refreshConnection: () => Promise<void>;
  refreshSchema: () => Promise<void>;
  refreshAll: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export function ProjectProvider({
  projectId,
  children,
}: {
  projectId: string;
  children: React.ReactNode;
}): React.JSX.Element {
  const [project, setProject] = useState<Project | null>(null);
  const [connection, setConnection] = useState<Connection | null>(null);
  const [schemaOverview, setSchemaOverview] =
    useState<SchemaOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refreshProject = useCallback(async () => {
    try {
      const res = await projectsApi.get(projectId);
      if (res.success && res.data) {
        setProject(res.data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load project");
    }
  }, [projectId]);

  const refreshConnection = useCallback(async () => {
    try {
      const res = await connectionsApi.get(projectId);
      if (res.success && res.data) {
        setConnection(res.data);
      } else {
        setConnection(null);
      }
    } catch {
      // 404 is normal if no connection is set up yet
      setConnection(null);
    }
  }, [projectId]);

  const refreshSchema = useCallback(async () => {
    try {
      const res = await schemaApi.getOverview(projectId);
      if (res.success && res.data) {
        setSchemaOverview(res.data);
      } else {
        setSchemaOverview(null);
      }
    } catch {
      setSchemaOverview(null);
    }
  }, [projectId]);

  const refreshAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await Promise.allSettled([
        refreshProject(),
        refreshConnection(),
        refreshSchema(),
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [refreshProject, refreshConnection, refreshSchema]);

  useEffect(() => {
    let isMounted = true;

    const init = async () => {
      setIsLoading(true);
      setError(null);
      try {
        await Promise.allSettled([
          refreshProject(),
          refreshConnection(),
          refreshSchema(),
        ]);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    void init();

    return () => {
      isMounted = false;
    };
  }, [refreshProject, refreshConnection, refreshSchema]);

  return (
    <ProjectContext.Provider
      value={{
        projectId,
        project,
        connection,
        schemaOverview,
        isLoading,
        error,
        refreshProject,
        refreshConnection,
        refreshSchema,
        refreshAll,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject(): ProjectContextType {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return context;
}
