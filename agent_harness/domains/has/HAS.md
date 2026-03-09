# HAS Domain Memory

## Overview
HAS (Healthcare AI Suite) — healthcare AI processing validation.

## Document Types
- **Attestation sur l'honneur** — Declaration of compliance
- **Facture** — Invoice for energy efficiency work
- **Devis** — Quote for planned work

## Validation Rules
- YAML-driven guidelines (guideline_version tracks rule version)
- Mandatory fields vary by document type
- Cross-reference validation between attestation and facture

## Known Error Patterns
- Missing SIREN/SIRET numbers
- Date format inconsistencies (DD/MM/YYYY vs YYYY-MM-DD)
- Mismatched amounts between devis and facture
- Incomplete beneficiary information
