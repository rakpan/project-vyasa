/**
 * TypeScript types for Project Kernel domain models.
 * These match the Pydantic models in src/project/types.py.
 */

export interface ProjectCreate {
  title: string;
  thesis: string;
  research_questions: string[];
  anti_scope?: string[] | null;
  target_journal?: string | null;
  seed_files?: string[] | null;
}

export interface ProjectConfig {
  id: string;
  title: string;
  thesis: string;
  research_questions: string[];
  anti_scope?: string[] | null;
  target_journal?: string | null;
  seed_files: string[];
  created_at: string; // ISO format timestamp
}

export interface ProjectSummary {
  id: string;
  title: string;
  created_at: string; // ISO format timestamp
}

