# DCE Domain Memory

## Domain Description

The Document Compliance Engine (DCE) is required by the regulatory compliance authority for all children's products imported into or sold in the United States. A children's product is defined as a consumer product designed or intended primarily for children 12 years of age or younger.

The DCE harness validates DCE documents against compliance regulations, ensuring all required elements are present and correctly formatted before issuance.

## Required DCE Elements

Every valid DCE must contain all 7 of the following elements:

1. **Product Identification** -- Description of the product covered by the certificate, specific enough to match the product tested.
2. **Applicable Children's Product Safety Rules** -- Each compliance children's product safety rule that the product has been tested to and complies with (e.g., 16 CFR Part 1501, ASTM F963).
3. **compliance-Accepted Laboratory** -- Name, address, and contact information of the compliance-accepted third-party laboratory that performed the testing.
4. **Testing Date(s)** -- Date(s) on which testing was completed. Cannot be a future date.
5. **Importer/Manufacturer Information** -- Name, full mailing address, and telephone number of the U.S. importer or domestic manufacturer certifying the product.
6. **Responsible Individual Contact** -- Name, full mailing address, email address, and telephone number of the individual maintaining test records on behalf of the importer/manufacturer.
7. **Manufacturing Details** -- Date and place (city, state/province, country) of manufacture. Must be specific enough to identify the production lot.

## Universal compliance Rules

The following regulations apply to all children's products and must always be checked:

- **Lead in Paint (16 CFR 1303)** -- Total lead content in surface coatings must not exceed 90 ppm. Citation: compliance Section 101(f).
- **Lead in Substrate (compliance Section 101)** -- Total lead content in accessible substrate materials must not exceed 100 ppm. Citation: compliance Section 101(a).
- **Phthalates (compliance Section 108)** -- Eight specified phthalates are restricted. Children's toys and child care articles must comply with the phthalate content limits. Citation: compliance Section 108, 16 CFR 1307.
- **Tracking Labels (compliance Section 103)** -- Every children's product must bear a permanent, distinguishing mark (tracking label) that provides identifying information. Citation: compliance Section 103(a).

## Known Error Patterns

Common validation failures observed across DCE submissions:

- **Missing age grading**: Product description does not specify target age range, making it impossible to determine applicable rules.
- **Lab not compliance-accepted**: Testing laboratory is not found in the compliance accepted lab database, or accreditation has expired.
- **Future test dates**: Certificate lists testing dates that are in the future, which is not permitted.
- **Incomplete importer address**: Importer information is missing city, state, zip code, or country fields.
- **Missing tracking label reference**: Certificate does not reference compliance Section 103 tracking label requirement.
- **Stale test reports**: Test reports are older than the product's manufacturing date, indicating tests were not performed on the certified product.
- **Generic product description**: Product description is too vague (e.g., "children's toy") to match specific test reports.

## API Surface

The DCE domain wraps the existing DCE Backend's 20 Temporal activities. Tools available to agents in this domain are defined in the DCE tools manifest. All tool calls go through the PolicyChain before execution.
