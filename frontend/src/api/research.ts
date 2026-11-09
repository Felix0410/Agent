import { request } from "../api";

export type ResearchStatus = { enabled: boolean; provider: string | null; status: string };
export type Evidence = {
  id: string;
  title: string;
  url: string;
  snippet: string;
  source_status: "SNIPPET_ONLY" | "EXTRACTED" | "EXTRACTION_FAILED";
  excerpt: string;
  searched_at: string;
};
export const getResearchStatus = (): Promise<ResearchStatus> => request("/api/research/status");
export const getEvidence = (runId: string): Promise<Evidence[]> =>
  request(`/api/runs/${encodeURIComponent(runId)}/research/evidence`);
