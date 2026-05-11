import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DashboardHome } from "@/components/dashboard/dashboard-home";

const { pushToast, apiRequest, fetchCurrentUser } = vi.hoisted(() => ({
  pushToast: vi.fn(),
  apiRequest: vi.fn(),
  fetchCurrentUser: vi.fn(),
}));

vi.mock("@/components/toast-provider", () => ({
  useToast: () => ({
    pushToast,
  }),
}));

vi.mock("@/lib/auth", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth")>("@/lib/auth");
  return {
    ...actual,
    apiRequest,
    fetchCurrentUser,
  };
});

test("renders dashboard data and matches snapshot output", async () => {
  const user = userEvent.setup();
  apiRequest.mockReset();
  fetchCurrentUser.mockReset();
  pushToast.mockReset();
  fetchCurrentUser.mockResolvedValueOnce({
    id: "user-1",
    full_name: "QA User",
    email: "qa@example.com",
    is_active: true,
    is_superuser: false,
    created_at: "2026-01-01T00:00:00Z",
    memberships: [{ workspace_id: "workspace-1", workspace_name: "Alpha Workspace", workspace_slug: "alpha", role: "admin" }],
  });
  apiRequest.mockResolvedValueOnce([
    { id: "workspace-1", name: "Alpha Workspace", role: "admin", status: "active" },
  ]);

  const { asFragment } = render(<DashboardHome />);

  await screen.findByText("Welcome back, QA User");
  await user.click(screen.getByRole("button", { name: /Import a new knowledge base/i }));
  expect(pushToast).toHaveBeenCalled();
  expect(asFragment()).toMatchSnapshot();
});

test("falls back to the dashboard error state on API failures", async () => {
  apiRequest.mockReset();
  fetchCurrentUser.mockReset();
  fetchCurrentUser.mockRejectedValueOnce(new Error("offline"));
  apiRequest.mockRejectedValueOnce(new Error("offline"));
  render(<DashboardHome />);
  await screen.findByText("Dashboard data is temporarily unavailable");
  expect(screen.getByRole("button", { name: "Retry dashboard" })).toBeInTheDocument();
});
