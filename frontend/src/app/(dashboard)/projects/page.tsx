import { PageHeader } from "@/components/common/page-header";
import { ProjectList } from "@/components/projects/project-list";

export const metadata = {
  title: "Projects Workspace — AskMyDB",
  description: "Manage your database projects and query workspaces",
};

export default function ProjectsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Database Workspaces"
        description="Select an existing project or create a new one to connect your SQL database and start asking natural language queries."
      />
      <ProjectList />
    </div>
  );
}
