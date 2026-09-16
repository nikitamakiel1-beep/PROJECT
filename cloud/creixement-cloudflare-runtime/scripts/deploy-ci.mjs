import { spawnSync } from "node:child_process";

const isWorkersCi = process.env.WORKERS_CI === "1" || process.env.CI === "true";
const commitSha = (process.env.WORKERS_CI_COMMIT_SHA || process.env.GITHUB_SHA || "").trim();
const branch = (process.env.WORKERS_CI_BRANCH || process.env.GITHUB_REF_NAME || "production/creixement-kairon").trim();

if (isWorkersCi && !commitSha) {
  console.error("Refusing CI deploy without WORKERS_CI_COMMIT_SHA/GITHUB_SHA.");
  process.exit(2);
}

const attestedCommit = commitSha || "local-unattested";
const vars = [
  `CREIXEMENT_COMMIT_SHA:${attestedCommit}`,
  `CREIXEMENT_BRANCH:${branch}`,
  "CREIXEMENT_RUNTIME_ID:kairon-cloudflare-v10",
  "CREIXEMENT_RUNTIME_VERSION:1.0.0",
  "CREIXEMENT_ENVIRONMENT:production",
  "CREIXEMENT_DB_TIMEOUT_MS:8000",
];

console.log(JSON.stringify({
  event: "creixement.cloudflare.deploy_attestation",
  commitSha: attestedCommit,
  branch,
  runtimeVersion: "1.0.0",
  runtimeId: "kairon-cloudflare-v10",
  workersCi: process.env.WORKERS_CI ?? null,
  buildUuid: process.env.WORKERS_CI_BUILD_UUID ?? null,
}));

const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const result = spawnSync(npx, ["wrangler", "deploy", "--var", ...vars], {
  stdio: "inherit",
  env: process.env,
});

if (result.error) {
  console.error(result.error);
  process.exit(1);
}
process.exit(result.status ?? 1);
