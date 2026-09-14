import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const output = resolve(here, "../src/buildMeta.generated.ts");
const commitSha = (process.env.WORKERS_CI_COMMIT_SHA || process.env.GITHUB_SHA || "").trim() || null;
const branch = (process.env.WORKERS_CI_BRANCH || process.env.GITHUB_REF_NAME || "").trim() || null;
const buildUuid = (process.env.WORKERS_CI_BUILD_UUID || "").trim() || null;
const workersCi = process.env.WORKERS_CI === "1";

const source = `// Generated at install/build time. Do not edit manually.\nexport const BUILD_COMMIT_SHA: string | null = ${JSON.stringify(commitSha)};\nexport const BUILD_BRANCH: string | null = ${JSON.stringify(branch)};\nexport const BUILD_WORKERS_CI = ${workersCi ? "true" : "false"};\nexport const BUILD_UUID: string | null = ${JSON.stringify(buildUuid)};\n`;
writeFileSync(output, source, "utf8");
console.log(JSON.stringify({ event: "creixement.build_meta.generated", commitSha, branch, buildUuid, workersCi }));
