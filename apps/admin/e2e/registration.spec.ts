import { test, expect } from "@playwright/test";

test("public registration validates passwords and explains email confirmation", async ({
  page,
}) => {
  await page.route("**/v1/registration", (route) =>
    route.fulfill({ json: { enabled: true } }),
  );
  await page.route("**/v1/registrations", (route) =>
    route.fulfill({ status: 202, json: { status: "check_email" } }),
  );
  await page.goto("/");
  await page
    .getByRole("button", { name: "New here? Create a free account" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Create your workspace" }),
  ).toBeVisible();
  await page.getByLabel("Workspace name", { exact: true }).fill("New business");
  await page.getByLabel("Email", { exact: true }).fill("new@example.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-long-password");
  await page
    .getByLabel("Confirm password", { exact: true })
    .fill("different-password-value");
  await expect(
    page.getByRole("button", { name: "Create account" }),
  ).toBeDisabled();
  await page
    .getByLabel("Confirm password", { exact: true })
    .fill("synthetic-long-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("status")).toContainText("Check your inbox");
  await expect(
    page.getByRole("heading", { name: "Sign in to Studio" }),
  ).toBeVisible();
  await expect(page.getByLabel("Password", { exact: true })).toHaveValue("");
});

test("closed signup does not offer account creation", async ({ page }) => {
  await page.route("**/v1/registration", (route) =>
    route.fulfill({ json: { enabled: false } }),
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Sign in to Studio" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "New here? Create a free account" }),
  ).toHaveCount(0);
});
