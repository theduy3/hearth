# Gates: Catthew Note4C household terminal

OWNS: hub/**, firmware/**, tests/**, sim/**, tools/**, docs/**, .env.example, README.md, GATES.md

Scope: Implement the approved color voice terminal, preserving Catthew identity and household sources, and deliver a fork PR with verified VPS/device operation.

- [x] G1: The isolated upstream baseline passes its existing regression suite
  CHECK: python3 -m unittest discover -s tests -v
  EXPECT: OK
  EVIDENCE: automatic-evidence=v1; definition-sha256=a9ebb7a92aea1c58d944c284626802ababdbb4c8785404f2e652da8974768869; exit=0; EXPECT=matched; output-sha256=958b668d4891f178b0851c3895845b32d4c931bf803414b10fb19104880bf563; output-bytes=9245; shell=/bin/sh; cwd=/Users/theduy/Repo/hearth-catthew-note4c; path=20e18ba3d3ca/32 entries

- [ ] G2: Authenticated hub, Catthew sessions, approvals, durable retries, source projections, STT and TTS pass behavioral integration tests
  EVIDENCE: pending; write and run focused tests before claiming this outcome

- [ ] G3: Color firmware compiles and simulator verifies real four-color rendering and button/audio lifecycle
  EVIDENCE: pending; ESP-IDF toolchain is not currently on PATH

- [ ] G4: VPS runtime uses verified ChatGPT sol6.1 with unchanged Catthew SOUL, private integrations and a working authenticated HTTPS endpoint
  EVIDENCE: pending

- [ ] G5: Verified original device flash backup exists and physical Note4C accepts color, voice, speech playback and reconnection checks
  EVIDENCE: pending

- [ ] G6: Household calendar and vault integration, scoped approvals, Telegram/CLI and Mac-off operation meet end-to-end acceptance
  EVIDENCE: pending

- [ ] G7: Independent branch review is resolved and a reviewable PR exists in theduy3/hearth
  EVIDENCE: pending
