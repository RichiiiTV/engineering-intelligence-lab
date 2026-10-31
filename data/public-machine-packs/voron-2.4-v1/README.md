# Voron 2.4 public reference pack — v1

This is real, publicly released Voron Design material. It describes a product family
and a controller configuration example, rather than a particular installed printer.

Import `voron-2.4-official-reference-pack.md` through Administration → Machine
knowledge. Choose **Licensed public documentation**, retain the GPL-3.0 attribution
from `manifest.json`, and confirm workspace publication rights. The existing local
embedding/classification pipeline assigns the machine automatically.

The single upload contains three unmodified upstream source bodies:

- Voron-2's official Voron 2.4 product README.
- Voron-Documentation's V2 Gantry Squaring guide.
- Voron-2's BigTreeTech Octopus V1 configuration example.

The original snapshots are stored alongside it. `manifest.json` records repository,
commit, path, original URL, byte length, SHA-256 and Git blob hash for every file.
The assembled upload also has its own SHA-256. The documentation snapshot is pinned
to `b8c014f88948c9fca963dfe726e0e66b1287af90`; the printer repository is pinned to
`7b32e405f0719881cca782500c822e01e3b16bf2`.

Voron Design and contributors retain their rights in the upstream material, released
under GNU GPL version 3. Both upstream LICENSE snapshots are retained. They are
byte-identical; one complete license copy is embedded in the upload. The assembled
pack is distributed under the same license. Added provenance headings, source
boundaries and the license appendix are identified as EIL operator changes; the
original source bodies are unchanged.

Coverage is limited to these text/configuration snapshots. Linked assembly manuals,
images, videos and included configuration files are not downloaded or followed.
Controller pins, placeholders, build sizes and firmware applicability must be
checked against the actual installation. Commands/macros remain reference data;
the app does not compile, flash, execute them or connect to equipment.

Example questions:

- “Welche drei Symptome nennt die Voron-2.4-Dokumentation für eine schlecht
  ausgerichtete Gantry?”
- “Which MCU and bootloader size are listed in the included Voron 2.4 Octopus example?”
- “Ist der Fehler EIL-UNKNOWN-9999 in diesen Quellen dokumentiert?” (It is absent.)

See `docs/public-machine-pilot.md` for local ingestion and answer validation results.
