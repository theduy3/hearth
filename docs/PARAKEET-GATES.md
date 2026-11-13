# Parakeet Q8_0 delivery gates

User authorizes Parakeet Unified English0.6B Q8_0 GGUF on the existing Bluehost terminal. Keep Terra, SOUL, household policy, Joe/Piper, public speech contract and recording privacy intact. No paid provider, VPS upgrade, production compilation or household writes. Do not claim reduced full-device latency from isolated STT timing.

- [x] P1: Runtime and exact731357568-byte Q8_0 model have pinned revisions, hashes and license/provenance; Linux CPU runtime loads on this VPS without production compilation.
  EVIDENCE: exact Q8 model/revision/SHA and license files verified; PyPI0.4.2 universal/native wheels installed binary-only with pinned hashes. CPU zen4 backend and actual inference succeed on glibc2.34. See PARAKEET-BENCHMARK.md.

- [x] P2: Same synthetic16kHz fixtures establish current Whisper timings and Parakeet cold/warm time, transcription correctness and peak memory under a bounded isolated unit. Judge suitability against current host RAM/swap and existing speech budget before switching.
  EVIDENCE: same Joe16kHz fixtures: Whisper short warm0.441s versus Q8 warm1.608s; longer Q8 samples also slower. Q8 recognition-only high-water RSS1004.8MiB including mapped pages. Trial restored original services. Suitability verdict: do not activate Q8 for lower latency on this host; full combined768MiB budget not proven.

- [ ] P3: Supported runtime API replaces Whisper in the responsible speech layer; validates mono PCM16/16kHz and30second bound, reuses one model, serializes inference, preserves Joe and fails closed on errors. Meaningful host tests and release checks pass.
  CHECK: python3 -m unittest discover -s tests -v
  EXPECT: OK
  EVIDENCE: host suite111tests passes, but no production speech-engine replacement is implemented because the candidate is slower and needs a combined memory-budget decision.
ABANDON: P3 Backend migration held for user speed/quality and resource-budget direction after measured Q8 regression.

- [ ] P4: Authorized deployment preserves queued/device conversations and speech rollback, loads only Parakeet recognition, passes synthetic transcription/speech and authenticated voice round trip, records measured timings and memory without private recordings or transcripts. Revert the speech unit/source if suitability or smoke verification fails.
  EVIDENCE: Q8 trial and automatic restoration completed; original Whisper/Joe STT/TTS and all live VPS checks pass. Candidate/runtime remain installed but inactive. No household writes, profile/SOUL change or gateway restart.
ABANDON: P4 No Q8 production activation without resolving measured speed/memory regression; retain working Whisper/Joe service.
