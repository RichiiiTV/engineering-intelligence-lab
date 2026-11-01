# Chat source reader

Implemented and locally validated on 2026-11-01 for the user's source-view refinement.

Normal chat citations and source-list cards now open a focused reading dialog.
The conversation stays in place; native dialog keyboard handling supports Escape,
focus containment and focus restoration. The reader has responsive typography,
headings/lists, a separate exact original-excerpt view, collapsed document details
and the existing authenticated original-file download. Markdown text excerpts no
longer claim a physical page number; PDF pages and log/code line ranges retain
their reported locations. Controls follow the Deutsch/English selection without
translating source content.

The source is the frozen passage already returned in the investigation export.
Opening it makes no model or retrieval request. Only a recognized pinned-public-pack
wrapper and known document frontmatter are moved into provenance. Adjacent text
remains available in its own disclosure, and the original-excerpt view always
contains the complete unchanged passage. Source HTML, external media and links
remain inert text; remote images/videos are never loaded. Submitted image previews
and downloads use the existing owner-authorized local attachment endpoints.
Source text and uploaded code are never executed. Advanced/legacy library views
retain their existing full-provenance details view and citation behavior.

## Validation

- `cd frontend; npm run test`: **52 tests passed** across 12 files, including five
  new reader acceptance tests. Coverage includes citation and card navigation,
  restoring focus/scroll behavior, exact raw text, scoped links, log/image/PDF
  presentation, bilingual controls, unknown citations and untrusted markup.
- `cd frontend; npm run build`: TypeScript and Vite build passed.
- Targeted `npx prettier --check` and `git diff --check`: passed.
- Browser verification used the existing public Voron test workspace on local
  port 8001, not a new model run. Confirmed the V2 Gantry Squaring excerpt, source
  cards, original-excerpt mode, Escape/focus return, German desktop layout and
  English 390 × 844 mobile layout with no dialog horizontal overflow. Temporary
  viewport override was reset. Screenshots: `reports/source-reader-ui/desktop.png`
  and `reports/source-reader-ui/mobile-en.png` (ignored local artifacts).
- The original-file link downloaded the public pack through the investigation's
  authenticated endpoint. Downloaded and committed source bytes both have SHA-256
  `6f989695d5ffcdb31da80a42911d5daae069c2f3e065020519c119e88639144e`.
- Backend code, endpoints and source corpus bytes were unchanged; backend tests
  were not repeated for this frontend-only refinement. The preceding corpus
  validation recorded 283 passing backend tests in `public-machine-pilot.md`.

## Limits

The reading view intentionally supports a small safe subset of Markdown, rather
than a full web/PDF renderer; complex tables and media markup can be inspected in
the exact original view or downloaded file. No source translation, OCR, ingestion,
retrieval or answer-quality change is included. The failed Voron controller pilot,
earlier M5 quality limitations and deferred hosted validation remain unchanged.
