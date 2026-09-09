import { randomUUID } from "node:crypto";
import { chooseDecisionMode } from "./scoring.js";
import { decidePolicy, type PolicyRuntimeContext } from "./policy.js";
import { deterministicIdempotencyKey, stableDigest } from "./runtime.js";
import type {
  ExecutionReceipt,
  Opportunity,
  OpportunityDecision,
  OpportunitySignal,
  OutcomeVerification,
  PolicyDecision,
  PolicyEnvelope,
  ProposedAction,
} from "./types.js";

export interface SignalVerifier {
  verify(signal: OpportunitySignal): Promise<{ accepted: boolean; reason?: string; signal: OpportunitySignal }>;
}

export interface OpportunityCompiler {
  compile(signal: OpportunitySignal): Promise<Opportunity | null>;
}

export interface OpportunityStore {
  save(opportunity: Opportunity): Promise<void>;
}

export interface ActionPlanner {
  plan(opportunity: Opportunity, decision: OpportunityDecision): Promise<ProposedAction[]>;
}

export interface ActionExecutor {
  execute(action: ProposedAction, context: { correlationId: string; idempotencyKey: string }): Promise<{
    status: "succeeded" | "failed";
    output?: unknown;
    connectorReceipt?: Record<string, unknown>;
    error?: unknown;
    retryable?: boolean;
  }>;
}

export interface ActionResultVerifier {
  verify(
    action: ProposedAction,
    execution: { status: "succeeded" | "failed"; output?: unknown; connectorReceipt?: Record<string, unknown>; error?: unknown },
  ): Promise<OutcomeVerification>;
}

export interface ReceiptStore {
  save(receipt: ExecutionReceipt): Promise<void>;
  getByIdempotencyKey?(idempotencyKey: string): Promise<ExecutionReceipt | null>;
}

export interface ApprovalQueue {
  queue(input: {
    correlationId: string;
    action: ProposedAction;
    policy: PolicyDecision;
    inputDigest: string;
    idempotencyKey: string;
  }): Promise<void>;
}

export interface RunObserver {
  onEvent(event: { type: string; correlationId: string; payload: Record<string, unknown> }): Promise<void>;
}

export interface PolicyContextProvider {
  getContext(input: { correlationId: string; action: ProposedAction; actionsThisRun: number }): Promise<PolicyRuntimeContext>;
}

export interface AutonomousLoopDeps {
  verifier: SignalVerifier;
  compiler: OpportunityCompiler;
  opportunities: OpportunityStore;
  planner: ActionPlanner;
  executor: ActionExecutor;
  receipts: ReceiptStore;
  observer?: RunObserver;
  resultVerifier?: ActionResultVerifier;
  approvals?: ApprovalQueue;
  policyContext?: PolicyContextProvider;
  policyEnvelopes: PolicyEnvelope[];
}

function idempotencyKey(action: ProposedAction, opportunity: Opportunity): string {
  return deterministicIdempotencyKey({
    opportunityId: opportunity.id,
    actionClass: action.actionClass,
    connector: action.connector ?? null,
    targetRef: action.targetRef ?? opportunity.targetEntityRef ?? null,
    payload: action.payload,
  });
}

function errorRecord(error: unknown): Record<string, unknown> {
  if (error instanceof Error) return { name: error.name, message: error.message };
  if (error && typeof error === "object") return { ...error as Record<string, unknown> };
  return { message: String(error) };
}

function isReusableReceipt(receipt: ExecutionReceipt): boolean {
  return ["succeeded", "queued", "blocked", "cancelled"].includes(receipt.status);
}

export class AutonomousEconomicLoop {
  constructor(private readonly deps: AutonomousLoopDeps) {}

  async processSignal(signal: OpportunitySignal): Promise<{
    correlationId: string;
    accepted: boolean;
    opportunity?: Opportunity;
    decision?: OpportunityDecision;
    receipts: ExecutionReceipt[];
  }> {
    const correlationId = randomUUID();
    const receipts: ExecutionReceipt[] = [];

    await this.emit("signal_received", correlationId, { signalId: signal.id, sourceType: signal.sourceType });

    const verification = await this.deps.verifier.verify(signal);
    if (!verification.accepted || verification.signal.rightsStatus === "blocked") {
      await this.emit("signal_rejected", correlationId, {
        signalId: signal.id,
        reason: verification.reason ?? "verification_failed",
      });
      return { correlationId, accepted: false, receipts };
    }

    const opportunity = await this.deps.compiler.compile(verification.signal);
    if (!opportunity) {
      await this.emit("signal_no_opportunity", correlationId, { signalId: signal.id });
      return { correlationId, accepted: true, receipts };
    }

    const decision = chooseDecisionMode(opportunity);
    opportunity.score = decision.score;
    opportunity.decisionMode = decision.mode;
    opportunity.status = decision.mode === "ABSTAIN" ? "rejected" : "qualified";
    await this.deps.opportunities.save(opportunity);

    await this.emit("opportunity_scored", correlationId, {
      opportunityId: opportunity.id,
      score: decision.score,
      mode: decision.mode,
      rationale: decision.rationale,
    });

    if (decision.mode === "ABSTAIN") {
      return { correlationId, accepted: true, opportunity, decision, receipts };
    }

    const actions = await this.deps.planner.plan(opportunity, decision);
    let actionsThisRun = 0;

    for (const action of actions) {
      const key = idempotencyKey(action, opportunity);
      const inputDigest = stableDigest(action.payload);
      const existing = await this.deps.receipts.getByIdempotencyKey?.(key);

      if (existing && isReusableReceipt(existing)) {
        receipts.push(existing);
        await this.emit("action_deduplicated", correlationId, {
          actionId: action.id,
          actionClass: action.actionClass,
          idempotencyKey: key,
          existingStatus: existing.status,
        });
        continue;
      }

      const dynamicContext = await this.deps.policyContext?.getContext({ correlationId, action, actionsThisRun });
      const policy = decidePolicy(action, this.deps.policyEnvelopes, {
        actionsThisRun,
        ...(dynamicContext ?? {}),
      });
      const startedAt = new Date().toISOString();

      if (!policy.allowed) {
        const receipt: ExecutionReceipt = {
          correlationId,
          idempotencyKey: key,
          actorAgent: action.actorAgent,
          actionClass: action.actionClass,
          policyVersion: policy.policyVersion ?? "none",
          policyDecision: policy.requiresHumanApproval ? "approval_required" : "blocked",
          inputDigest,
          status: policy.requiresHumanApproval ? "queued" : "blocked",
          startedAt,
          completedAt: new Date().toISOString(),
          verified: false,
        };
        receipts.push(receipt);
        await this.deps.receipts.save(receipt);

        if (policy.requiresHumanApproval && this.deps.approvals) {
          await this.deps.approvals.queue({ correlationId, action, policy, inputDigest, idempotencyKey: key });
        }

        await this.emit("action_not_executed", correlationId, {
          actionId: action.id,
          actionClass: action.actionClass,
          reason: policy.reason,
          requiresHumanApproval: policy.requiresHumanApproval,
        });
        continue;
      }

      actionsThisRun += 1;
      await this.emit("action_authorized", correlationId, {
        actionId: action.id,
        actionClass: action.actionClass,
        policyVersion: policy.policyVersion ?? "unknown",
        idempotencyKey: key,
      });

      let execution: Awaited<ReturnType<ActionExecutor["execute"]>>;
      try {
        execution = await this.deps.executor.execute(action, { correlationId, idempotencyKey: key });
      } catch (error) {
        execution = { status: "failed", error, retryable: true };
      }

      const completedAt = new Date().toISOString();
      const outputDigest = execution.output === undefined ? undefined : stableDigest(execution.output);
      let outcome: OutcomeVerification | undefined;
      if (this.deps.resultVerifier) {
        try {
          outcome = await this.deps.resultVerifier.verify(action, execution);
        } catch (error) {
          outcome = {
            verified: false,
            reason: `Result verification failed: ${errorRecord(error).message ?? "unknown"}`,
            truthLevel: execution.connectorReceipt ? "executed_connector_receipt" : "hypothesis",
          };
        }
      }

      const receipt: ExecutionReceipt = {
        correlationId,
        idempotencyKey: key,
        actorAgent: action.actorAgent,
        actionClass: action.actionClass,
        policyVersion: policy.policyVersion ?? "unknown",
        policyDecision: "authorized",
        inputDigest,
        ...(outputDigest ? { outputDigest } : {}),
        ...(execution.connectorReceipt ? { connectorReceipt: execution.connectorReceipt } : {}),
        status: execution.status,
        startedAt,
        completedAt,
        verified: outcome?.verified ?? false,
        retryable: execution.retryable ?? false,
        ...(execution.error ? { error: errorRecord(execution.error) } : {}),
      };
      receipts.push(receipt);
      await this.deps.receipts.save(receipt);

      await this.emit("action_executed", correlationId, {
        actionId: action.id,
        actionClass: action.actionClass,
        status: execution.status,
        verified: outcome?.verified ?? false,
        truthLevel: outcome?.truthLevel ?? (execution.connectorReceipt ? "executed_connector_receipt" : "hypothesis"),
        verificationReason: outcome?.reason ?? "No result verifier configured; execution success is not business-outcome proof.",
        idempotencyKey: key,
      });
    }

    return { correlationId, accepted: true, opportunity, decision, receipts };
  }

  private async emit(type: string, correlationId: string, payload: Record<string, unknown>): Promise<void> {
    if (this.deps.observer) await this.deps.observer.onEvent({ type, correlationId, payload });
  }
}
