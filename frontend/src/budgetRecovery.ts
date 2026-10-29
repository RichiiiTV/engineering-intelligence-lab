import type { Run } from "./types";

export function tokenContinuation(run: Run): number | null {
  const tokenStop =
    run.error?.resource === "tokens" ||
    (!run.error?.resource &&
      run.error?.message.startsWith("tokens budget exhausted"));
  if (run.status !== "budget_exceeded" || !tokenStop) return null;
  const l = run.limits;
  if (
    run.model_calls >= l.max_model_calls ||
    run.tool_calls >= l.max_tool_calls ||
    run.steps >= l.max_steps ||
    run.elapsed_seconds >= l.timeout_seconds
  )
    return null;
  // The reviewed Ollama adapter uses a fixed 8,192-token context. Server admission is authoritative.
  const minimum = 8192 + Math.min(l.max_output_tokens, 256),
    remaining = l.max_total_tokens - run.tokens;
  if (remaining >= minimum) return 0;
  const extra = Math.min(32768, 131072 - l.max_total_tokens);
  return extra > 0 && remaining + extra >= minimum ? extra : null;
}
