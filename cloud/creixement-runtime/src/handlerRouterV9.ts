import { bioecologyCycle } from "./bioecologyHandler.js";
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
  return runLegacyHandler(ctx);
}
