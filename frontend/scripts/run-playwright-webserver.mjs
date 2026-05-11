import { cpSync, existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawn } from "node:child_process";

const workspaceRoot = process.cwd();
const distDir = process.env.NEXT_DIST_DIR || ".next-e2e";
const host = process.env.HOSTNAME || "127.0.0.1";
const port = process.env.PORT || "3001";

await runBuild();
copyStaticAssets();
await startStandaloneServer();

async function runBuild() {
  await runChild(process.execPath, ["./scripts/run-next-build.mjs"], {
    cwd: workspaceRoot,
    env: {
      ...process.env,
      NEXT_DIST_DIR: distDir,
      NODE_OPTIONS: process.env.NODE_OPTIONS || "--max-old-space-size=4096",
    },
  });
}

function copyStaticAssets() {
  const sourceDir = path.join(workspaceRoot, distDir, "static");
  const targetDir = path.join(workspaceRoot, distDir, "standalone", "frontend", distDir, "static");

  if (!existsSync(sourceDir)) {
    throw new Error(`Expected built static assets at ${sourceDir}`);
  }

  mkdirSync(targetDir, { recursive: true });
  cpSync(sourceDir, targetDir, { recursive: true, force: true });
}

async function startStandaloneServer() {
  const serverEntry = path.join(workspaceRoot, distDir, "standalone", "frontend", "server.js");
  const child = spawn(process.execPath, [serverEntry], {
    cwd: workspaceRoot,
    env: {
      ...process.env,
      NEXT_DIST_DIR: distDir,
      HOSTNAME: host,
      PORT: port,
    },
    stdio: "inherit",
  });

  let shuttingDown = false;

  const shutdown = (signal) => {
    if (shuttingDown) {
      return;
    }
    shuttingDown = true;
    if (!child.killed) {
      child.kill(signal);
      setTimeout(() => {
        if (!child.killed) {
          child.kill("SIGKILL");
        }
      }, 5000).unref();
    }
  };

  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(signal, () => shutdown(signal));
  }

  await new Promise((resolve, reject) => {
    child.on("error", reject);
    child.on("exit", (code, signal) => {
      if (shuttingDown) {
        resolve();
        return;
      }
      if (signal) {
        reject(new Error(`Playwright web server exited from signal ${signal}`));
        return;
      }
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`Playwright web server exited with code ${code ?? "unknown"}`));
    });
  });
}

function runChild(command, args, options) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      ...options,
      stdio: "inherit",
    });
    child.on("error", reject);
    child.on("exit", (code, signal) => {
      if (signal) {
        reject(new Error(`Command exited from signal ${signal}`));
        return;
      }
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`Command exited with code ${code ?? "unknown"}`));
    });
  });
}
