# IDP Domain Memory

## Overview
Intelligent Document Processing — extracts structured data from documents using configurable plugins. Each plugin defines an extraction schema that determines what fields to extract. The IDP Platform processes documents through multiple stages (classification, extraction, validation) and returns structured results with per-stage details.

## Core Workflow
1. A document (PDF) is uploaded to a plugin via `upload_document`
2. The platform processes it through the plugin's configured stages
3. Each stage produces a result with status, summary, details, issues, and metrics
4. The final job has a status (pending/running/completed/failed) and optional verdict

## Key Concepts
- **Plugin**: A document type definition with an extraction schema and processing stages
- **Schema**: JSON structure defining fields to extract (versioned, calibratable)
- **Calibration**: Automated schema refinement using sample documents (runs as Temporal workflow)
- **Job**: A single document processing run — has stages, status, and verdict
- **Verdict**: Human or agent review decision (accept/reject) on extracted data
- **Stage**: A processing step (e.g., classification, extraction, validation) with its own result

## Error Patterns
- Schema mismatch: plugin schema doesn't match document structure → low extraction confidence
- Missing fields: required schema fields not found in document → stage issues flagged
- Calibration drift: schema calibrated on different document format than submitted
- Plugin misconfiguration: wrong stages or model assignment for document type

## API Surface
The IDP domain wraps the IDP Platform REST API (19 endpoints). All tool calls go through PolicyChain before execution. Bearer token authentication required.
