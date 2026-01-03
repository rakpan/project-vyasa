/**
 * Reusable fixtures for project-related test data
 * All IDs and timestamps are deterministic for stable tests
 */

export const TEST_PROJECT_ID = 'test-project-12345';
export const TEST_JOB_ID = 'test-job-67890';
export const TEST_INGESTION_ID = 'test-ingestion-abcde';

export const mockProject = {
  id: TEST_PROJECT_ID,
  title: 'Test Research Project',
  thesis: 'This is a test thesis statement for E2E testing.',
  research_questions: [
    'What is the primary research question?',
    'How does this relate to existing work?',
  ],
  anti_scope: ['Mobile applications', 'Hardware security'],
  target_journal: 'IEEE Test Journal',
  seed_files: ['test-document.pdf'],
  rigor_level: 'exploratory',
  created_at: '2024-01-15T10:30:00Z',
  tags: ['test', 'e2e'],
  last_updated: '2024-01-15T10:30:00Z',
  archived: false,
};

export const mockProjectCreate = {
  title: 'New Test Project',
  thesis: 'This is a new test project thesis.',
  research_questions: ['What is the research question?'],
  anti_scope: [],
  target_journal: null,
  seed_files: [],
};

export const mockProjectTemplates = [
  {
    id: 'exploratory-research',
    name: 'Exploratory Research',
    description: 'Default rigor, broad scope',
    rigor_level: 'exploratory',
  },
  {
    id: 'conservative-review',
    name: 'Conservative Review',
    description: 'Stricter validation, precision-focused',
    rigor_level: 'conservative',
  },
];

