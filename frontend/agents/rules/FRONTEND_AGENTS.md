# AI Agent Guidelines & Coding Standards for Frontend

This document establishes mandatory coding standards, architectural rules, and behavior guidelines for all AI agents working on the frontend codebase.

---

## 1. Tech Stack — Non-Negotiable Choices

| Concern | Choice | Notes |
| :--- | :--- | :--- |
| **Framework** | Next.js 16 (App Router) | Use `app/` directory routing. No Pages Router. |
| **Language** | TypeScript 5 (strict mode) | 100% type coverage. No `any` except unavoidable library gaps. |
| **UI Library** | React 19 | Use Server Components by default; `"use client"` only where needed. |
| **Component Kit** | Shadcn UI (`base-nova` style) + Base UI React | Install via `npx shadcn@latest add <component>`. Never hand-roll primitives that Shadcn provides. |
| **Styling** | Tailwind CSS v4 | Use `@theme inline` design tokens in `globals.css`. Never use inline `style={}` unless dynamically computed. |
| **Icons** | Lucide React | `import { IconName } from "lucide-react"`. No other icon libraries. |
| **HTTP Client** | Axios | Centralized instance at `@/lib/api/client.ts`. Never use raw `fetch()` for API calls (except SSE streams). |
| **Forms** | React Hook Form + Zod | `useForm<T>()` with `zodResolver`. Never use uncontrolled forms or manual validation. |
| **State** | React Context + `useReducer` for auth/global; Local `useState` for component state | No external state library (Redux, Zustand) unless explicitly approved. |
| **Notifications** | Sonner (toast) via Shadcn | `import { toast } from "sonner"`. |
| **SSE** | Native `fetch()` + `ReadableStream` | For streaming endpoints (chat, embeddings). Do NOT use EventSource for POST requests. |

---

## 2. Component-Based Architecture

### 2.1 Directory Structure

```
frontend/src/
├── app/                          # Next.js App Router pages & layouts
│   ├── (auth)/                   # Auth route group (login, register) — no sidebar
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── (dashboard)/              # Authenticated route group — with sidebar
│   │   ├── layout.tsx            # Dashboard shell (sidebar + header + main)
│   │   ├── projects/
│   │   │   ├── page.tsx          # Project list
│   │   │   └── [projectId]/
│   │   │       ├── layout.tsx    # Project-scoped layout
│   │   │       ├── page.tsx      # Project overview
│   │   │       ├── connection/page.tsx
│   │   │       ├── schema/page.tsx
│   │   │       └── chat/
│   │   │           ├── page.tsx  # Chat sessions list / new chat
│   │   │           └── [sessionId]/page.tsx
│   │   └── settings/page.tsx
│   ├── layout.tsx                # Root layout (fonts, providers)
│   ├── globals.css
│   └── page.tsx                  # Landing / redirect
│
├── components/                   # Reusable components
│   ├── ui/                       # Shadcn primitives (auto-generated)
│   ├── common/                   # App-wide reusable components
│   │   ├── app-sidebar.tsx
│   │   ├── header.tsx
│   │   ├── loading-spinner.tsx
│   │   ├── empty-state.tsx
│   │   ├── error-boundary.tsx
│   │   ├── confirm-dialog.tsx
│   │   └── page-header.tsx
│   ├── auth/                     # Auth-specific components
│   │   ├── login-form.tsx
│   │   ├── register-form.tsx
│   │   └── auth-guard.tsx
│   ├── projects/                 # Project domain components
│   │   ├── project-card.tsx
│   │   ├── project-list.tsx
│   │   └── create-project-dialog.tsx
│   ├── connections/              # Connection domain components
│   │   ├── connection-form.tsx
│   │   ├── connection-status.tsx
│   │   └── dialect-select.tsx
│   ├── schema/                   # Schema explorer components
│   │   ├── schema-overview.tsx
│   │   ├── table-list.tsx
│   │   ├── column-table.tsx
│   │   ├── annotation-editor.tsx
│   │   └── schema-search.tsx
│   └── chat/                     # Chat domain components
│       ├── chat-input.tsx
│       ├── message-list.tsx
│       ├── message-bubble.tsx
│       ├── query-result-table.tsx
│       ├── sql-viewer.tsx
│       ├── session-sidebar.tsx
│       └── sse-status-indicator.tsx
│
├── lib/                          # Utilities, API client, shared logic
│   ├── api/                      # API layer
│   │   ├── client.ts             # Axios instance with interceptors
│   │   ├── auth.ts               # Auth API functions
│   │   ├── projects.ts           # Projects API functions
│   │   ├── connections.ts        # Connections API functions
│   │   ├── schema.ts             # Schema introspection API functions
│   │   ├── annotations.ts        # Semantic layer API functions
│   │   ├── embeddings.ts         # Embeddings API functions
│   │   └── chat.ts               # Chat API functions
│   ├── utils.ts                  # cn() helper
│   ├── constants.ts              # App-wide constants
│   └── validations.ts            # Shared Zod schemas
│
├── hooks/                        # Custom React hooks
│   ├── use-auth.ts
│   ├── use-project.ts
│   ├── use-sse.ts
│   └── use-debounce.ts
│
├── providers/                    # React Context providers
│   ├── auth-provider.tsx
│   ├── project-provider.tsx
│   └── providers.tsx             # Compose all providers
│
└── types/                        # Shared TypeScript types
    ├── api.ts                    # ApiResponse<T>, PaginatedData<T> envelope types
    ├── auth.ts                   # User, Token types
    ├── project.ts                # Project types
    ├── connection.ts             # Connection types
    ├── schema.ts                 # Schema, Table, Column types
    ├── annotation.ts             # Annotation types
    ├── embedding.ts              # Embedding, search result types
    └── chat.ts                   # ChatSession, ChatMessage, QueryRun types
```

### 2.2 Component Classification

| Category | Location | Rules |
| :--- | :--- | :--- |
| **Shadcn Primitives** | `components/ui/` | Auto-generated by CLI. Never modify directly. Customize via `className` prop or wrapper. |
| **Domain Components** | `components/<domain>/` | Feature-specific. May import from `ui/` and `common/`. Never import from another domain's components. |
| **Common Components** | `components/common/` | App-wide reusable. Must not contain domain-specific logic. |
| **Page Components** | `app/**/page.tsx` | Thin orchestrators. Compose domain components. Minimal logic. |
| **Layout Components** | `app/**/layout.tsx` | Shell structure. Handle auth guards, navigation, providers. |

### 2.3 Component Design Rules

1. **Single Responsibility**: Each component does one thing. If a component file exceeds ~150 lines, it should be split.
2. **Props over Internal State**: Prefer controlled components. Parent owns state; child receives via props.
3. **Composition over Configuration**: Use `children`, slots, and render props instead of deeply nested prop objects.
4. **Named Exports Only**: `export function ComponentName()` — never `export default`. Exception: Next.js pages/layouts which require default export.
5. **Co-locate Styles**: Use Tailwind classes directly in JSX. No CSS modules. No styled-components.
6. **Loading/Error/Empty States**: Every component that fetches data must handle all three states explicitly:
   ```tsx
   if (isLoading) return <Skeleton />;
   if (error) return <ErrorState message={error.message} />;
   if (data.length === 0) return <EmptyState />;
   return <DataView data={data} />;
   ```

---

## 3. API Integration Layer

### 3.1 Centralized Axios Client (`@/lib/api/client.ts`)

```typescript
// MANDATORY PATTERN — all API calls go through this instance
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  headers: { "Content-Type": "application/json" },
});

// Request interceptor: attach JWT
apiClient.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: unwrap ApiResponse envelope
apiClient.interceptors.response.use(
  (response) => response.data, // Returns the full ApiResponse<T>
  (error) => {
    // Handle 401 → redirect to login
    // Handle error envelope → throw structured error
  }
);
```

### 3.2 API Function Pattern

Every API domain file follows this exact pattern:

```typescript
// @/lib/api/projects.ts
import { apiClient } from "./client";
import type { ApiResponse, PaginatedData } from "@/types/api";
import type { Project, ProjectCreate, ProjectUpdate } from "@/types/project";

export const projectsApi = {
  create: (data: ProjectCreate) =>
    apiClient.post<never, ApiResponse<Project>>("/projects", data),

  list: (params?: { skip?: number; limit?: number }) =>
    apiClient.get<never, ApiResponse<PaginatedData<Project>>>("/projects", { params }),

  get: (projectId: string) =>
    apiClient.get<never, ApiResponse<Project>>(`/projects/${projectId}`),

  update: (projectId: string, data: ProjectUpdate) =>
    apiClient.patch<never, ApiResponse<Project>>(`/projects/${projectId}`, data),

  delete: (projectId: string) =>
    apiClient.delete<never, ApiResponse<null>>(`/projects/${projectId}`),
};
```

**Rules:**
- Group all functions for a domain in a single object export.
- Use the backend's exact `ApiResponse<T>` envelope type as the return type.
- Never hardcode API paths — derive from constants if needed.
- Never call `apiClient` directly from components — always go through the API layer.

### 3.3 Backend Response Envelope Types (`@/types/api.ts`)

```typescript
// MUST match backend's app.core.responses exactly
export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T | null;
  error: ErrorDetail | null;
}

export interface ErrorDetail {
  code: string;
  message: string;
  details: unknown | null;
}

export interface PaginatedData<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}
```

---

## 4. Authentication & Route Protection

### 4.1 Auth State Management

- JWT token stored in `localStorage` (key: `access_token`).
- `AuthProvider` context wraps the entire app.
- On mount, call `GET /api/v1/auth/check` to validate token and hydrate user state.
- On 401 response (interceptor), clear token and redirect to `/login`.

### 4.2 Route Guard Pattern

```tsx
// Use in (dashboard)/layout.tsx
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppSidebar />
      <main>{children}</main>
    </AuthGuard>
  );
}
```

- `AuthGuard` checks auth context. If not authenticated, redirects to `/login`.
- Auth pages (`/login`, `/register`) redirect to `/projects` if already authenticated.

---

## 5. SSE (Server-Sent Events) Handling

### 5.1 SSE Hook Pattern (`@/hooks/use-sse.ts`)

For streaming endpoints (chat messages, embedding generation):

```typescript
export function useSSE<T>(url: string, options: SSEOptions) {
  // 1. Use fetch() with POST method and ReadableStream reader
  // 2. Parse "event:" and "data:" lines from the stream
  // 3. Return { events, isStreaming, error, abort }
  // 4. Clean up AbortController on unmount
}
```

**Rules:**
- Never use `EventSource` for POST-based SSE endpoints.
- Always attach the JWT Bearer token in the fetch headers.
- Always provide an abort mechanism for cleanup.
- Parse SSE events into typed objects matching backend event schemas.

---

## 6. TypeScript Standards

1. **No `any`**: Use `unknown` if the type is truly unknown, then narrow with type guards.
2. **Interface for Objects**: Use `interface` for data shapes. Use `type` only for unions, intersections, and utility types.
3. **Explicit Return Types**: All exported functions and hooks must declare return types.
4. **Discriminated Unions**: Use discriminated unions for variant states:
   ```typescript
   type AsyncState<T> =
     | { status: "idle" }
     | { status: "loading" }
     | { status: "success"; data: T }
     | { status: "error"; error: string };
   ```
5. **Path Aliases**: Always use `@/` prefix. Never use relative imports like `../../../`.

---

## 7. Naming Conventions

| Entity | Convention | Example |
| :--- | :--- | :--- |
| **Files** | `kebab-case.tsx` / `.ts` | `project-card.tsx`, `use-auth.ts` |
| **Components** | `PascalCase` | `ProjectCard`, `ChatInput` |
| **Hooks** | `camelCase` starting with `use` | `useAuth`, `useProject` |
| **Types/Interfaces** | `PascalCase` | `Project`, `ChatSession` |
| **API functions** | `camelCase` grouped in object | `projectsApi.create()` |
| **Constants** | `SCREAMING_SNAKE_CASE` | `API_BASE_URL`, `MAX_RETRIES` |
| **CSS variables** | `--kebab-case` | `--color-primary`, `--sidebar-width` |

---

## 8. Error Handling

1. **API Errors**: Catch in the API layer. Surface via toast notifications or inline error states.
2. **Component Errors**: Use React Error Boundaries for unexpected render errors.
3. **Form Errors**: Display inline field errors via React Hook Form + Zod validation.
4. **Never Swallow Errors**: No empty `catch {}` blocks. Always log or display.
5. **Structured Error Display**: Use the backend's `ErrorDetail` shape to show user-friendly messages:
   ```tsx
   if (!response.success) {
     toast.error(response.error?.message ?? response.message);
   }
   ```

---

## 9. Performance Rules

1. **Server Components by Default**: Only add `"use client"` when the component needs hooks, event handlers, or browser APIs.
2. **Dynamic Imports**: Use `next/dynamic` for heavy components (code editors, charts) with `{ ssr: false }`.
3. **Image Optimization**: Use `next/image` for all images. Never use raw `<img>` tags.
4. **Debounce Inputs**: Debounce search/filter inputs (300ms minimum) before triggering API calls.
5. **Pagination**: Always paginate list views. Never load unbounded datasets client-side.

---

## 10. Agent Behavior & Verification Rules

1. **Read Next.js 16 Docs First**: Before writing any Next.js code, consult `node_modules/next/dist/docs/` for breaking changes. Next.js 16 has different APIs than training data.
2. **Install Shadcn Components via CLI**: Run `npx shadcn@latest add <component>` — never copy-paste component code manually.
3. **Verify Before Declaring Completion**:
   - Run `npm run build` — must compile without errors.
   - Run `npm run lint` — must pass ESLint.
   - Visually verify in browser if UI changes are made.
4. **No Console Logs in Production Code**: Use `console.error` only for error boundaries. Remove all `console.log` before committing.
5. **Responsive Design**: All pages must work on desktop (1280px+) and tablet (768px+). Mobile is secondary but must not break.

---

## 11. Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | Backend API base URL | `http://localhost:8000/api/v1` |
| `NEXT_PUBLIC_APP_NAME` | Application display name | `NL-DB Query Platform` |

**Rules:**
- Client-accessible env vars **must** be prefixed with `NEXT_PUBLIC_`.
- Never store secrets in frontend env vars.
- Access via `process.env.NEXT_PUBLIC_*` — never hardcode URLs.
