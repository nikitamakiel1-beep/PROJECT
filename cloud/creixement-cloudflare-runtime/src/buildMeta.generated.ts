// This file is overwritten during dependency installation in Workers Builds.
// The committed fallback keeps local/typecheck environments deterministic.
export const BUILD_COMMIT_SHA: string | null = null;
export const BUILD_BRANCH: string | null = null;
export const BUILD_WORKERS_CI = false;
export const BUILD_UUID: string | null = null;
