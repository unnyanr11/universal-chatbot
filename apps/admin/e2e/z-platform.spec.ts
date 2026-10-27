import { test, expect, type Page } from "@playwright/test";
async function login(page: Page, email = "owner@cedar.example") {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-e2e-password");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
}

test("configuration publication and workflow dry run use persisted versions", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByLabel("Name", { exact: true })
    .fill("Cedar published assistant");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Publish saved draft" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Publish saved draft" }).click();
  await expect(page.getByText(/Published version 1/)).toBeVisible();
  await page.getByRole("button", { name: "Workflows", exact: true }).click();
  await page
    .getByRole("button", { name: "Save workflow", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Start dry run" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Start dry run" }).click();
  await expect(page.getByText("DRY RUN · SIMULATED WRITES")).toBeVisible();
  await page.getByLabel("Service", { exact: true }).selectOption({ index: 1 });
  await page
    .getByLabel("Available slot", { exact: true })
    .selectOption({ index: 1 });
  await page.getByRole("button", { name: "Continue workflow" }).click();
  await expect(
    page.getByRole("button", { name: "Confirm simulation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Confirm simulation" }).click();
  await expect(page.locator(".receipt .badge")).toHaveText("succeeded");
});

test("human handoff, private notes and workspace erasure remain separate", async ({
  page,
  browser,
}) => {
  await login(page);
  const customerContext = await browser.newContext();
  const customer = await customerContext.newPage();
  await login(customer, "customer@cedar.example");
  await customer.getByRole("button", { name: "Chat", exact: true }).click();
  await customer.getByRole("button", { name: "Request human support" }).click();
  await expect(customer.locator(".messages")).toContainText(
    "Automated replies are paused",
  );
  await page.getByRole("button", { name: "Support", exact: true }).click();
  await page
    .getByRole("button", { name: /Customer requested human support/ })
    .click();
  await page.getByRole("button", { name: "Claim conversation" }).click();
  await page.getByLabel("Reply or note").fill("PRIVATE_SYNTHETIC_AGENT_NOTE");
  await page.getByLabel("Internal note").check();
  await page.getByRole("button", { name: "Save private note" }).click();
  await expect(
    page.getByText("PRIVATE_SYNTHETIC_AGENT_NOTE", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Internal note").uncheck();
  await page
    .getByLabel("Reply or note")
    .fill("A human agent is ready to assist.");
  await page.getByRole("button", { name: "Send human reply" }).click();
  await customer.getByRole("button", { name: "Refresh replies" }).click();
  await expect(customer.locator(".messages")).toContainText(
    "A human agent is ready to assist.",
  );
  await expect(customer.locator(".messages")).not.toContainText(
    "PRIVATE_SYNTHETIC_AGENT_NOTE",
  );
  await page.getByRole("button", { name: "Return to assistant" }).click();
  await customer.getByRole("button", { name: "Privacy", exact: true }).click();
  await customer
    .getByLabel("Preference", { exact: true })
    .fill("Prefer concise answers");
  await customer.getByLabel("I consent").check();
  await customer.getByRole("button", { name: "Remember preference" }).click();
  await expect(
    customer.getByText("Prefer concise answers", { exact: true }),
  ).toBeVisible();
  await customer
    .getByLabel("Type DELETE MY WORKSPACE DATA to confirm")
    .fill("DELETE MY WORKSPACE DATA");
  await customer
    .getByRole("button", { name: "Delete my workspace data", exact: true })
    .click();
  await expect(
    customer.getByText("Prefer concise answers", { exact: true }),
  ).not.toBeVisible();
  await customerContext.close();
});
