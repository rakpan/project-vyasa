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

