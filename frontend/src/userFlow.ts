import { api, post } from "./api";
import type { Case, CaseDetail, Run, Source } from "./types";
import type { SiemensQuery } from "./siemens";

export interface Attachment {
  key: string;
  name: string;
  size: number;
  file?: File;
  source?: Source;
}
export const fromSource = (source: Source): Attachment => ({
  key: source.id,
  name: source.filename,
  size: source.size,
  source,
});
export function validateFiles(current: Attachment[], incoming: File[]) {
  if (current.length + incoming.length > 10)
    throw new Error("Use up to 10 files in one investigation.");
  if (
    current.reduce((n, f) => n + f.size, 0) +
      incoming.reduce((n, f) => n + f.size, 0) >
    30 * 1024 * 1024
  )
    throw new Error("These files exceed the 30 MiB total limit.");
  for (const file of incoming) {
    if (!/\.(pdf|csv)$/i.test(file.name))
      throw new Error(`${file.name}: choose a CSV or PDF file.`);
    const max = /\.pdf$/i.test(file.name) ? 10 : 2;
    if (!file.size || file.size > max * 1024 * 1024)
      throw new Error(
        `${file.name}: use a non-empty file of at most ${max} MiB.`,
      );
  }
}
async function hashFile(file: File) {
  const bytes = await new Promise<ArrayBuffer>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () =>
      reject(
        new Error(`Could not read ${file.name}. Please choose the file again.`),
      );
    reader.readAsArrayBuffer(file);
  });
  return Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    (b) => b.toString(16).padStart(2, "0"),
  ).join("");
}
export async function startUserInvestigation(options: {
  question: string;
  files: Attachment[];
  caseId: string;
  policy: string;
  onCase: (id: string) => void;
  onProgress: (text: string) => void;
  onUploaded: (key: string, source: Source) => void;
  siemens?: SiemensQuery;
}) {
  const { question, files, policy, onCase, onProgress, onUploaded } = options;
  let caseId = options.caseId;
  if (!files.length) {
    onProgress("Starting your question…");
    return post<Run>("/api/investigations", {
      question: question.trim(),
      chat_mode: true,
      ...(options.siemens ? { siemens: options.siemens } : {}),
      limits: { max_output_tokens: 2048 },
    });
  }
  if (!caseId) {
    onProgress("Preparing your investigation…");
    const created = await post<Case>("/api/cases", {
      title: question.trim().slice(0, 120),
    });
    caseId = created.id;
    onCase(caseId);
  }
  // Recover a successful upload after a lost response. Compare content, not filenames.
  const existing = await api<CaseDetail>(`/api/cases/${caseId}`);
  for (let index = 0; index < files.length; index++) {
    const item = files[index];
    if (item.source || !item.file) continue;
    onProgress(`Adding file ${index + 1} of ${files.length}: ${item.name}`);
    const digest = await hashFile(item.file);
    let source = existing.sources.find((s) => s.sha256 === digest);
    if (!source) {
      const data = new FormData();
      data.set("file", item.file);
      data.set("data_policy", policy);
      source = await api<Source>(`/api/cases/${caseId}/sources`, {
        method: "POST",
        body: data,
      });
      existing.sources.push(source);
    }
    onUploaded(item.key, source);
  }
  onProgress("Starting the investigation…");
  return post<Run>("/api/investigations", {
    case_id: caseId,
    question: question.trim(),
    use_mock_mcp: false,
    limits: { max_output_tokens: 2048 },
    ...(options.siemens ? { siemens: options.siemens } : {}),
  });
}
export function friendlyStatus(status: string) {
  return (
    (
      {
        queued: "Waiting to start",
        running: "Investigating",
        paused: "Paused",
        completed: "Completed",
        failed: "Needs attention",
        cancelled: "Cancelled",
        interrupted: "Interrupted",
        timed_out: "Time limit reached",
        budget_exceeded: "Limit reached",
      } as Record<string, string>
    )[status] || status
  );
}
export function readableAnswer(
  answer: string,
  citations: { citation_id: string }[],
) {
  return answer.replace(
    /(?:pdf:[0-9a-f-]{36}:p[0-9]+:c[0-9]+|csv:[0-9a-f-]{36}:r[0-9]+|siemens:[0-9a-f-]{36}:r[0-9]+)/g,
    (id) => {
      if (id.startsWith("siemens:")) {
        const index = citations
          .filter((c) => c.citation_id.startsWith("siemens:"))
          .findIndex((c) => c.citation_id === id);
        return index < 0
          ? "Unverified Siemens reference"
          : `Siemens source ${index + 1}`;
      }
      const index = citations.findIndex((c) => c.citation_id === id);
      return index < 0 ? "Unverified source" : `Source ${index + 1}`;
    },
  );
}
