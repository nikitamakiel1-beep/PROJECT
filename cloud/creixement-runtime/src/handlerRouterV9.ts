import { bioecologyCycle } from "./bioecologyHandler.js";
import { conwayCourtCycle } from "./conwayCourtHandler.js";
import {
  runHandler as runLegacyHandler,
  writeJobReceipt,
  type HandlerContext,
  type HandlerResult,
  type JobExecutionRow,
} from "./handlers.js";

export type { HandlerContext, HandlerResult, JobExecutionRow };
export { writeJobReceipt };

export async function runHandler(ctx: HandlerContext): Promise<HandlerResult> {
  if (ctx.definition.handler_key === "evolution.bioecology_cycle") {
    return bioecologyCycle(ctx);
  }
  if (ctx.definition.handler_key === "evolution.conway_courts") {
    return conwayCourtCycle(ctx);
  }
  return runLegacyHandler(ctx);
}
