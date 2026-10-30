import { test, expect } from "@playwright/test";

test("database outage gives a clear login error without opening a workspace", async ({ page }) => {
  await page.route("**/v1/sessions", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "DATABASE_UNAVAILABLE" } }),
    }),
  );
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("owner@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-test-password");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "The workspace database is unavailable. Ask the administrator to check its connection settings.",
  );
  await expect(page.getByRole("button", { name: "Open workspace" })).toBeEnabled();
  await expect(page.getByRole("heading", { name: "Sign in to Studio" })).toBeVisible();
});
