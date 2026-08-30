"use client";

import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { FolderPlus, Loader2, Plus } from "lucide-react";

import { projectsApi } from "@/lib/api/projects";
import { projectSchema, type ProjectFormData } from "@/lib/validations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface CreateProjectDialogProps {
  onSuccess?: () => void;
  trigger?: React.ReactNode;
}

export function CreateProjectDialog({
  onSuccess,
  trigger,
}: CreateProjectDialogProps): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ProjectFormData>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: "",
      description: "",
    },
  });

  const onSubmit = async (data: ProjectFormData) => {
    setIsSubmitting(true);
    try {
      const response = await projectsApi.create({
        name: data.name,
        description: data.description || null,
      });

      if (response.success) {
        toast.success("Project created successfully!");
        reset();
        setOpen(false);
        onSuccess?.();
      } else {
        throw new Error(response.message || "Failed to create project");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create project";
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button className="bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/20">
            <Plus className="mr-1.5 h-4 w-4" />
            New Project
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <FolderPlus className="h-5 w-5" />
            </div>
            <DialogTitle>Create New Project</DialogTitle>
          </div>
          <DialogDescription>
            Create an isolated workspace for a new database connection and chat session.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="project-name">Project Name</Label>
            <Input
              id="project-name"
              placeholder="e.g. E-Commerce Analytics, Stripe DB"
              disabled={isSubmitting}
              {...register("name")}
            />
            {errors.name && (
              <p className="text-xs text-red-400">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="project-description">Description (Optional)</Label>
            <Input
              id="project-description"
              placeholder="Brief summary of what this database stores"
              disabled={isSubmitting}
              {...register("description")}
            />
            {errors.description && (
              <p className="text-xs text-red-400">{errors.description.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={isSubmitting}
              className="text-zinc-400 hover:text-white"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="bg-blue-600 hover:bg-blue-500 text-white"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create Project"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
