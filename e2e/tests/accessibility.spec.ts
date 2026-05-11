import { expect, test } from "@playwright/test";

const workspaceId = "workspace-1";
const sessionId = "session-1";

test.describe("UI regression (mocked APIs) @ui-regression", () => {
  test("signup and chat surfaces support keyboard-first navigation and accessible labels @ui-regression", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];

    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });

    await page.route("**/api/v1/auth/signup", async (route) => {
      await route.fulfill({
        json: {
          expires_in: 900,
          user: {
            id: "user-1",
            email: "qa@example.com",
            full_name: "QA User",
            is_active: true,
            is_superuser: false,
            created_at: "2026-01-01T00:00:00Z",
            memberships: [{ workspace_id: workspaceId, workspace_name: "Alpha Workspace", workspace_slug: "alpha", role: "admin" }],
          },
        },
      });
    });

    await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      json: {
        id: "user-1",
        email: "qa@example.com",
        full_name: "QA User",
        memberships: [{ workspace_id: workspaceId, workspace_name: "Alpha Workspace", workspace_slug: "alpha", role: "admin" }],
      },
    });
    });

    await page.route("**/api/v1/workspaces", async (route) => {
    await route.fulfill({
      json: [{ id: workspaceId, name: "Alpha Workspace", slug: "alpha", description: "workspace", status: "active", role: "admin", created_at: "2026-01-01T00:00:00Z" }],
    });
    });

    await page.route("**/api/v1/settings?workspace_id=*", async (route) => {
    await route.fulfill({
      json: {
        identity: {
          bot_name: "Atlas",
          bot_avatar: null,
          brand_color_primary: "#0ea5e9",
          brand_color_secondary: "#0284c7",
          logo: null,
          tagline: "Revenue intelligence",
          welcome_message: "Ask grounded questions.",
        },
        behavior: {
          tone: "professional",
          response_style: "mixed",
          max_response_length: 600,
          markdown_enabled: true,
          citations_enabled: true,
          confidence_score_enabled: true,
        },
        handoff: {
          enabled: true,
          custom_message: "Talk to a human",
          enable_scheduling: true,
          escalate_on_low_confidence: true,
          escalate_on_repeated_failures: true,
        },
        voice: {
          voice_input_enabled: false,
          voice_output_enabled: false,
          voice_style: null,
          transcript_preview_enabled: true,
          auto_read_assistant_responses: false,
        },
      },
    });
    });

    await page.route("**/api/v1/leads/settings?workspace_id=*", async (route) => {
    await route.fulfill({
      json: {
        workspace_id: workspaceId,
        lead_capture_enabled: true,
        lead_capture_on_first_message: true,
        lead_capture_after_message_count: 1,
        lead_capture_on_low_confidence: true,
        force_lead_before_chat: false,
        required_fields: ["name", "email"],
        schedule_call_enabled: true,
        lead_notifications_enabled: false,
        admin_notification_email: null,
        notification_webhook_url: null,
        auto_response_message: "Thanks, we'll follow up.",
      },
    });
    });

    await page.route("**/api/v1/chat/sessions?workspace_id=*", async (route) => {
    await route.fulfill({
      json: [
        {
          id: sessionId,
          workspace_id: workspaceId,
          user_id: "user-1",
          title: "Quarterly Review",
          status: "active",
          channel: "web",
          started_at: "2026-01-01T00:00:00Z",
          last_message_at: "2026-01-01T00:00:00Z",
          session_summary: null,
          needs_human_review: false,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          message_count: 0,
        },
      ],
    });
    });

    await page.route(`**/api/v1/chat/history/${sessionId}`, async (route) => {
    await route.fulfill({
      json: {
        session: {
          id: sessionId,
          workspace_id: workspaceId,
          user_id: "user-1",
          title: "Quarterly Review",
          status: "active",
          channel: "web",
          started_at: "2026-01-01T00:00:00Z",
          last_message_at: "2026-01-01T00:00:00Z",
          session_summary: null,
          needs_human_review: false,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          message_count: 0,
        },
        messages: [],
      },
    });
    });

    await page.goto("/signup");
    await expect(page.getByRole("heading", { name: "Start your account" })).toBeVisible();
    await expect(page.getByLabel("Full name")).toBeVisible();
    await expect(page.getByLabel("Workspace name")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();

    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Full name")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Workspace name")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Email")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Password")).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Create account" })).toBeFocused();

    await page.goto("/dashboard/chat");
    await expect(page.getByLabel("Chat message input")).toBeVisible();
    await expect(page.getByRole("group", { name: "Answer mode" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Send message" })).toBeVisible();

    expect(consoleErrors).toEqual([]);
  });
});
