import fs from "node:fs";

import { defineConfig, devices } from "@playwright/test";

const edgeExecutablePath = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const e2eDistDir = ".next-e2e";
const includeEdge = process.env.PLAYWRIGHT_INCLUDE_EDGE === "1" && fs.existsSync(edgeExecutablePath);
const includeFirefox = process.env.PLAYWRIGHT_INCLUDE_FIREFOX === "1";
const uiRegressionTag = /@ui-regression/;
const realStackTag = /@real-stack/;
const projects = [
  {
    name: "chromium",
    grep: uiRegressionTag,
    grepInvert: realStackTag,
    use: { ...devices["Desktop Chrome"] },
  },
  {
    name: "mobile-chrome",
    grep: uiRegressionTag,
    grepInvert: realStackTag,
    use: { ...devices["Pixel 7"] },
  },
];

if (includeFirefox) {
  projects.push({
    name: "firefox",
    grep: uiRegressionTag,
    grepInvert: realStackTag,
    use: { ...devices["Desktop Firefox"] },
  });
}

if (includeEdge) {
  projects.push(
    {
      name: "edge",
      grep: uiRegressionTag,
      grepInvert: realStackTag,
      use: { ...devices["Desktop Edge"], executablePath: edgeExecutablePath },
    },
    {
      name: "mobile-edge",
      grep: uiRegressionTag,
      grepInvert: realStackTag,
      use: { ...devices["Pixel 7"], executablePath: edgeExecutablePath },
    },
  );
}

if (process.env.PLAYWRIGHT_REAL_STACK === "1") {
  projects.push({
    name: "real-stack-chromium",
    grep: realStackTag,
    use: { ...devices["Desktop Chrome"] },
  });
}

export default defineConfig({
  testDir: "./e2e/tests",
  timeout: 60_000,
  workers: 1,
  retries: 0,
  expect: {
    timeout: 10_000,
  },
  use: {
    actionTimeout: 10_000,
    baseURL: "http://127.0.0.1:3001",
    navigationTimeout: 15_000,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects,
  webServer: process.env.PLAYWRIGHT_EXTERNAL_SERVER === "1"
    ? undefined
    : {
        command: `node ./scripts/run-playwright-webserver.mjs`,
        cwd: "./frontend",
        url: "http://127.0.0.1:3001",
        env: {
          HOSTNAME: "127.0.0.1",
          NEXT_DIST_DIR: e2eDistDir,
          NODE_OPTIONS: "--max-old-space-size=4096",
          PORT: "3001",
        },
        reuseExistingServer: false,
        timeout: 240_000,
      },
});
