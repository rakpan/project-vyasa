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
  rigor_level?: "exploratory" | "conservative";
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
  rigor_level?: "exploratory" | "conservative";
}

export interface ProjectSummary {
  id: string;
  title: string;
  created_at: string; // ISO format timestamp
  seed_files?: string[]; // Optional, may be included in list response
}

// Hub-specific types
export interface ManifestSummary {
  words: number;
  claims: number;
  density: number; // Claims per 100 words
  citations: number;
  tables: number;
  figures: number;
  flags_count_by_type: Record<string, number>;
}

export interface ProjectHubSummary {
  project_id: string;
  title: string;
  tags: string[];
  rigor_level: "exploratory" | "conservative";
  last_updated: string; // ISO format timestamp
  status: "Idle" | "Processing" | "AttentionNeeded";
  open_flags_count: number;
  manifest_summary?: ManifestSummary;
}

export interface ProjectGrouping {
  active_research: ProjectHubSummary[];
  archived_insights: ProjectHubSummary[];
}

// Template types (matches backend ProjectTemplate)
export interface ProjectTemplate {
  id: string;
  name: string;
  description: string;
  suggested_rqs: string[];
  suggested_anti_scope: string[];
  suggested_rigor: "exploratory" | "conservative";
  example_thesis?: string;
}
