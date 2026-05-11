import { expect, test } from "@playwright/test";

const workspaceId = "workspace-1";
const sessionId = "session-1";
const ignoredConsoleErrors = [
  "Failed to fetch RSC payload",
  "Falling back to browser navigation",
];

test.describe("UI regression (mocked APIs) @ui-regression", () => {
  test("signup, upload, grounded chat, lead capture, and analytics flow @ui-regression", async ({ page }) => {
    const consoleErrors: string[] = [];
    let documentListRequests = 0;
    let documents = [] as Array<{
      id: string;
      title: string;
      mime_type: string;
      file_size: number;
      ingestion_status: string;
      metadata_json: Record<string, unknown>;
      summary: string;
      chunk_count: number;
      created_at: string;
      updated_at: string;
    }>;
    let leads = [] as Array<{
      id: string;
      name: string | null;
      email: string | null;
      company: string | null;
      message: string | null;
      status: string;
      priority: string;
      tag: string;
      created_at: string;
      updated_at: string;
      chat_session_id: string | null;
      workspace_id: string;
      phone: string | null;
      use_case: string | null;
      source: string;
      high_intent: boolean;
      notes: string | null;
      metadata_json: Record<string, unknown> | null;
    }>;

    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });

    await page.route("**/api/v1/auth/signup", async (route) => {
      await page.context().addCookies([
        {
          name: "access_token",
          value: "mock-access-token",
          domain: "127.0.0.1",
          path: "/",
          httpOnly: true,
          sameSite: "Lax",
        },
        {
          name: "csrf_token",
          value: "mock-csrf-token",
          domain: "127.0.0.1",
          path: "/",
          sameSite: "Lax",
        },
      ]);
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

    await page.route(`**/api/v1/workspaces/${workspaceId}/documents`, async (route) => {
      if (route.request().method() === "GET") {
        documentListRequests += 1;
        const payload =
          documents.length === 1 &&
          documents[0].ingestion_status === "processing" &&
          documentListRequests >= 3
            ? documents.map((document) => ({
                ...document,
                ingestion_status: "indexed",
                updated_at: "2026-01-01T00:00:05Z",
              }))
            : documents;

        if (payload !== documents) {
          documents = payload;
        }
        await route.fulfill({ json: payload });
        return;
      }

      documents = [
        {
          id: "doc-1",
          title: "quarterly.txt",
          mime_type: "text/plain",
          file_size: 128,
          ingestion_status: "processing",
          metadata_json: { page_count: 1 },
          summary: "Revenue grew and onboarding improved.",
          chunk_count: 2,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ];
      documentListRequests = 0;
      await route.fulfill({ status: 201, json: { message: "uploaded", document: documents[0] } });
    });

    await page.route(`**/api/v1/workspaces/${workspaceId}/documents/doc-1/reindex`, async (route) => {
    documents = documents.map((document) => ({ ...document, ingestion_status: "pending" }));
    await route.fulfill({ json: { message: "reindexed", document: documents[0] } });
    });

    await page.route("**/api/v1/settings?workspace_id=*", async (route) => {
      await route.fulfill({
        json: {
          workspace_id: workspaceId,
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
          prompt: {
            custom_system_prompt: null,
            company_instructions: null,
            business_rules: null,
          },
          lead_capture: {
            enabled: true,
            force_before_chat: false,
            trigger_on_first_message: true,
            trigger_on_low_confidence: true,
            trigger_after_n_messages: 1,
            required_fields: ["name", "email"],
            custom_form_message: null,
            auto_response_message: "Thanks, we'll follow up.",
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
          widget: {
            position: "right",
            size: "comfortable",
            theme: "dark",
            welcome_popup_message: "Ask grounded questions.",
            launcher_icon: null,
            show_branding: true,
            delay_before_appearance_seconds: 0,
            allowed_origins: ["http://127.0.0.1:3001"],
          },
          access_control: {
            restrict_to_logged_in_users: false,
            chatbot_mode: "public",
            allow_guest_access: true,
            rate_limit_per_user_per_minute: 30,
          },
          knowledge_base: {
            disabled_document_ids: [],
            disabled_urls: [],
            prioritized_document_ids: [],
            prioritized_urls: [],
            chunk_relevance_threshold: 0.45,
          },
          analytics: {
            tracking_enabled: true,
            feedback_collection_enabled: true,
            anonymize_user_data: false,
          },
          notifications: {
            enabled: true,
            notification_types: ["lead_capture"],
            email_recipients: [],
            webhook_endpoints: [],
            retry_attempts: 3,
            triggers: {},
            template_overrides: {},
          },
          updated_at: "2026-01-01T00:00:00Z",
        },
      });
    });

    await page.route("**/api/v1/settings/public?workspace_id=*", async (route) => {
      await route.fulfill({
        json: {
          workspace_id: workspaceId,
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
          lead_capture: {
            enabled: true,
            force_before_chat: false,
            trigger_on_first_message: true,
            trigger_on_low_confidence: true,
            trigger_after_n_messages: 1,
            required_fields: ["name", "email"],
            custom_form_message: null,
            auto_response_message: "Thanks, we'll follow up.",
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
          widget: {
            position: "right",
            size: "comfortable",
            theme: "dark",
            welcome_popup_message: "Ask grounded questions.",
            launcher_icon: null,
            show_branding: true,
            delay_before_appearance_seconds: 0,
            allowed_origins: ["http://127.0.0.1:3001"],
          },
          access_control: {
            restrict_to_logged_in_users: false,
            chatbot_mode: "public",
            allow_guest_access: true,
            rate_limit_per_user_per_minute: 30,
          },
          analytics: {
            tracking_enabled: true,
            feedback_collection_enabled: true,
            anonymize_user_data: false,
          },
          embed: {
            auth_token: "public-preview-token",
            auth_expires_at: "2026-12-31T23:59:59Z",
            api_base_url: "http://127.0.0.1:3001",
            script_url: "http://127.0.0.1:3001/widget-dist/widget.js",
            version: "1.0.0",
            allowed_origins: ["http://127.0.0.1:3001"],
          },
        },
      });
    });

    await page.route(`**/api/v1/workspaces/${workspaceId}/members`, async (route) => {
      await route.fulfill({
        json: [
          {
            id: "member-1",
            user_id: "user-1",
            full_name: "QA User",
            email: "qa@example.com",
            role: "admin",
          },
        ],
      });
    });

    await page.route("**/api/v1/meeting-types/list?workspace_id=*", async (route) => {
      await route.fulfill({
        json: {
          items: [
            {
              id: "meeting-type-1",
              workspace_id: workspaceId,
              title: "Sales demo",
              description: "Talk through pricing and deployment fit.",
              duration_minutes: 30,
              location_type: "video",
              assigned_user_id: "user-1",
              availability_mode: "default",
              is_active: true,
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-01T00:00:00Z",
            },
          ],
          total: 1,
        },
      });
    });

    await page.route("**/widget-dist/widget.js", async (route) => {
      await route.fulfill({
        contentType: "application/javascript",
        body: `
          (function () {
            var host = document.createElement("advanced-rag-widget");
            var root = host.attachShadow({ mode: "open" });
            var launcher = document.createElement("button");
            launcher.className = "abrag-launcher";
            launcher.type = "button";
            launcher.textContent = "Open widget";
            root.appendChild(launcher);
            document.body.appendChild(host);
          })();
        `,
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

    await page.route("**/api/v1/chat/message", async (route) => {
    await route.fulfill({
      contentType: "text/event-stream",
      body: [
        `event: start\ndata: {"session_id":"${sessionId}","generation_id":"gen-1","message_id":"msg-1"}`,
        `event: token\ndata: {"delta":"Revenue "}`,
        `event: token\ndata: {"delta":"grew 18 percent."}`,
        `event: complete\ndata: {"answer":"Revenue grew 18 percent.","citations":[{"file_name":"quarterly.txt","page_number":1,"url":null,"chunk_preview":"Revenue grew 18 percent year over year."}],"confidence":"High","metadata":{"retrieved_chunks":2,"processing_time":14,"stopped":false,"message_id":"msg-1","generation_id":"gen-1","lead_capture":{"should_prompt":true,"trigger":"after_n_messages","message":"Share your details for follow-up.","schedule_call_enabled":true,"high_intent":true}}}`,
      ].join("\n\n"),
    });
    });

    await page.route("**/api/v1/leads/capture", async (route) => {
    leads = [
      {
        id: "lead-1",
        workspace_id: workspaceId,
        chat_session_id: sessionId,
        name: "Taylor Morgan",
        email: "taylor@example.com",
        phone: null,
        company: "Northwind",
        use_case: "sales",
        message: "Need pricing details",
        source: "chatbot",
        status: "new",
        priority: "high",
        tag: "sales",
        high_intent: true,
        notes: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        metadata_json: null,
      },
    ];
    await route.fulfill({ json: { message: "Lead captured", lead: leads[0] } });
    });

    await page.route("**/api/v1/leads?workspace_id=*", async (route) => {
    await route.fulfill({ json: { items: leads, total: leads.length } });
    });

    await page.route("**/api/v1/leads/lead-1?workspace_id=*", async (route) => {
    await route.fulfill({
      json: {
        lead: leads[0],
        conversation: [{ id: "msg-1", role: "assistant", content: "Revenue grew 18 percent.", created_at: "2026-01-01T00:00:00Z" }],
      },
    });
    });

    await page.route("**/api/v1/analytics/overview?workspace_id=*", async (route) => {
    await route.fulfill({
      json: {
        generated_at: "2026-01-01T00:00:00Z",
        filters: { workspace_id: workspaceId, date_from: null, date_to: null, user_id: null, document_id: null, source: null },
        metrics: {
          total_chats: 1,
          total_users: 1,
          total_messages: 2,
          total_documents: documents.length,
          total_website_sources: 0,
          total_leads: leads.length,
          conversion_rate: 0,
          average_response_time_ms: 120,
          average_confidence_score: 0.88,
        },
        metric_cards: [{ label: "Total chats", value: 1, display_value: "1", hint: "Chat sessions in range" }],
        daily_chat_volume: [],
        daily_lead_volume: [],
        source_distribution: [],
        confidence_distribution: [],
        top_knowledge_sources: [],
        alerts: [],
        insights: [],
      },
    });
    });

    await page.goto("/signup");
    await page.getByLabel("Full name").fill("QA User");
    await page.getByLabel("Workspace name").fill("Alpha Workspace");
    await page.getByLabel("Email").fill("qa@example.com");
    await page.getByLabel("Password").fill("CorrectHorseBatteryStaple!");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.goto("/dashboard/documents");
    await page.locator('input[type="file"]').setInputFiles({
      name: "quarterly.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Revenue grew 18 percent year over year."),
    });
    const uploadedDocumentCard = page.locator("article").filter({ hasText: "quarterly.txt" });
    await expect(uploadedDocumentCard).toBeVisible();
    await expect(uploadedDocumentCard.getByText("processing")).toBeVisible();
    await expect(uploadedDocumentCard.getByText("indexed")).toBeVisible({ timeout: 10000 });

    await page.goto("/dashboard/chat");
    await page.getByLabel("Chat message input").fill("How did revenue change?");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.getByText("Revenue grew 18 percent.")).toBeVisible();
    await expect(page.getByText("quarterly.txt")).toBeVisible();
    await page.getByRole("button", { name: "Share details" }).click();
    await expect(page.getByRole("heading", { name: "Talk to a human expert" })).toBeVisible();
    await page.getByPlaceholder("Name *").fill("Taylor Morgan");
    await page.getByPlaceholder("Email *").fill("taylor@example.com");
    await page.getByRole("button", { name: "Submit details" }).click();

    await page.goto("/dashboard/leads");
    await expect(page.getByRole("heading", { name: "Taylor Morgan" }).last()).toBeVisible();

    await page.goto("/dashboard/analytics");
    await expect(page.getByRole("heading", { name: "Analytics and Insights" })).toBeVisible();
    await expect(page.getByText("Total chats")).toBeVisible();
    await expect(page.getByText("Chat sessions in range")).toBeVisible();

    await page.goto("/dashboard/widget-preview");
    await expect(page.getByRole("heading", { name: "Live widget preview" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workspace-scoped script" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Production widget renderer" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Copy embed script" })).toBeEnabled();
    await expect(page.getByTitle("Live widget preview")).toBeVisible();
    await expect(page.getByText("http://127.0.0.1:3001/widget-dist/widget.js", { exact: true })).toBeVisible();
    await expect(page.frameLocator('iframe[title="Live widget preview"]').getByText("Live widget mount")).toBeVisible();
    await expect(page.getByText("Ready")).toBeVisible({ timeout: 15000 });
    expect(
      consoleErrors.filter(
        (message) => !ignoredConsoleErrors.some((knownMessage) => message.includes(knownMessage)),
      ),
    ).toEqual([]);
  });
});
