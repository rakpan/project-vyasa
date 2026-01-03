/**
 * Reusable fixtures for claim/triple-related test data
 */

import { TEST_PROJECT_ID, TEST_JOB_ID } from './project-fixtures';

export const mockTriple = {
  subject: 'Machine Learning',
  predicate: 'improves',
  object: 'data analysis accuracy',
  confidence: 0.92,
  evidence: 'Recent studies show that ML models significantly improve data analysis accuracy.',
  source_pointer: {
    doc_hash: 'doc-hash-123',
    page: 5,
    bbox: [100, 200, 300, 250],
    snippet: 'Machine Learning improves data analysis accuracy',
  },
  claim_id: 'claim-001',
  linked_rq: 'What is the primary research question?',
};

export const mockClaimProposed = {
  ...mockTriple,
  status: 'Proposed',
  provenance: {
    proposed_by: 'Cartographer',
    verified_by: null,
    flagged_by: null,
  },
};

export const mockClaimVerified = {
  ...mockTriple,
  status: 'Accepted',
  provenance: {
    proposed_by: 'Cartographer',
    verified_by: 'Brain',
    flagged_by: null,
  },
};

export const mockClaimFlagged = {
  ...mockTriple,
  subject: 'Conflicting Claim',
  predicate: 'contradicts',
  object: 'previous findings',
  status: 'Flagged',
  provenance: {
    proposed_by: 'Cartographer',
    verified_by: 'Brain',
    flagged_by: 'Critic',
  },
  conflict: {
    conflictId: 'conflict-001',
    summary: 'Source A asserts X, while Source B contradicts this on page Y.',
    details: 'Detailed conflict explanation',
    sourceA: {
      doc_hash: 'doc-hash-123',
      page: 5,
      excerpt: 'Source A claims that X is true.',
    },
    sourceB: {
      doc_hash: 'doc-hash-456',
      page: 12,
      excerpt: 'Source B contradicts this, stating X is false.',
    },
    claimA: 'X is true',
    claimB: 'X is false',
  },
};

export const mockWorkflowResult = {
  job_id: TEST_JOB_ID,
  status: 'COMPLETED',
  result: {
    extracted_json: {
      triples: [mockClaimProposed, mockClaimVerified, mockClaimFlagged],
    },
    artifact_manifest: {
      blocks: [
        {
          block_id: 'block-001',
          text: 'This is a manuscript block with claim-001 referenced.',
          claim_ids: ['claim-001'],
          citation_keys: ['Smith2020'],
          status: 'draft',
        },
      ],
      metrics: {
        total_words: 150,
        total_claims: 3,
        claims_per_100_words: 2.0,
        citation_count: 5,
      },
    },
  },
};

