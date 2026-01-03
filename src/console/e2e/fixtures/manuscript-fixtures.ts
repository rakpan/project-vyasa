/**
 * Reusable fixtures for manuscript-related test data
 */

import { TEST_PROJECT_ID } from './project-fixtures';

export const mockManuscriptBlock = {
  block_id: 'block-001',
  project_id: TEST_PROJECT_ID,
  text: 'Machine Learning improves data analysis accuracy. Recent studies show significant improvements.',
  claim_ids: ['claim-001', 'claim-002'],
  citation_keys: ['Smith2020', 'Jones2021'],
  status: 'draft',
  version: 1,
  rigor_level: 'exploratory',
};

export const mockForkedBlock = {
  block_id: 'block-001',
  text: 'Machine Learning significantly enhances data analysis accuracy. Recent empirical studies demonstrate substantial improvements in precision and recall metrics.',
  rigor_level: 'conservative',
  read_only: true,
};

