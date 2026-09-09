import { createHash, randomUUID } from "node:crypto";
import { chooseDecisionMode } from "./scoring.js";
import { decidePolicy } from "./policy.js";
import type {
  ExecutionReceipt,
  Opportunity,
  OpportunityDecision,
  OpportunitySignal,
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
  }>;
}

export interface ReceiptStore {
  save(receipt: ExecutionReceipt): Promise<void>;
}

export interface RunObserver {
  onEvent(event: { type: string; correlationId: string; payload: Record<string, unknown> }): Promise<void>;
}

export interface AutonomousLoopDeps {
  verifier: SignalVerifier;
  compiler: OpportunityCompiler;
  opportunities: OpportunityStore;
  planner: ActionPlanner;
  executor: ActionExecutor;
  receipts: ReceiptStore;
  observer?: RunObserver;
  policyEnvelopes: PolicyEnvelope[];
}

function digest(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function idempotencyKey(action: ProposedAction, opportunity: Opportunity): string {
  return digest({ opportunityId: opportunity.id, actionClass: action.actionClass, payload: action.payload });
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
    for (const action of actions) {
      const policy = decidePolicy(action, this.deps.policyEnvelopes);
      const key = idempotencyKey(action, opportunity);
      const startedAt = new Date().toISOString();

      if (!policy.allowed) {
        const receipt: ExecutionReceipt = {
          correlationId,
          idempotencyKey: key,
          actorAgent: action.actorAgent,
          actionClass: action.actionClass,
          policyVersion: policy.policyVersion ?? "none",
          policyDecision: policy.requiresHumanApproval ? "approval_required" : "blocked",
          inputDigest: digest(action.payload),
          status: policy.requiresHumanApproval ? "queued" : "blocked",
          startedAt,
          completedAt: new Date().toISOString(),
        };
        receipts.push(receipt);
        await this.deps.receipts.save(receipt);
        await this.emit("action_not_executed", correlationId, {
          actionId: action.id,
          actionClass: action.actionClass,
          reason: policy.reason,
          requiresHumanApproval: policy.requiresHumanApproval,
        });
        continue;
      }

      const execution = await this.deps.executor.execute(action, { correlationId, idempotencyKey: key });
      const completedAt = new Date().toISOString();
      const outputDigest = execution.output === undefined ? undefined : digest(execution.output);
      const receipt: ExecutionReceipt = {
        correlationId,
        idempotencyKey: key,
        actorAgent: action.actorAgent,
        actionClass: action.actionClass,
        policyVersion: policy.policyVersion ?? "unknown",
        policyDecision: "authorized",
        inputDigest: digest(action.payload),
        ...(outputDigest ? { outputDigest } : {}),
        ...(execution.connectorReceipt ? { connectorReceipt: execution.connectorReceipt } : {}),
        status: execution.status,
        startedAt,
        completedAt,
      };
      receipts.push(receipt);
      await this.deps.receipts.save(receipt);
      await this.emit("action_executed", correlationId, {
        actionId: action.id,
        actionClass: action.actionClass,
        status: execution.status,
        idempotencyKey: key,
      });
    }

    return { correlationId, accepted: true, opportunity, decision, receipts };
  }

  private async emit(type: string, correlationId: string, payload: Record<string, unknown>): Promise<void> {
    if (this.deps.observer) await this.deps.observer.onEvent({ type, correlationId, payload });
  }
}
