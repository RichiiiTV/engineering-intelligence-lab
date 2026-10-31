# Real public machine corpus: Voron 2.4

Added and locally validated on 2026-10-31 at the user's request to find a real machine
online and add its documentation to the app.

## Sources and publication

The selected machine family is the real Voron 2.4 printer. The official product
[README](https://github.com/VoronDesign/Voron-2/blob/7b32e405f0719881cca782500c822e01e3b16bf2/README.md),
[V2 Gantry Squaring guide](https://github.com/VoronDesign/Voron-Documentation/blob/b8c014f88948c9fca963dfe726e0e66b1287af90/build/mechanical/v2_gantry_squaring.md)
and [Octopus controller configuration](https://github.com/VoronDesign/Voron-2/blob/7b32e405f0719881cca782500c822e01e3b16bf2/firmware/klipper_configurations/Octopus/Voron2_Octopus_Config.cfg)
were retrieved from the official Voron Design repositories. Both repositories carry
GNU GPL version 3 LICENSE files; the exact license snapshots are retained.

`data/public-machine-packs/voron-2.4-v1/` contains original source snapshots, a
manifest and one importable Markdown pack. It preserves the original bodies and
all notices, adds declared provenance/source-boundary headers, and includes the
complete GPL license. The two upstream license files are byte-identical, so one
full copy is embedded. Raw/configuration material remains untrusted reference data.
Scoped Git attributes preserve original line endings and intentional upstream
whitespace; application-code whitespace checks remain enabled. Indexed Git bytes
are checked against the manifest before commit.
Nothing from the sources was compiled, flashed, executed or followed to equipment.

The package is **62,116 bytes**. Its published SHA-256 is
`6f989695d5ffcdb31da80a42911d5daae069c2f3e065020519c119e88639144e`.
The manifest also records original file sizes, SHA-256/Git blob hashes, upstream
paths, commit pins and attribution. The content covers the three listed references;
linked manuals, images and videos are outside this snapshot. The Octopus example
contains hardware/build-size variants and placeholders requiring installation checks.

Publication used the actual authenticated administrator UI after the user signed
in. No credentials or roles were changed or bypassed. The admin form now lets the
human distinguish internal material from licensed public documentation and record
bounded license/provenance text. Existing clients retain their prior default.

In the current workspace, automatic local classification created **Voron 2.4** as
a **product family**, with one source and **63 of 63 passages indexed**. It used one
classifier call and 3,671 tokens. The stored bytes/hash, `licensed-public` policy,
license note and active availability were checked after publication. New questions
can retrieve this reference automatically; existing runs retain their prior snapshots.
New installations import the pack explicitly through the administrator workflow.

## Validation

- `.venv\Scripts\python.exe -m pytest -q`: **283 passed in 225.77 seconds**.
- In `frontend`, `npm test -- --reporter=dot`: **47 passed**; `npm run build` passed.
- Ruff, whitespace and lockfile checks passed; no dependency changes were needed.
- New checks cover source/hash/license integrity, original-body preservation,
  public-license metadata, missing public-license form input, oversized note
  rejection and member upload rejection. These establish ingestion behavior, not
  general model answer quality.

Three local-model answer probes used an isolated state containing the same real
corpus and generated test accounts. All selected the Voron family; no Siemens
lookup, hosted provider, equipment access or content execution occurred.

| Probe | Review result | Model/tool calls | Tokens |
|---|---|---:|---:|
| German: three documented symptoms of poor gantry squaring | Correct symptoms with an exact observed source citation | 2 / 1 | 6,251 |
| English: MCU and bootloader size in the Octopus example | **Failed: answered an unrelated gantry question and speculated about Siemens from citation IDs** | 4 / 2 | 13,209 |
| German: meaning of invented code EIL-UNKNOWN-9999 | Correctly stated that the code is undocumented | 3 / 1 | 11,297 |

The controller run had actually observed passages containing **STM32F446** and
**32KiB**. Its failure is an answer-generation/question-focus problem despite
available evidence; its root cause has not been established. The narrow answer
contract reported `no_support` but did not detect the unrelated-question/vendor
assertions. The failed run and observations are retained unchanged. This is **two
expected behaviors out of three**, not a general quality pass. Earlier M5 quality
failures remain relevant; this task did not start a further quality-remediation
milestone. Hosted validation stays deferred.

Ignored local evidence: `reports/voron-pilot-ingestion.json`,
`voron-pilot-questions.json`, `voron-publication.json`, `voron-publication-proof.png`,
`voron-full-backend.log`, `voron-frontend.log` and `reports/voron-pilot-state/`.
