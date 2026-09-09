import type { VercelRequest, VercelResponse } from "@vercel/node";
import { authorizeBearer } from "../src/auth.js";
import { loadEnv, loadOwnerToken } from "../src/env.js";
import { SupabaseHttp } from "../src/supabase.js";

interface OwnerDecisionBody {
  idempotencyKey?: string;
  subjectType?: string;
  subjectKey?: string;
  decision?: string;
  payloadDigest?: string;
  rationale?: string;
  modifications?: Record<string, unknown>;
  evidenceRefs?: string[];
}

function bodyObject(value: unknown): OwnerDecisionBody {
  if (typeof value === "string") {
    try { return JSON.parse(value) as OwnerDecisionBody; } catch { return {}; }
  }
  return value && typeof value === "object" ? value as OwnerDecisionBody : {};
}

export default async function handler(request: VercelRequest, response: VercelResponse): Promise<void> {
  if (request.method !== "GET" && request.method !== "POST") {
    response.setHeader("Allow", "GET, POST");
    response.status(405).json({ ok: false, error: "method_not_allowed" });
    return;
  }

  try {
    const env = loadEnv();
    const ownerToken = loadOwnerToken();
    if (!authorizeBearer(request.headers.authorization, ownerToken)) {
      response.status(401).json({ ok: false, error: "unauthorized" });
      return;
    }
    const db = new SupabaseHttp(env);

    if (request.method === "GET") {
      const rows = await db.select<Array<Record<string, unknown>>>(
        "v_owner_decision_queue_v6?select=*&order=created_at.asc&limit=100",
      );
      response.status(200).json({ ok: true, observedAt: new Date().toISOString(), decisions: rows });
      return;
    }

    const body = bodyObject(request.body);
    const required = [body.idempotencyKey, body.subjectType, body.subjectKey, body.decision, body.payloadDigest];
    if (required.some((value) => typeof value !== "string" || value.trim().length === 0)) {
      response.status(400).json({ ok: false, error: "missing_required_fields" });
      return;
    }
    if (!/^[0-9a-fA-F]{64}$/.test(body.payloadDigest!)) {
      response.status(400).json({ ok: false, error: "invalid_payload_digest" });
      return;
    }

    const result = await db.rpc<Record<string, unknown>>("creixement_submit_owner_decision_v6", {
      p_idempotency_key: body.idempotencyKey!.slice(0, 200),
      p_subject_type: body.subjectType!.slice(0, 40),
      p_subject_key: body.subjectKey!.slice(0, 300),
      p_decision: body.decision!.slice(0, 20),
      p_payload_digest: body.payloadDigest!.toLowerCase(),
      p_rationale: body.rationale?.slice(0, 4000) ?? null,
      p_modifications: body.modifications ?? {},
      p_evidence_refs: Array.isArray(body.evidenceRefs) ? body.evidenceRefs.slice(0, 50) : [],
    });

    response.status(201).json({
      ok: true,
      recorded: result,
      execution: "not_performed",
      note: "The decision is durable and evented; downstream execution remains subject to policy, authorization and receipts.",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    response.status(503).json({ ok: false, error: "owner_decision_unavailable", detail: message.slice(0, 1000) });
  }
}
