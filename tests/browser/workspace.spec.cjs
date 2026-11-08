const { test, expect } = require("@playwright/test");
const { spawn } = require("node:child_process");
const AxeBuilder = require("@axe-core/playwright").default;
let server;
let url;

test.beforeAll(async () => {
  server = spawn(
    process.env.PYTHON || "python3",
    ["-m", "compass", "gui", "--demo", "--no-browser"],
    { stdio: ["ignore", "pipe", "pipe"] }
  );
  url = await new Promise((resolve, reject) => {
    let output = "";
    const timer = setTimeout(() => reject(new Error("Server startup timed out")), 10000);
    server.stdout.on("data", (chunk) => {
      output += chunk;
      const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#\S+/);
      if (match) {
        clearTimeout(timer);
        resolve(match[0]);
      }
    });
    server.once("error", reject);
    server.once("exit", (code) => reject(new Error(`Server exited ${code}`)));
  });
});

test.afterAll(() => server?.kill());

test("hardware-to-decision workflow, exports, errors, and accessible layouts", async ({
  page,
}, testInfo) => {
  const errors = [];
  const csp = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && /Content Security Policy|Refused to/.test(message.text()))
      csp.push(message.text());
  });
  await page.goto(url);

  await test.step("recommendations and explanations", async () => {
    await expect(page.locator("#best-name")).toHaveText("Sequoia");
    await expect(page.locator("#origin")).toHaveText("DEMO HARDWARE");
    await expect(page.locator("#model-id")).toHaveText("MacBookPro13,3");
    await page.getByRole("button", { name: "Smoothness", exact: true }).click();
    await expect(page.locator("#best-name")).toHaveText("Big Sur");
    await page.getByRole("button", { name: "Newer apps", exact: true }).click();
    await expect(page.locator("#best-name")).toHaveText("Sequoia");
    await page.getByRole("button", { name: "Why this version?", exact: true }).click();
    await expect(page.locator("#detail")).toBeVisible();
    const dialogAudit = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(dialogAudit.violations).toEqual([]);
    await expect(page.locator("#detail-content")).toContainText("Model prior");
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Explain OS recency", exact: true }).click();
    await expect(page.locator("#help-dialog")).toBeVisible();
    await expect(page.locator("#help-content")).toContainText("not an app compatibility database");
    await page.keyboard.press("Escape");
    await page.locator("#show-excluded").uncheck();
    await expect(page.locator("#candidates tr")).toHaveCount(5);
    await page.locator("#show-excluded").check();
    await expect(page.locator("#candidates tr")).toHaveCount(6);
    const audit = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(audit.violations).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath("desktop.png"), fullPage: true });
  });

  await test.step("comparison and target-specific planning", async () => {
    await page.locator('[data-tab="compare"]').click();
    await expect(page.locator(".comparison-heading")).toBeVisible();
    await page.locator("#compare-left").selectOption("12");
    await page.locator("#compare-right").selectOption("15");
    await page.locator("#run-compare").click();
    await expect(page.locator("#comparison-result")).toContainText("Monterey");
    await expect(page.locator("#comparison-result")).toContainText("not percentages");
    await page.locator('[data-tab="plan"]').click();
    await expect(page.locator("#plan-state")).toHaveText("4 items need review");
    for (const id of ["backup", "identity", "apps", "recovery"]) {
      await page.locator(`#confirm-${id}`).check();
      await expect(page.locator(`#confirm-${id}`)).toBeChecked();
    }
    await expect(page.locator("#plan-state")).toHaveText("Planning checklist complete");
    await page.locator("#plan-target").selectOption("26");
    await expect(page.locator("#plan-state")).toHaveText("Target excluded");
    await expect(page.locator(".phase")).toHaveCount(1);
    await page.locator("#plan-target").selectOption("12");
    await expect(page.locator("#plan-content")).toContainText("in-place downgrade");
    await page.screenshot({ path: testInfo.outputPath("plan.png"), fullPage: true });
    const download = page.waitForEvent("download");
    await page.locator("#export-plan").click();
    expect((await download).suggestedFilename()).toBe("compass-MacBookPro13-3-plan.md");
  });

  await test.step("declared app constraints and session isolation", async () => {
    await page.locator('[data-tab="overview"]').click();
    await page.locator("#app-name").fill("My essential app");
    await page.locator("#app-min").selectOption("26");
    await page.getByRole("button", { name: "Add app", exact: true }).click();
    await expect(page.locator("#best-name")).toHaveText("No reviewed fit");
    await page.getByRole("button", { name: "Remove My essential app", exact: true }).click();
    await expect(page.locator("#best-name")).toHaveText("Sequoia");
    await page.locator('[data-tab="plan"]').click();
    await page.locator("#plan-target").selectOption("15");
    await expect(page.locator("#confirm-backup")).not.toBeChecked();
  });

  await test.step("hardware scenarios, profile validation and restoration", async () => {
    await page.locator('[data-tab="hardware"]').click();
    await page.locator("#scenario-ram").fill("4");
    await page.locator("#scenario-drive").selectOption("hdd");
    await page.getByRole("button", { name: "Run simulation", exact: true }).click();
    await expect(page.locator("#scenario-result")).toContainText(
      "active hardware profile has not changed"
    );
    await expect(page.locator("#full-inventory")).toContainText("16 GiB");
    await page.locator("#model-search").fill("MacBookAir5,2");
    await expect(page.locator("#model-select option")).toHaveCount(1);
    await page.locator("#model-select").selectOption("MacBookAir5,2");
    await page.locator("#ram-input").fill("2");
    await page.getByRole("button", { name: "Analyze configuration", exact: true }).click();
    await expect(page.locator("#full-inventory")).toContainText("MacBookAir5,2");
    await expect(page.locator("#inventory-origin")).toHaveText("MANUAL PROFILE");
    await page.getByRole("button", { name: "Restore session profile", exact: true }).click();
    await expect(page.locator("#full-inventory")).toContainText("MacBookPro13,3");
    await page.locator("#import-profile").setInputFiles({
      name: "invalid.json",
      mimeType: "application/json",
      buffer: Buffer.from('{"model":"../../etc/passwd","ram_gb":16}'),
    });
    await expect(page.locator("#error")).toBeVisible();
    await expect(page.locator("#error")).toContainText("previous valid analysis");
    await expect(page.locator("#full-inventory")).toContainText("MacBookPro13,3");
    await page.locator("#dismiss-error").click();
    const download = page.waitForEvent("download");
    await page.locator("#export-profile").click();
    expect((await download).suggestedFilename()).toBe("compass-MacBookPro13-3-profile.json");
    await page.screenshot({ path: testInfo.outputPath("hardware.png"), fullPage: true });
  });

  await test.step("commands, evidence filters, report export, and layout", async () => {
    await page.keyboard.press("Control+k");
    await expect(page.locator("#command-dialog")).toBeVisible();
    const commandAudit = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(commandAudit.violations).toEqual([]);
    await page.locator("#command-search").fill("Owner reports");
    await page.keyboard.press("Enter");
    await expect(page.locator("#evidence")).toBeVisible();
    await expect(page.locator("#corpus-note")).toContainText("bundled corpus contains 2");
    await expect(page.getByRole("link", { name: "Read the original report" })).toHaveCount(1);
    await page.locator("#evidence-sentiment").selectOption("negative");
    await expect(page.locator("#evidence-list")).toContainText("No reports match");
    await page.locator('[data-tab="overview"]').click();
    await page.locator("#export-format").selectOption("json");
    const download = page.waitForEvent("download");
    await page.locator("#export").click();
    expect((await download).suggestedFilename()).toBe("compass-MacBookPro13-3.json");
    await page.getByRole("button", { name: "Larger text", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("data-text-size", "large");
    await page.getByRole("button", { name: "Light mode", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.screenshot({ path: testInfo.outputPath("light-large.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
    ).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath("mobile-large.png"), fullPage: true });
    for (const tab of ["compare", "plan", "hardware", "evidence", "method"]) {
      await page.locator(`[data-tab="${tab}"]`).click();
      await expect(page.locator(`#${tab}`)).toBeVisible();
      const audit = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      expect(audit.violations).toEqual([]);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
      ).toBeTruthy();
    }
    expect(errors).toEqual([]);
    expect(csp).toEqual([]);
  });

  await test.step("unkeyed launch does not disclose hardware", async () => {
    await page.goto(url.split("#")[0]);
    await expect(page.locator("#error")).toContainText("Missing session key");
    await expect(page.locator("#device-name")).toHaveText("Reading hardware…");
  });
});
