import { api, post } from "./api";
import type { Case, CaseDetail, Run, Source } from "./types";
import type { SiemensQuery } from "./siemens";
import type { LibrarySelection } from "./KnowledgeLibrary";

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
    throw new Error("Bis zu 10 Dateien pro Untersuchung verwenden.");
  if (
    current.reduce((n, f) => n + f.size, 0) +
      incoming.reduce((n, f) => n + f.size, 0) >
    30 * 1024 * 1024
  )
    throw new Error("Diese Dateien überschreiten die Gesamtgrenze von 30 MiB.");
  for (const file of incoming) {
    if (!/\.(pdf|csv)$/i.test(file.name))
      throw new Error(`${file.name}: CSV- oder PDF-Datei auswählen.`);
    const max = /\.pdf$/i.test(file.name) ? 10 : 2;
    if (!file.size || file.size > max * 1024 * 1024)
      throw new Error(
        `${file.name}: eine nicht leere Datei mit höchstens ${max} MiB verwenden.`,
      );
  }
}
async function hashFile(file: File) {
  const bytes = await new Promise<ArrayBuffer>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () =>
      reject(
        new Error(
          `Datei konnte nicht gelesen werden: ${file.name}. Bitte wähle die Datei erneut aus.`,
        ),
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
  library?: LibrarySelection;
}) {
  const { question, files, policy, onCase, onProgress, onUploaded } = options;
  let caseId = options.caseId;
  if (!files.length) {
    onProgress("Deine Frage wird gestartet…");
    return post<Run>("/api/investigations", {
      question: question.trim(),
      chat_mode: true,
      ...(options.library
        ? {
            use_library: options.library.enabled,
            ...(options.library.enabled &&
            options.library.documentIds !== undefined
              ? { library_document_ids: options.library.documentIds }
              : {}),
          }
        : {}),
      ...(options.siemens ? { siemens: options.siemens } : {}),
      limits: { max_output_tokens: 2048 },
    });
  }
  if (!caseId) {
    onProgress("Untersuchung wird vorbereitet…");
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
    onProgress(
      `Datei wird hinzugefügt: ${index + 1} of ${files.length}: ${item.name}`,
    );
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
  onProgress("Untersuchung wird gestartet…");
  return post<Run>("/api/investigations", {
    case_id: caseId,
    question: question.trim(),
    use_mock_mcp: false,
    ...(options.library
      ? {
          use_library: options.library.enabled,
          ...(options.library.enabled &&
          options.library.documentIds !== undefined
            ? { library_document_ids: options.library.documentIds }
            : {}),
        }
      : {}),
    limits: { max_output_tokens: 2048 },
    ...(options.siemens ? { siemens: options.siemens } : {}),
  });
}
export function friendlyStatus(status: string) {
  return (
    (
      {
        queued: "Wartet auf den Start",
        running: "Wird untersucht",
        paused: "Pausiert",
        completed: "Abgeschlossen",
        failed: "Aufmerksamkeit erforderlich",
        cancelled: "Abgebrochen",
        interrupted: "Unterbrochen",
        timed_out: "Zeitlimit erreicht",
        budget_exceeded: "Budget erreicht",
      } as Record<string, string>
    )[status] || status
  );
}
export function readableAnswer(
  answer: string,
  citations: { citation_id: string }[],
) {
  return answer.replace(
    /(?:pdf:[0-9a-f-]{36}:p[0-9]+:c[0-9]+|csv:[0-9a-f-]{36}:r[0-9]+|siemens:[0-9a-f-]{36}:r[0-9]+|kb:[0-9a-f-]{36}:p[0-9]+:c[0-9]+)/g,
    (id) => {
      if (id.startsWith("kb:")) {
        const index = citations
          .filter((c) => c.citation_id.startsWith("kb:"))
          .findIndex((c) => c.citation_id === id);
        return index < 0
          ? "Ungeprüfte Bibliotheksreferenz"
          : `Bibliotheksquelle ${index + 1}`;
      }
      if (id.startsWith("siemens:")) {
        const index = citations
          .filter((c) => c.citation_id.startsWith("siemens:"))
          .findIndex((c) => c.citation_id === id);
        return index < 0
          ? "Ungeprüfte Siemens-Referenz"
          : `Siemens-Quelle ${index + 1}`;
      }
      const index = citations.findIndex((c) => c.citation_id === id);
      return index < 0 ? "Ungeprüfte Quelle" : `Quelle ${index + 1}`;
    },
  );
}
