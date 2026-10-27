import { test, expect } from "@playwright/test";

test("knowledge and booking journey uses real local services", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("owner@cedar.example");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-e2e-password");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Knowledge", exact: true }).click();
  await page.getByLabel("Upload source").setInputFiles({
    name: "cedar-faq.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "Cedar bicycle service hours are 09:00 to 17:00 on weekdays.",
    ),
  });
  await expect(page.getByText("ready", { exact: true })).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole("button", { name: "Chat", exact: true }).click();
  await page
    .getByLabel("Message", { exact: true })
    .fill("What are the bicycle service hours?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator(".message.assistant")).toContainText("09:00");
  await page.getByRole("button", { name: "[1] cedar-faq.txt" }).click();
  await expect(page.locator(".chat-side .passage")).toContainText("09:00");
  await page.getByRole("button", { name: "Appointments", exact: true }).click();
  const select = page.getByLabel("Service", { exact: true });
  await select.selectOption({ index: 1 });
  await page.locator(".slots button").first().click();
  await expect(page.locator(".receipt")).toContainText("awaiting confirmation");
  await page
    .getByRole("button", { name: "Confirm appointment", exact: true })
    .click();
  await expect(page.locator(".receipt")).toContainText("succeeded");
  await expect(page.locator(".booking-row")).toHaveCount(1);
  await page
    .locator(".booking-row")
    .getByRole("button", { name: "Cancel", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm cancellation", exact: true })
    .click();
  await expect(page.locator(".booking-row")).toContainText("cancelled");
  await page.getByRole("button", { name: "Knowledge", exact: true }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(
    page.getByText("Your assistant is ready to learn"),
  ).toBeVisible();
});

test("iframe widget can authenticate and reach real chat", async ({
  page,
  request,
}) => {
  const login = await request.post("/v1/sessions", {
    data: { email: "owner@cedar.example", password: "synthetic-e2e-password" },
  });
  const { access_token } = await login.json();
  const headers = { Authorization: `Bearer ${access_token}` };
  const projects = await (
    await request.get("/v1/projects", { headers })
  ).json();
  const bots = await (
    await request.get(`/v1/projects/${projects.items[0].id}/assistants`, {
      headers,
    })
  ).json();
  await page.goto("/demo-embed.html");
  await page.getByLabel("Assistant ID").fill(bots.items[0].id);
  await page.getByRole("button", { name: "Load widget" }).click();
  await page.getByRole("button", { name: "Chat with us" }).click();
  const frame = page.frameLocator('iframe[title="Business assistant"]');
  await frame.getByLabel("Email", { exact: true }).fill("owner@cedar.example");
  await frame
    .getByLabel("Password", { exact: true })
    .fill("synthetic-e2e-password");
  await frame.getByRole("button", { name: "Open workspace" }).click();
  await expect(
    frame.getByRole("heading", { name: "What would you like to know?" }),
  ).toBeVisible();
  await frame
    .getByLabel("Message", { exact: true })
    .fill("interstellar photosynthesis");
  await frame.getByRole("button", { name: "Send message" }).click();
  await expect(frame.locator(".message.assistant")).toContainText(
    "enough information",
  );
});
