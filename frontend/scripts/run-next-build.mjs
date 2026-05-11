import { existsSync, rmSync } from "node:fs";
import { execFileSync, spawn } from "node:child_process";
import path from "node:path";
import process from "node:process";

const workspaceRoot = process.cwd();
const nextDir = path.join(workspaceRoot, process.env.NEXT_DIST_DIR || ".next");

if (existsSync(nextDir)) {
  removeBuildDirectory(nextDir);
}

const nextBinary = process.platform === "win32"
  ? path.join(workspaceRoot, "..", "node_modules", ".bin", "next.cmd")
  : path.join(workspaceRoot, "..", "node_modules", ".bin", "next");

const child = process.platform === "win32"
  ? spawn("cmd.exe", ["/d", "/s", "/c", `${nextBinary} build`], {
      cwd: workspaceRoot,
      stdio: "inherit",
      env: process.env,
    })
  : spawn(nextBinary, ["build"], {
      cwd: workspaceRoot,
      stdio: "inherit",
      env: process.env,
    });

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});

function removeBuildDirectory(targetDir) {
  const maxAttempts = 5;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      rmSync(targetDir, { recursive: true, force: true, maxRetries: 3, retryDelay: 150 });
      return;
    } catch (error) {
      if (attempt === maxAttempts) {
        break;
      }
      sleep(250 * attempt);
    }
  }

  if (process.platform === "win32") {
    execFileSync("cmd.exe", ["/d", "/s", "/c", `if exist "${targetDir}" rmdir /s /q "${targetDir}"`], {
      stdio: "inherit",
    });
    return;
  }

  throw new Error(`Could not remove stale Next.js build directory: ${targetDir}`);
}

function sleep(milliseconds) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds);
}
