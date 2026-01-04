/**
 * Review Queue types for Project Vyasa.
 * 
 * Mirrors the ReviewTask and ReviewStatus schemas from the orchestrator.
 */

export type ReviewStatus = 
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "REQUEST_MORE"
  | "FAILED";

export interface Claim {
  claim_id: string;
  claim_text: string;
  subject: string;
  predicate: string;
  object: string;
  confidence: number;
  evidence?: string;
  source_anchor?: {
    doc_id: string;
    page_number: number;
    bbox?: { x: number; y: number; w: number; h: number };
    span?: { start: number; end: number };
    snippet?: string;
  };
}

export interface ReviewTask {
  review_id: string;
  project_id: string;
  job_id: string;
  dispute_id: string;
  candidate_claims: Claim[];
  source_quality_score: number;
  status: ReviewStatus;
  created_at: string; // ISO timestamp
  updated_at: string; // ISO timestamp
}

