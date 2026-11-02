import type { Run } from "./types";
import { t } from "./i18n";

export function tokenContinuation(run: Run): number | null {
  const tokenStop =
    run.error?.resource === "tokens" ||
    (!run.error?.resource &&
      run.error?.message.startsWith("tokens budget exhausted"));
  const outputStop = run.error?.resource === "output_tokens";
  if (run.status !== "budget_exceeded" || !(tokenStop || outputStop))
    return null;
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
  if (outputStop || run.finish_from_evidence) return null;
  const extra = Math.min(32768, 131072 - l.max_total_tokens);
  return extra > 0 && remaining + extra >= minimum ? extra : null;
}

export function continuationLabel(run: Run, extra: number): string {
  return run.error?.resource === "output_tokens"
    ? t("Aus vorhandenen Belegen abschließen")
    : extra
      ? t("Mit zusätzlicher Kapazität fortsetzen")
      : t("Untersuchung fortsetzen");
}
