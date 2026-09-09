import { createHmac, timingSafeEqual } from "node:crypto";

export interface ServiceIdentity {
  service: string;
  keyId: string;
  enabled: boolean;
  allowedAudiences: string[];
  allowedOperations: string[];
  maxClockSkewSeconds: number;
}

export interface SignedServiceRequest {
  service: string;
  keyId: string;
  audience: string;
  operation: string;
  correlationId: string;
  nonce: string;
  timestamp: string;
  bodyDigest: string;
  signature: string;
}

export interface NonceStore {
  has(service: string, nonce: string): Promise<boolean>;
  put(service: string, nonce: string, expiresAt: string): Promise<void>;
}

function canonicalPayload(request: Omit<SignedServiceRequest, "signature">): string {
  return [
    request.service,
    request.keyId,
    request.audience,
    request.operation,
    request.correlationId,
    request.nonce,
    request.timestamp,
    request.bodyDigest,
  ].join("\n");
}

function equalHex(a: string, b: string): boolean {
  if (!/^[0-9a-f]+$/i.test(a) || !/^[0-9a-f]+$/i.test(b)) return false;
  const left = Buffer.from(a, "hex");
  const right = Buffer.from(b, "hex");
  if (left.length !== right.length) return false;
  return timingSafeEqual(left, right);
}

export function signServiceRequest(
  request: Omit<SignedServiceRequest, "signature">,
  secret: string,
): SignedServiceRequest {
  if (!secret) throw new Error("Signing secret must not be empty");
  const signature = createHmac("sha256", secret).update(canonicalPayload(request)).digest("hex");
  return { ...request, signature };
}

export async function verifyServiceRequest(
  request: SignedServiceRequest,
  identity: ServiceIdentity,
  secret: string,
  nonceStore: NonceStore,
  now = new Date(),
): Promise<{ allowed: boolean; reason: string }> {
  if (!identity.enabled) return { allowed: false, reason: "service identity disabled" };
  if (identity.service !== request.service || identity.keyId !== request.keyId) {
    return { allowed: false, reason: "service identity/key mismatch" };
  }
  if (!identity.allowedAudiences.includes(request.audience)) {
    return { allowed: false, reason: "audience not permitted" };
  }
  if (!identity.allowedOperations.includes(request.operation)) {
    return { allowed: false, reason: "operation not permitted" };
  }
  const timestampMs = Date.parse(request.timestamp);
  if (!Number.isFinite(timestampMs)) return { allowed: false, reason: "invalid request timestamp" };
  const skewMs = Math.abs(now.getTime() - timestampMs);
  if (skewMs > identity.maxClockSkewSeconds * 1000) {
    return { allowed: false, reason: "request timestamp outside allowed clock skew" };
  }
  if (await nonceStore.has(request.service, request.nonce)) {
    return { allowed: false, reason: "replayed nonce" };
  }

  const { signature: _signature, ...unsigned } = request;
  const expected = createHmac("sha256", secret).update(canonicalPayload(unsigned)).digest("hex");
  if (!equalHex(expected, request.signature)) return { allowed: false, reason: "invalid signature" };

  await nonceStore.put(
    request.service,
    request.nonce,
    new Date(timestampMs + identity.maxClockSkewSeconds * 2000).toISOString(),
  );
  return { allowed: true, reason: "signed service request verified" };
}
