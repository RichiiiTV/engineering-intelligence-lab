# Simplified user experience — design proposal v1

Status: approved by the user on 2026-10-29; implementation on branch `codex/simple-user-experience`.

Generated using the built-in image_gen tool, with GPT Image 2 requested. These are visual proposals, not functional screenshots.

## Proposed flow

1. Start: attach CSV/PDF evidence and ask a question. One primary action: Investigate.
2. Progress: show a plain-language status and a simple pause/cancel option; keep tool logs hidden by default.
3. Results: lead with the finding, a small comparison, clickable source references and calibrated uncertainty. Offer report download or another question.

Retain the current technical workbench under Advanced workspace. Keep budgets, model configuration, raw traces, UUIDs and hashes out of the ordinary user flow. Preserve evidence isolation, synthetic/public-data confirmation and explicit approval before saving report drafts. The intended simple flow creates the underlying case without requiring a separate case-setup step. UI copy, labels, and source summaries must be populated from validated case evidence rather than hardcoded from this example.

## Files

- 01-start-investigation.png
- 02-review-findings.png

## Generation prompts

### Screen 1

Use case: ui-mockup.
Asset type: high-fidelity desktop web application mockup for approval, screen 1 of a simpler two-screen user journey for the existing Engineering Intelligence Lab (EIL).
Primary request: Use GPT Image 2 to visualize an extremely simple, approachable engineering investigation app for ordinary users. This is a real application screen, not a marketing landing page and not an admin dashboard.
Composition: one complete flat front-facing desktop screen, landscape approximately 1536x1024. No physical monitor, no perspective, no annotations around the screen. Calm near-white canvas, clear charcoal text, restrained muted-violet primary action consistent with the existing EIL product, subtle gray borders and generous spacing. Clean contemporary sans-serif typography, realistic 16px body text and a confident 36px heading. Large readable controls. Aim for a shippable product screenshot.
Header: small purple outline beaker mark and "Engineering Intelligence Lab" on the left; one quiet "My investigations" navigation link and a small round user avatar on the right. No left sidebar.
Main content: a centered column about 760 pixels wide. An understated three-step line "1 Add files   2 Ask a question   3 Review findings". Main heading exactly "What would you like to investigate?" and subheading "Add your files and ask in plain language."
Main white bordered card: a spacious labeled question field "Your question" containing "Why did false rejects increase at station S03?" Below it a visually simple file attachment area with paperclip icon and "Add CSV or PDF files". Two compact attached-file rows with small format icons, filenames "inspection_data.csv" and "maintenance_note.pdf", and quiet checkmarks. No metadata tables. Small helper text "Synthetic or licensed public data only." One large violet primary button at the lower right of the card, exactly "Investigate", with a small right arrow. Below the card a small unobtrusive lock icon and text "Your files are processed locally."
Below with ample space: a simple heading "Recent investigations", with just two minimal text rows, "S03 inspection drift" with "Completed · Yesterday" and "Packaging line check" with "Draft". A very subtle footer text link "Advanced workspace" provides access to the existing technical view.
Constraints: communicate one clear task and one primary action. Preserve an engineering investigation purpose, no decorative illustrations or photos. No tool timeline, no token counts, no UUIDs, no MCP jargon, no budget controls, no source hashes, no KPI grid, no dense report text. The mockup must feel dramatically simpler than a technical admin interface. All copy in English. Render the requested text accurately and crisply; no lorem ipsum or random labels.

### Screen 2

Use case: ui-mockup.
Asset type: high-fidelity desktop web application mockup for approval, screen 2 of the same simplified Engineering Intelligence Lab (EIL) user journey.
Primary request: Use GPT Image 2 to design the completed investigation results screen for an ordinary engineer. Make findings immediately understandable and make evidence available through small source links. Dramatically simpler than an admin/debug dashboard.
Style: flat front-facing realistic product screenshot, landscape around 1536x1024. Near-white background, charcoal large readable sans-serif type, restrained violet primary button and violet beaker outline logo, very subtle gray borders and generous whitespace, consistent with a minimal upload-and-question EIL app. No physical device or perspective. No ornamental illustrations.
Header: violet outline beaker mark plus "Engineering Intelligence Lab" left. Quiet "My investigations" link and round avatar right. No sidebar.
Main centered content, about 900 pixels wide. A small back link "My investigations". Under it a discreet green check and "Investigation complete". Main heading exactly "Here's what changed." Show the original question below in quieter text: "Why did false rejects increase at station S03?"
One large main white card. A small label "Main finding". Headline "False rejects increased most at S03". One clear explanatory sentence "The rate rose from 1.61% to 14.11% — an increase of 12.50 percentage points." Within the same card, a very simple two-row horizontal comparison, labeled "Before" and "During incident", bars sharing one scale. A short light-lavender bar for Before, value "1.61%"; a much longer violet bar for During incident, value "14.11%". Values must be accurate and visually proportional. This is a small supporting chart, not a dashboard.
Below that, a short section labeled "Related evidence" with text "Lighting and exposure settings changed in the same period." Two easy-to-click source pills, a spreadsheet icon with "Inspection data" and a document icon with "Maintenance note · page 2". A quiet soft amber or neutral note exactly "A possible connection, not a confirmed cause." No confidence percentage or causal certainty.
Below the card, a simple next-step block, label "Suggested next check", sentence "Check illumination uniformity and verify camera exposure settings." This suggests human verification only, not equipment control.
At the bottom of the main content one clear violet primary action "Download report". A secondary text action "Ask another question". An unobtrusive collapsed row "Advanced details" conceals technical traces. A tiny footer "Synthetic demo evidence · Review findings before use".
Constraints: single-column plain-language results; no KPI tile grid, no station ranking table, no UUIDs, no model selector, no token budgets, no MCP jargon, no tool timeline, no raw citations or hashes, no data-policy form on this screen. Sources must feel accessible without overwhelming the answer. Preserve strong contrast and large readable body copy. All copy in English, exactly spelled. No lorem ipsum.
