import { t } from "./i18n";
/** Presentation only: persisted API identifiers and original source text stay unchanged. */
export const statusLabel = (value: string) =>
  (
    ({
      queued: t("Eingereiht"),
      running: t("In Bearbeitung"),
      completed: t("Abgeschlossen"),
      failed: t("Fehlgeschlagen"),
      cancelled: t("Abgebrochen"),
      interrupted: t("Unterbrochen"),
      paused: t("Pausiert"),
      timed_out: t("Zeitlimit erreicht"),
      budget_exceeded: t("Budget erreicht"),
      accepted: t("Angenommen"),
      extracting: t("Wird extrahiert"),
      indexing: t("Wird indexiert"),
      classifying: t("Wird zugeordnet"),
      discarded: t("Verworfen"),
      pending: t("Ausstehend"),
      approved: t("Freigegeben"),
      rejected: t("Abgelehnt"),
      starting: t("Wird gestartet"),
      parsing: t("Wird gelesen"),
      ready: t("Bereit"),
      stopped: t("Beendet"),
    }) as Record<string, string>
  )[value] || value;

const notices: Record<string, string> = {
  "Citation resolution checks location and source identity, not whether a claim follows.":
    "Quellenprüfungen bestätigen Fundstelle und Quellenidentität, nicht die Unterstützung einer Aussage.",
  "Lexical scores are relevance scores, not calibrated probabilities.":
    "Lexikalische Werte bewerten Relevanz, nicht kalibrierte Wahrscheinlichkeiten.",
  "CSV example rows are not the full aggregation; source hashes and query definitions identify its inputs.":
    "CSV-Beispielzeilen sind nicht die vollständige Aggregation; Quellprüfsummen und Abfragedefinitionen kennzeichnen die Eingaben.",
  "PDF extraction can lose layout; OCR is disabled; absence from search is not evidence of absence.":
    "Bei der PDF-Extraktion kann Layout verloren gehen; OCR ist deaktiviert. Ein fehlender Suchtreffer beweist kein Fehlen der Information.",
  "The configured local model cannot inspect the attached images. Ask the user to type visible error codes; do not claim to have inspected images.":
    "Das konfigurierte lokale Modell kann die angehängten Bilder nicht auswerten. Bitte sichtbare Fehlercodes im Chat eingeben.",
  "No exact CPU/firmware compatibility has been established. Open the manual and check its validity section. No verified engineering answer is available.":
    "Die Kompatibilität mit der genauen CPU und Firmware wurde nicht bestätigt. Handbuch öffnen und den Gültigkeitsbereich prüfen. Es liegt keine verifizierte technische Diagnose vor.",
  "Automatic machine knowledge retrieval was not completed.":
    "Die automatische Suche im Maschinenwissen wurde nicht abgeschlossen.",
  "The provided error logs were not read.":
    "Die eingereichten Fehlerprotokolle wurden nicht gelesen.",
  "Selected sources were not retrieved.":
    "Die ausgewählten Quellen wurden nicht abgerufen.",
  "Some references were not returned by the source tools.":
    "Einige Quellenangaben wurden von den Quellwerkzeugen nicht zurückgegeben.",
  "The answer has no observed source citations.":
    "Die Antwort enthält keine beobachteten Quellenbelege.",
  "Safety classification or interlock role is not established by the retrieved sources.":
    "Die abgerufenen Quellen belegen die behauptete Sicherheitsfunktion oder Verriegelungsrolle nicht.",
  "An evidence quotation does not match an observed passage.":
    "Ein Belegzitat stimmt nicht mit einem abgerufenen Abschnitt überein.",
  "Semantic search unavailable; keyword search was used.":
    "Semantische Suche nicht verfügbar; Stichwortsuche wurde verwendet.",
  "Embedding model changed; reindex documents. Keyword search was used.":
    "Embedding-Modell geändert; Dokumente bitte neu indexieren. Stichwortsuche wurde verwendet.",
  "Documents have not been indexed for semantic search; keyword search was used.":
    "Dokumente sind noch nicht semantisch indexiert; Stichwortsuche wurde verwendet.",
  "No selected source matches the requested product/version.":
    "Keine ausgewählte Quelle passt zum angefragten Produkt bzw. zur Version.",
  "This answer only transcribes the requested image text; no machine diagnosis was performed.":
    "Diese Antwort liest nur den angefragten Bildtext ab; es wurde keine Maschinendiagnose durchgeführt.",
};
export function displayNotice(value: string): string {
  return t(Object.hasOwn(notices, value) ? notices[value] : value);
}

export function requestError(detail: string, status: number): string {
  if (/CSV columns do not match/i.test(detail))
    return t(
      "Die CSV-Spalten entsprechen nicht dem erwarteten Format. Bitte Spaltenüberschriften prüfen.",
    );
  // Stable German guidance rather than exposing backend/library exception prose.
  if (status === 401)
    return t(
      "Anmeldung fehlgeschlagen oder Sitzung abgelaufen. Bitte erneut anmelden.",
    );
  if (status === 403) return t("Für diese Aktion fehlt die Berechtigung.");
  if (status === 404)
    return t(
      "Der angefragte Eintrag wurde nicht gefunden oder gehört nicht zu deinem Konto.",
    );
  if (status === 413)
    return t(
      "Die Datei oder Anfrage überschreitet die erlaubte Größe. Bitte kleinere Dateien verwenden.",
    );
  if (status === 429)
    return t("Zu viele Anfragen. Bitte kurz warten und erneut versuchen.");
  if (status === 503)
    return t(
      "Der benötigte Dienst ist momentan nicht verfügbar. Bitte später erneut versuchen.",
    );
  if (status === 409) {
    if (/current answer|active|running|idle|queue/i.test(detail))
      return t(
        "Eine Verarbeitung läuft bereits oder die Warteschlange ist belegt. Bitte warten und erneut versuchen.",
      );
    if (/submission ID|another problem/i.test(detail))
      return t(
        "Diese Übermittlung gehört zu einer anderen Frage. Bitte einen neuen Chat beginnen.",
      );
    if (/limit|budget|capacity/i.test(detail))
      return t(
        "Das verfügbare Budget oder Speicherlimit wurde erreicht. Bitte die Frage eingrenzen oder die Administration kontaktieren.",
      );
    return t(
      "Die Aktion konnte wegen eines Zustandskonflikts nicht ausgeführt werden. Bitte die Ansicht aktualisieren und erneut versuchen.",
    );
  }
  if (status === 400 || status === 422)
    return t(
      "Die Eingaben oder Dateien sind ungültig. Bitte Dateiformat, Größe und Pflichtfelder prüfen.",
    );
  return t(
    "Die Anfrage konnte nicht abgeschlossen werden. Bitte erneut versuchen; weitere technische Angaben stehen in den lokalen Dienstprotokollen.",
  );
}
