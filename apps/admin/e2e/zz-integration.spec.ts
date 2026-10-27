import { test, expect } from "@playwright/test";

test("published guest widget, enquiries and isolated draft preview work end to end", async ({
  page,
  request,
  context,
}) => {
  const login = await request.post("/v1/sessions", {
    data: { email: "owner@cedar.example", password: "synthetic-e2e-password" },
  });
  const headers = {
    Authorization: `Bearer ${(await login.json()).access_token}`,
  };
  const projects = await (
    await request.get("/v1/projects", { headers })
  ).json();
  const project = projects.items[0].id;
  const created = await request.post(`/v1/projects/${project}/assistants`, {
    headers,
    data: {
      name: "Integration acceptance",
      welcome_message: "Ask about our warranty.",
    },
  });
  const assistant = (await created.json()).id;
  const root = `/v1/assistants/${assistant}`;
  const uploaded = await request.post(root + "/documents", {
    headers,
    multipart: {
      file: {
        name: "public-warranty.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("Warranty lasts twelve months."),
      },
    },
  });
  expect(uploaded.status()).toBe(202);
  await expect
    .poll(async () => {
      const data = await (
        await request.get(root + "/documents", { headers })
      ).json();
      return data.items[0]?.status;
    })
    .toBe("ready");
  const config = await (
    await request.get(root + "/configuration", { headers })
  ).json();
  const saved = await request.put(root + "/configuration", {
    headers,
    data: {
      revision: config.revision,
      configuration: {
        ...config.configuration,
        allowed_domains: ["127.0.0.1:8000"],
      },
    },
  });
  expect(
    (
      await request.post(root + "/publish", {
        headers,
        data: { revision: (await saved.json()).revision },
      })
    ).status(),
  ).toBe(200);
  expect(
    (
      await request.put(root + "/integration", {
        headers,
        data: {
          revision: 0,
          enabled: true,
          lead_capture: true,
          daily_limit: 100,
        },
      })
    ).status(),
  ).toBe(200);
  await page.goto("/demo-embed.html?public=1");
  await page.getByLabel("Assistant ID").fill(assistant);
  await page.getByRole("button", { name: "Load widget" }).click();
  await page.getByRole("button", { name: "Chat with us" }).click();
  const frame = page.frameLocator('iframe[title="Business assistant"]');
  await expect(
    frame.getByRole("heading", { name: "Integration acceptance" }),
  ).toBeVisible();
  await expect(frame.getByLabel("Email", { exact: true })).toHaveCount(0);
  await frame.getByLabel("Your question").fill("warranty");
  await frame.getByRole("button", { name: "Send message" }).click();
  await expect(frame.getByRole("log")).toContainText("twelve months");
  await frame.getByText("Leave an enquiry", { exact: true }).click();
  await frame.getByLabel("Name", { exact: true }).fill("Synthetic visitor");
  await frame.getByLabel("Email", { exact: true }).fill("visitor@example.test");
  await frame.getByLabel("Enquiry", { exact: true }).fill("Please contact me.");
  await frame.getByLabel(/I agree to share/).check();
  await frame.getByRole("button", { name: "Submit enquiry" }).click();
  await expect(frame.getByRole("status")).toContainText("enquiry was received");
  expect(
    (await (await request.get(root + "/leads", { headers })).json()).items[0]
      .name,
  ).toBe("Synthetic visitor");
  await request.post(root + "/documents", {
    headers,
    multipart: {
      file: {
        name: "draft-zephyr.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("Confidential zephyr draft policy."),
      },
    },
  });
  await expect
    .poll(async () => {
      const data = await (
        await request.get(root + "/documents", { headers })
      ).json();
      return data.items.every(
        (item: { status: string }) => item.status === "ready",
      );
    })
    .toBe(true);
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill("owner@cedar.example");
  await page
    .getByLabel("Password", { exact: true })
    .fill("synthetic-e2e-password");
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByLabel("Assistant", { exact: true }).selectOption(assistant);
  await page.getByRole("button", { name: "Integrate", exact: true }).click();
  await page.getByLabel("Starter template").selectOption("support");
  await page.getByRole("button", { name: "Apply starter template" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Template saved as a draft",
  );
  await page
    .getByRole("button", { name: "Create private draft preview" })
    .click();
  const popupPromise = context.waitForEvent("page");
  await page.getByRole("link", { name: "Open private draft preview" }).click();
  const preview = await popupPromise;
  await expect(
    preview.getByRole("heading", { name: "Customer support" }),
  ).toBeVisible();
  await preview.getByLabel("Your question").fill("zephyr");
  await preview.getByRole("button", { name: "Send message" }).click();
  await expect(preview.getByRole("log")).toContainText("Confidential zephyr");
  await expect(
    preview.getByRole("button", { name: "Request human support" }),
  ).toHaveCount(0);
  const publicPage = await context.newPage();
  await publicPage.goto(`/chat.html?assistant=${assistant}`);
  await expect(
    publicPage.getByRole("heading", { name: "Integration acceptance" }),
  ).toBeVisible();
  await publicPage.getByLabel("Your question").fill("zephyr");
  await publicPage.getByRole("button", { name: "Send message" }).click();
  await expect(publicPage.getByRole("log")).toContainText("enough information");
  expect((await request.get("/v1/downloads/wordpress")).status()).toBe(200);
});
