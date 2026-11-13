# Parakeet Q8 evaluation and backend selection — closed

The user initially authorized Parakeet Unified English0.6B Q8_0 preparation and evaluation. After seeing its latency/memory results, the user explicitly selected the lowest-latency recognizer. **Whisper base.en int8 is retained; Q8 production activation is cancelled.** Terra, SOUL, household policy, Joe/Piper and recording privacy remain intact.

- [x] P1: Runtime and exact731357568-byte Q8_0 model have pinned revisions, hashes and license/provenance; Linux CPU runtime loads on this VPS without production compilation.
  EVIDENCE: model/revision/SHA and license files verified; PyPI0.4.2 universal/native wheels installed binary-only with pinned hashes. CPU zen4 backend and inference succeed on glibc2.34. See PARAKEET-BENCHMARK.md.

- [x] P2: Matched synthetic fixtures establish transcription correctness, measured timing and recognition memory; user chooses the active backend from the evidence.
  EVIDENCE: short greeting warm median Whisper0.441s versus Q8 1.608s. Q8 recognition-only high-water RSS1004.8MiB including mapped pages. User explicitly selected lowest latency; original Whisper/Joe remains active and live checks verify its selection and health.

## Superseded delivery gates

Original P3 (implement a production Q8/Piper backend) and P4 (activate it) were held after the measured regression. The user's explicit lowest-latency choice supersedes and cancels those two Q8 delivery requirements. They are removed from the active gate list for that documented scope change, not represented as successful Q8 implementation/deployment. No handoff or further Q8 decision is pending. A future Q8 migration would require new user direction.

No paid service, VPS upgrade, production compilation or household writes occurred. The candidate remains inactive. Existing whole-project physical acceptance and individually confirmed household pilots are tracked separately in GATES.md.
