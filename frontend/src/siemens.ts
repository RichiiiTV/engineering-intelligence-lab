export type SiemensQuery = {
  question: string;
  family?: string;
  cpu?: string;
  firmware?: string;
  tia_version?: string;
};
export type PublicReference = {
  citation_id: string;
  title: string;
  url: string;
  description?: string;
  kind: string;
  tia_version?: string;
  edition?: string;
  language?: string;
  cited_in_answer?: boolean;
};
export type SiemensSnapshot = {
  query_origin?: string;
  enabled: boolean;
  outbound_query: string;
  status: string;
  remote_search_status?: string;
  connection_verified?: boolean;
  retrieved_at?: string;
  version_notice?: string;
  error?: string;
};

export function isSiemensQuestion(question: string) {
  return /\b(?:siemens|simatic|tia(?:\s+portal)?|sps|plc|ob\d+|s7[- ]?\d{3,4})\b/i.test(
    question,
  );
}
export function siemensUrl(value: string) {
  try {
    if (/[\\\s]/.test(value)) return false;
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      !url.username &&
      !url.password &&
      (!url.port || url.port === "443") &&
      (url.hostname === "siemens.com" ||
        url.hostname === "docs.tia.siemens.cloud" ||
        url.hostname.endsWith(".siemens.com")) &&
      url.hostname !== "jobs.siemens.com"
    );
  } catch {
    return false;
  }
}
