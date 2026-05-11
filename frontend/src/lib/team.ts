import { apiRequest } from "@/lib/auth";

export type WorkspaceSummary = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  status: string;
  role: string;
  created_at: string;
};

export type WorkspaceMemberSummary = {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  role: "admin" | "team_member" | "viewer";
};

export async function fetchWorkspaceList(): Promise<WorkspaceSummary[]> {
  return apiRequest<WorkspaceSummary[]>("/api/v1/workspaces");
}

export async function fetchWorkspaceMembers(workspaceId: string): Promise<WorkspaceMemberSummary[]> {
  return apiRequest<WorkspaceMemberSummary[]>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members`,
  );
}

export async function addWorkspaceMember(
  workspaceId: string,
  payload: { email: string; role: WorkspaceMemberSummary["role"] },
): Promise<WorkspaceMemberSummary> {
  return apiRequest<WorkspaceMemberSummary>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members`,
    {
      method: "POST",
      json: payload,
    },
  );
}

export async function updateWorkspaceMemberRole(
  workspaceId: string,
  memberId: string,
  payload: { role: WorkspaceMemberSummary["role"] },
): Promise<WorkspaceMemberSummary> {
  return apiRequest<WorkspaceMemberSummary>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(memberId)}`,
    {
      method: "PATCH",
      json: payload,
    },
  );
}

export async function removeWorkspaceMember(
  workspaceId: string,
  memberId: string,
): Promise<{ message: string }> {
  return apiRequest<{ message: string }>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(memberId)}`,
    {
      method: "DELETE",
    },
  );
}
