import type { PublicReference, SiemensQuery, SiemensSnapshot } from "./siemens";

export interface Case {
  id: string;
  title: string;
  created_at: string;
}
export interface Source {
  id: string;
  filename: string;
  kind: "pdf" | "csv";
  sha256: string;
  size: number;
  row_count?: number;
  page_count?: number;
  data_policy: string;
}
export interface CaseDetail extends Case {
  sources: Source[];
}
export interface Limits {
  max_steps: number;
  max_model_calls: number;
  max_tool_calls: number;
  max_total_tokens: number;
  max_output_tokens: number;
  timeout_seconds: number;
}
export interface Run {
  id: string;
  case_id: string | null;
  chat_mode?: boolean;
  use_library?: boolean;
  library_document_ids?: string[];
  siemens?: SiemensQuery | null;
  question: string;
  status: string;
  created_at: string;
  model: string;
  model_calls: number;
  tool_calls: number;
  tokens: number;
  steps: number;
  elapsed_seconds: number;
  attempt_started_at: string | null;
  source_ids: string[];
  use_mock_mcp: boolean;
  limits: Limits;
  error: { code: string; message: string; resource?: string | null } | null;
  result: {
    answer: string;
    warning: string;
    capacity_limited?: boolean;
    answer_contract?: {
      outcome: string;
      issues: string[];
      claim_entailment: string;
    };
  } | null;
}
export interface RunEvent {
  id: number;
  run_id: string;
  at: string;
  type: string;
  data: Record<string, unknown>;
}
export interface Rank {
  station_id: string;
  baseline_rate: number;
  incident_rate: number;
  delta_percentage_points: number;
  baseline_inspected: number;
  incident_inspected: number;
  supporting_row_count: number;
  example_citations: string[];
}
export interface Comparison {
  ranking: Rank[];
  query_provenance: Record<string, unknown>;
  uncertainty: string;
}
export interface Citation {
  citation_id: string;
  kind: string;
  filename: string;
  sha256: string;
  source_id: string;
  page?: number;
  pages?: number[];
  text?: string;
  row?: Record<string, unknown>;
  cited_in_answer?: boolean;
  returned_by_tool?: boolean;
}
export interface Hit extends Citation {
  lexical_score: number;
}
export interface EvidenceReport {
  machine_id?: string;
  machine_snapshot?: { id: string; title: string; version: string }[];
  machine_retrieval?: {
    method?: string;
    notice?: string | null;
    semantic_available?: boolean;
  };
  answer_contract?: {
    outcome: string;
    issues: string[];
    claim_entailment: string;
  };
  library_snapshot?: { id: string; title: string; version: string }[];
  library_citations?: {
    pages?: number[];
    line_start?: number;
    line_end?: number;
    returned_by_tool?: boolean;
    id: string;
    citation_id: string;
    title: string;
    filename: string;
    page: number;
    text: string;
    family: string;
    version: string;
    license_note: string;
    data_policy: string;
    cited_in_answer: boolean;
  }[];
  library_retrieval?: {
    method?: string;
    notice?: string | null;
    semantic_available?: boolean;
  };
  library_citation_checks?: {
    unresolved: string[];
    not_returned_by_tools: string[];
  };
  integrations?: { siemens?: SiemensSnapshot | null };
  external_references?: PublicReference[];
  external_reference_checks?: {
    unresolved: string[];
    technical_claims_verified: boolean;
  };
  answer: string;
  citations: Citation[];
  citation_checks: {
    unresolved: string[];
    not_returned_by_tools: string[];
    malformed: string[];
    has_answer_citations: boolean;
  };
  uncertainty: { limitations: string[] };
  source_snapshot: Source[];
}
export interface Proposal {
  id: string;
  case_id: string;
  run_id: string;
  title: string;
  body: string;
  sha256: string;
  status: string;
  created_at: string;
  draft_id: string | null;
}
export interface Draft extends Proposal {
  proposal_id: string;
}
