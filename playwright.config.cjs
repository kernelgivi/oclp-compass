const { defineConfig } = require("@playwright/test");

// Optional executable override makes the same suite usable in constrained CI.
const executablePath = process.env.COMPASS_BROWSER_EXECUTABLE;
module.exports = defineConfig({
  testDir: "./tests/browser",
  timeout: 120000,
  expect: { timeout: 10000 },
  workers: 1,
  use: {
    browserName: "chromium",
    viewport: { width: 1536, height: 1100 },
    launchOptions: executablePath
      ? {
          executablePath,
          args: [
            "--no-sandbox",
            "--no-zygote",
            "--single-process",
            "--disable-dev-shm-usage",
            "--use-gl=angle",
            "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader",
          ],
        }
      : {},
  },
  reporter: "list",
});
