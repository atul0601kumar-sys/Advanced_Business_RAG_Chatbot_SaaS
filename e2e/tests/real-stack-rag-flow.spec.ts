import path from "node:path";

import { expect, test } from "@playwright/test";

test.describe("Real stack @real-stack", () => {
  test.skip(
    process.env.PLAYWRIGHT_REAL_STACK !== "1",
    "Set PLAYWRIGHT_REAL_STACK=1 to run against the live backend and infrastructure stack.",
  );

  test("signup, login, index a live TXT document, answer with citation, and surface a lead in dashboard @real-stack", async ({
    page,
  }) => {
    test.setTimeout(240_000);

    const uniqueSuffix = Date.now();
    const accountName = "Real Stack QA";
    const workspaceName = `Real Stack Workspace ${uniqueSuffix}`;
    const email = `real-stack-${uniqueSuffix}@example.com`;
    const password = "CorrectHorseBatteryStaple!";
    const leadName = "Jordan Pipeline";
    const leadEmail = `lead-${uniqueSuffix}@example.com`;
    const documentFileName = "real-stack-knowledge-base.txt";
    const documentPath = path.resolve(process.cwd(), "e2e/fixtures/real-stack-knowledge-base.txt");

    await page.goto("/signup");
    await page.getByLabel("Full name").fill(accountName);
    await page.getByLabel("Workspace name").fill(workspaceName);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Create account" }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByText(workspaceName)).toBeVisible();

    await page.getByRole("button", { name: "Logout" }).click();
    await expect(page).toHaveURL(/\/login$/);

    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.goto("/dashboard/documents");
    await page.locator('input[type="file"]').setInputFiles(documentPath);
    await expect(page.getByText(documentFileName)).toBeVisible();
    await expect(
      page
        .locator("article")
        .filter({ hasText: documentFileName })
        .getByText("indexed"),
    ).toBeVisible({ timeout: 120_000 });

    await page.goto("/dashboard/chat");
    await page.getByLabel("Chat message input").fill(
      "Who owns Project Atlas and what budget is assigned to it?",
    );
    await page.getByRole("button", { name: "Send message" }).click();

    await expect(page.getByText(/Priya Raman/i)).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText(documentFileName)).toBeVisible({ timeout: 120_000 });

    await page.getByRole("button", { name: "Talk to human" }).click();
    await expect(
      page.getByRole("heading", { name: "Talk to a human expert" }),
    ).toBeVisible();
    await page.getByPlaceholder("Name *").fill(leadName);
    await page.getByPlaceholder("Email *").fill(leadEmail);
    await page.getByPlaceholder("Company").fill("Northwind Revenue");
    await page.getByPlaceholder("Tell us what you need").fill(
      "Need pricing and rollout support for the Atlas deployment.",
    );
    await page.getByRole("button", { name: "Submit details" }).click();

    await page.goto("/dashboard/leads");
    await expect(page.getByRole("heading", { name: leadName })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByText(leadEmail)).toBeVisible();
  });
});
