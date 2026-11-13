# Gates: Catthew Note4C household terminal

OWNS: hub/**, firmware/**, tests/**, sim/**, tools/**, docs/**, assets/**, deploy/**, .github/**, requirements*.txt, .gitignore, README.md, GATES.md

Scope: Implement the approved color voice terminal, preserving Catthew identity and household sources, and deliver a fork PR with verified VPS/device operation.

Run Python checks in an environment with `requirements.txt` installed. Latest local validation used the private `~/.local/share/catthew-note4c/test-venv/bin/python`; Linux CI installs requirements in a fresh venv.

- [x] G1: Current host regression suite verifies household scope, durable voice requests, approvals, audio and four-color frame projection
  CHECK: python3 -m unittest discover -s tests -v
  EXPECT: /^OK$/m
  EVIDENCE: 137 tests passed locally and in Linux CI run43392558966 at09d1fa2. Coverage includes scoped records, explicit event expiry, today-only/local-day filtering, grocery isolation/Markdown/retries/races, typed per-request page selection and projection refresh before completion.

- [x] G2: The live authenticated HTTPS voice path recognizes speech, invokes Catthew and returns text plus valid16kHz speaker audio
  CHECK: ssh -o BatchMode=yes -o ConnectTimeout=10 bluehost 'docker exec --user 1500 --workdir /home/hermes/.hermes/catthew-terminal hermes /home/hermes/.hermes/hermes-agent/venv/bin/python -m tools.voice_smoke'
  EXPECT: VOICE_PATH_VERIFIED
  EVIDENCE: latest read-only synthetic task-speech test completed STT→Catthew→MCP→16kHz audio, selected page today, and verified public audio. Private task-page-voice-check.json records request2c997479825b4512aaae82c38ee06073, 111084 PCM bytes and22.398s audio-ready time for this household query. This is backend routing/audio evidence, not a new physical microphone/playback claim.

- [x] G3: Digest-pinned ESP-IDF6.1 builds the native BWRY firmware; actual driver, PCM protocol and button timing have host regression coverage
  EVIDENCE: run43392558966 succeeded at09d1fa2e92dc437be0192ca489561b47c5a9d627 (SDK and137 Linux host tests). Its artifact was identity-checked, flashed and verified in all3regions without NVS erasure; Wi-Fi/time/online/frame HTTP200 readiness passed.

- [x] G4: Supervised VPS services use user-selected ChatGPT Terra6.1, unchanged SOUL, restricted tools, measured faster Whisper and exactly two authenticated TLS color screens
  CHECK: python3 tools/verify_vps.py --soul-sha256 4ef56b0716db7006c89862fa9019c430d6b7b7a93b0b058c682f46615e2702f0
  EXPECT: VPS_VERIFIED
  EVIDENCE: user explicitly selected gpt-6.1-terra and the lowest measured STT latency (Whisper). Fresh verify_vps exits0 with all checks true/VPS_VERIFIED: two_page_navigation, selected model/provider, unchanged SOUL, scoped tools, male speech, frames/TLS, Telegram and owned supervision.137host tests pass for today-only Tasks and Grocery Shopping, stable visible-pixel ETags, frame transport, request-scoped navigation, and exact speech-process/model-hash checks. Fresh public frames match the complete current projection. Actual model grocery-read succeeded with0items; original profile config bytes were restored after a supported household-only MCP refresh.

- [x] G5A: The private16MiB original image retains its checksum and recorded successful hardware verify-flash result
  CHECK: python3 tools/verify_factory_backup.py
  EXPECT: FACTORY_BACKUP_VERIFIED
  EVIDENCE: automatic-evidence=v1; definition-sha256=e179404318a665ae4ceab0adb965052028de1d4c0de1feb6d25c9d4457c5dfe2; exit=0; EXPECT=matched; output-sha256=64a118b2abbb2aca60dc3377f8c505ed448cc92a9cd4a98c388f2509f07d182c; output-bytes=24; shell=/bin/sh; cwd=/Users/theduy/Repo/hearth-catthew-note4c; path=20e18ba3d3ca/32 entries

- [ ] G5: Physical Note4C accepts verified firmware and passes color, microphone, speaker, gesture and reconnect checks
  EVIDENCE: firmware09d1fa2 identity/flash verified, pairing retained and authenticated frame success. Previous user evidence confirms the~15second settling waveform and voice chat. New physical request-directed navigation, Joe voice, interruption and reconnect acceptance still require user observation.

- [ ] G6: Individually confirmed live task/event tests, private approvals, source sharing with Telegram/CLI and Mac-off operation pass
  EVIDENCE: user-authorized classification completed three elapsed closure records and kept the future closure pending; due dates, source metadata, older completed records and cancelled grocery history were preserved. No calendar mutation or fabricated live grocery item. Full task/calendar/approval/shared-channel/Mac-off pilot remains pending.

- [ ] G7: Whole-branch source review findings are resolved and the fork draft PR presents verified evidence and pending acceptance clearly
  EVIDENCE: earlier foundation and grocery/event reviews found and resolved concrete issues (coverage in docs/NOTE4C-REVIEW.md). Latest09d1fa2 routing was self-reviewed and passed137tests, CI and live task-speech routing. A fresh independent routing review could not run: repeated review-service upstream502; fallback CLI review returned invalid_params. No review output was produced by those attempts. Draft PR remains unmerged; independent follow-up remains open.
