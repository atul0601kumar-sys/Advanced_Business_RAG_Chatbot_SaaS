import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const requiredFiles = [
  ".env",
  path.join("backend", ".env"),
  path.join("frontend", ".env.local"),
];
const requiredArtifacts = [
  path.join("backend", "coverage.xml"),
  path.join("frontend", "coverage", "coverage-summary.json"),
];

const missingFiles = requiredFiles.filter((file) => !fs.existsSync(path.join(root, file)));
const missingArtifacts = requiredArtifacts.filter((file) => !fs.existsSync(path.join(root, file)));

if (missingFiles.length) {
  console.error("Pre-deployment check failed. Missing environment files:");
  for (const file of missingFiles) {
    console.error(`- ${file}`);
  }
  process.exit(1);
}

if (missingArtifacts.length) {
  console.error("Pre-deployment check failed. Missing required test artifacts:");
  for (const file of missingArtifacts) {
    console.error(`- ${file}`);
  }
  console.error("Run `npm run test:ci` before `npm run test:predeploy` to generate fresh reports.");
  process.exit(1);
}

console.log("Pre-deployment environment files and coverage artifacts are present.");
