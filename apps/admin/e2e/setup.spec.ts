import { test, expect } from "@playwright/test";

test("setup guide links to real configuration and unsaved edits cannot be published", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("owner@cedar.example");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-e2e-password");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("button", { name: "Setup guide", exact: true }).click();
  await expect(
    page
      .getByRole("list", { name: "Assistant setup steps" })
      .getByRole("listitem"),
  ).toHaveCount(4);
  await page.getByRole("button", { name: "Personalise assistant" }).click();
  await expect(
    page.getByRole("heading", { name: "Connect your AI service" }),
  ).toBeVisible();
  const name = page.getByLabel("Name", { exact: true });
  const originalName = await name.inputValue();
  await name.fill("Updated draft name");
  await expect(
    page.getByText(
      "You have unsaved changes. Save your draft before publishing or leaving this page.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Publish saved draft", exact: true }),
  ).toBeDisabled();
  await name.fill(originalName);
  await page.getByRole("button", { name: "Setup guide", exact: true }).click();
  await page
    .getByRole("button", { name: "Add knowledge", exact: true })
    .click();
  await expect(
    page.getByLabel("Upload source", { exact: true }),
  ).toBeAttached();
  await page.getByRole("button", { name: "Setup guide", exact: true }).click();
  await page
    .getByRole("button", { name: "Test assistant", exact: false })
    .click();
  await expect(
    page.getByRole("heading", { name: "Chat", exact: true }),
  ).toBeVisible();
});
