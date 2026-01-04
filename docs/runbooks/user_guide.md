# Project Vyasa User Guide

## Overview

Project Vyasa is a local agentic research factory that helps you build research artifacts (knowledge graphs and manuscripts) from your seed corpus. This guide covers common workflows and features.

## Core Workflows

### Starting a Research Project

1. **Create a Project**: Navigate to the Projects page and click "New Project"
2. **Define Your Thesis**: Enter your research thesis and research questions
3. **Upload Seed Corpus**: Upload PDF files that form your initial knowledge base
4. **Start Research**: Click "Start Research" to begin extraction and synthesis

### Working with the Workbench

The workbench provides a 3-pane interface:
- **Left**: Source/Evidence viewer (PDF or extracted text)
- **Center**: Manuscript editor with live graph updates
- **Right**: Knowledge graph visualization

## Web Search (Workbench)

The Workbench includes a **Web Search** panel that allows you to search the web and queue URLs for review.

### Web Search Restrictions

**Important**: Web search results are restricted to **approved domains only**:
- Government sites (`.gov`)
- Educational institutions (`.edu`)
- Organizations (`.org`)
- Commercial sites (`.com`, `.net`) with quality scoring

This restriction ensures only high-fidelity sources enter your knowledge graph. If a search returns no results, it may be because all results were filtered by the allowlist policy.

### Queue for Review

When you select URLs and click "Queue for Review":
1. **Quota Check**: Each URL consumes 1 request from your monthly quota (default: 500/month)
2. **Allowlist Filtering**: URLs are filtered to ensure only approved domains are processed
3. **Firecrawl Scraping**: URLs are scraped via Firecrawl Cloud (retrieval only)
4. **Claim Extraction**: Claims are extracted using Vyasa's Worker pipeline
5. **Review Task Creation**: A `ReviewTask` is created with status `PENDING` (requires human approval)
6. **No Direct Persistence**: Claims are **not** written to the knowledge graph until you approve them in the Review Queue

**Quota Management**: If your quota is exceeded, the queue operation will fail with a `FAILED` status and reason `quota_exceeded`. You can check your quota usage in the Review Queue or by querying the `web_usage` collection in ArangoDB.

## Handling Disagreements

When the system detects conflicting evidence or requires human judgment, review tasks are created in the **Review Queue**.

### Accessing the Review Queue

1. Navigate to your project: `/projects/{project_id}`
2. Click on "Review Queue" (or navigate to `/projects/{project_id}/review-queue`)
3. Review pending tasks that require your approval

### Review Queue Features

The Review Queue displays:
- **Dispute Summary**: Brief description of the disagreement
- **Source Information**: URLs and domains of web sources (if applicable)
- **Claim Count**: Number of candidate claims extracted
- **Status Badge**: Current review status (PENDING, APPROVED, REJECTED, etc.)
- **Source Quality Score**: Quality assessment of the source (0-100%)

### Review Task Details

Each review task shows:
- Sample claims extracted from web sources
- Source quality metrics
- Creation timestamp
- Related dispute context

**Note**: Approve/Reject actions are coming soon. For now, the Review Queue is read-only and serves as a visibility surface for pending review tasks.

### When Review Tasks Are Created

Review tasks are automatically created when:
- Web augmentation discovers conflicting evidence
- The system requires human judgment on candidate claims
- Quality gates flag content for manual review

## Best Practices

1. **Regular Review**: Check the Review Queue periodically to stay on top of pending reviews
2. **Source Quality**: Pay attention to source quality scores when evaluating claims
3. **Claim Context**: Review sample claims to understand the nature of the disagreement

## Troubleshooting

### No Review Tasks Showing

- Ensure web augmentation is enabled (`WEB_AUGMENTATION_ENABLED=true`)
- Check that disputes have been detected in your project
- Verify that the orchestrator service is running

### Review Queue Not Loading

- Check browser console for errors
- Verify orchestrator API is accessible
- Ensure project ID is correct in the URL

