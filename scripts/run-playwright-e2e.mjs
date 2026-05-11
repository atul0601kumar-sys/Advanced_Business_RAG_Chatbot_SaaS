import http from "node:http";
import path from "node:path";
import process from "node:process";
import { execFile, spawn } from "node:child_process";

const repoRoot = process.cwd();
const frontendRoot = path.join(repoRoot, "frontend");
const port = 3001;
const host = "127.0.0.1";

const serverProcess = spawn(process.execPath, ["./scripts/run-playwright-webserver.mjs"], {
  cwd: frontendRoot,
  env: {
    ...process.env,
    HOSTNAME: host,
    NEXT_DIST_DIR: ".next-e2e",
    NODE_OPTIONS: process.env.NODE_OPTIONS || "--max-old-space-size=4096",
    PORT: String(port),
  },
  stdio: "inherit",
});

let shuttingDown = false;

try {
  await waitForServer(`http://${host}:${port}`, 240_000);
  const exitCode = await runPlaywright();
  await shutdownServer();
  process.exit(exitCode);
} catch (error) {
  await shutdownServer();
  throw error;
}

async function runPlaywright() {
  const cliPath = path.join(repoRoot, "node_modules", "@playwright", "test", "cli.js");
  const args = [cliPath, "test", ...process.argv.slice(2)];
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, args, {
      cwd: repoRoot,
      env: {
        ...process.env,
        PLAYWRIGHT_EXTERNAL_SERVER: "1",
      },
      stdio: "inherit",
    });
    child.on("error", reject);
    child.on("exit", (code, signal) => {
      if (signal) {
        reject(new Error(`Playwright exited from signal ${signal}`));
        return;
      }
      resolve(code ?? 1);
    });
  });
}

function waitForServer(baseUrl, timeoutMs) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const request = http.get(baseUrl, (response) => {
        response.resume();
        resolve();
      });
      request.on("error", () => {
        if (Date.now() - startedAt >= timeoutMs) {
          reject(new Error(`Timed out waiting for E2E server at ${baseUrl}`));
          return;
        }
        setTimeout(attempt, 1000).unref();
      });
      request.setTimeout(2000, () => {
        request.destroy();
      });
    };
    attempt();
  });
}

async function shutdownServer() {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;

  if (serverProcess.exitCode !== null || serverProcess.killed) {
    return;
  }

  if (process.platform === "win32") {
    await new Promise((resolve) => {
      execFile("taskkill", ["/pid", String(serverProcess.pid), "/t", "/f"], () => resolve());
    });
    return;
  }

  serverProcess.kill("SIGTERM");
  await new Promise((resolve) => {
    const timer = setTimeout(() => {
      if (serverProcess.exitCode === null) {
        serverProcess.kill("SIGKILL");
      }
      resolve();
    }, 5000);
    timer.unref();
    serverProcess.on("exit", () => {
      clearTimeout(timer);
      resolve();
    });
  });
}
