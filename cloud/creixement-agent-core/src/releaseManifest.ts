import { createHash } from "node:crypto";

export interface ReleaseComponent {
  key: string;
  version: string;
  digest: string;
  kind: "code" | "migration" | "config" | "schema" | "prompt" | "template" | "model";
}

export interface ReleaseManifest {
  releaseId: string;
  branch: string;
  commitSha: string;
  createdAt: string;
  components: ReleaseComponent[];
  migrationHead: string;
  constitutionVersion: string;
  schedulerVersion: string;
  manifestDigest: string;
}

function canonical(manifest: Omit<ReleaseManifest, "manifestDigest">): string {
  const components = [...manifest.components].sort((a, b) => a.key.localeCompare(b.key));
  return JSON.stringify({ ...manifest, components });
}

export function buildReleaseManifest(input: Omit<ReleaseManifest, "manifestDigest">): ReleaseManifest {
  const manifestDigest = createHash("sha256").update(canonical(input)).digest("hex");
  return { ...input, components: [...input.components].sort((a, b) => a.key.localeCompare(b.key)), manifestDigest };
}

export function verifyReleaseManifest(manifest: ReleaseManifest): boolean {
  const { manifestDigest, ...unsigned } = manifest;
  return createHash("sha256").update(canonical(unsigned)).digest("hex") === manifestDigest;
}
