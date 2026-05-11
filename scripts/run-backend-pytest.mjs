import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
import process from "node:process";

const repoRoot = process.cwd();
const backendDir = path.join(repoRoot, "backend");

const candidates = [
  path.join(backendDir, ".venv", "Scripts", "python.exe"),
  path.join(backendDir, ".venv", "bin", "python"),
  "python",
];

const python = candidates.find((candidate) => candidate === "python" || existsSync(candidate));

if (!python) {
  console.error("Unable to find a Python interpreter for backend tests.");
  process.exit(1);
}

const child = spawn(python, ["-m", "pytest", ...process.argv.slice(2)], {
  cwd: backendDir,
  stdio: "inherit",
  shell: false,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
