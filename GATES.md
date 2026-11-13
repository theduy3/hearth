# Gates: Catthew Note4C household terminal

OWNS: hub/**, firmware/**, tests/**, sim/**, tools/**, docs/**, assets/**, deploy/**, .github/**, requirements*.txt, .gitignore, README.md, GATES.md

Scope: Implement the approved color voice terminal, preserving Catthew identity and household sources, and deliver a fork PR with verified VPS/device operation.

- [x] G1: Current host regression suite verifies household scope, durable voice requests, approvals, audio and four-color frame projection
  CHECK: python3 -m unittest discover -s tests -v
  EXPECT: /^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=12a88a106df0a0405160214aa2c4016fb2fd05a99cb6821de7676919ffb5c8ed; exit=0; EXPECT=matched; output-sha256=41723b0cc6cf6e02735d98a1a72c6adc4a3c65ebf46348150e47f6daf4f2bbd0; output-bytes=16618; shell=/bin/sh; cwd=/Users/theduy/Repo/hearth-catthew-note4c; path=20e18ba3d3ca/32 entries

- [x] G2: The live authenticated HTTPS voice path recognizes speech, invokes Catthew and returns text plus valid16kHz speaker audio
  CHECK: ssh -o BatchMode=yes -o ConnectTimeout=10 bluehost 'docker exec --user 1500 --workdir /home/hermes/.hermes/catthew-terminal hermes /home/hermes/.hermes/hermes-agent/venv/bin/python -m tools.voice_smoke'
  EXPECT: VOICE_PATH_VERIFIED
  EVIDENCE: automatic-evidence=v1; definition-sha256=b5a29841315a55cc21418f0b801e2c00f6edfad52f35deb0d883df731b4a5b7f; exit=0; EXPECT=matched; output-sha256=baeee91fc36935e3f5a008f5ec1a9a09c12e3f03a27bb64c0cc5c419c5862c78; output-bytes=197; shell=/bin/sh; cwd=/Users/theduy/Repo/hearth-catthew-note4c; path=20e18ba3d3ca/32 entries

- [x] G3: Digest-pinned ESP-IDF6.1 builds the native BWRY firmware; actual driver, PCM protocol and button timing have host regression coverage
  EVIDENCE: run43364193431 succeeded at41c302dde153b2f0f68b795b82d5f3caec6c68d0 (SDK and105 Linux host tests); current artifact flashed and hardware-verified; lifecycle and completed-text corrections included.

- [x] G4: Supervised VPS services use selected ChatGPT sol6.1, unchanged SOUL, restricted tools and authenticated TLS color frames
  CHECK: python3 tools/verify_vps.py --soul-sha256 4ef56b0716db7006c89862fa9019c430d6b7b7a93b0b058c682f46615e2702f0
  EXPECT: VPS_VERIFIED
  EVIDENCE: automatic-evidence=v1; definition-sha256=4c4c9ef613040c8b5ac2f8188b32be9633a76f96b27e7203ee30f42b6a988060; exit=0; EXPECT=matched; output-sha256=01e730bda9afecd1a4c6ad8cbd7eec89a4c9077d0ae7fba578137b2b95b0bf60; output-bytes=352; shell=/bin/sh; cwd=/Users/theduy/Repo/hearth-catthew-note4c; path=20e18ba3d3ca/32 entries

- [x] G5A: The private16MiB original image retains its checksum and recorded successful hardware verify-flash result
  CHECK: python3 tools/verify_factory_backup.py
  EXPECT: FACTORY_BACKUP_VERIFIED
  EVIDENCE: automatic-evidence=v1; definition-sha256=e179404318a665ae4ceab0adb965052028de1d4c0de1feb6d25c9d4457c5dfe2; exit=0; EXPECT=matched; output-sha256=64a118b2abbb2aca60dc3377f8c505ed448cc92a9cd4a98c388f2509f07d182c; output-bytes=24; shell=/bin/sh; cwd=/Users/theduy/Repo/hearth-catthew-note4c; path=20e18ba3d3ca/32 entries

- [ ] G5: Physical Note4C accepts verified firmware and passes color, microphone, speaker, gesture and reconnect checks
  EVIDENCE: firmware41c302d bootloader/partition/application flashed and hardware-verified; USB expected identity/configured=false; private flash log retained. Human color/audio/gesture/reconnect acceptance pending via tools/setup-note4c.sh.

- [ ] G6: Individually confirmed live task/event tests, private approvals, source sharing with Telegram/CLI and Mac-off operation pass
  EVIDENCE: pending; no real household records have been changed by verification

- [x] G7: Whole-branch source review findings are resolved and the fork draft PR presents verified evidence and pending acceptance clearly
  EVIDENCE: Standards validation finding and Spec P2/P3 independently rechecked resolved at41c302d; coverage limits in docs/NOTE4C-REVIEW.md. Draft PR1 updated with current behavior, CI/flash/VPS evidence and pending G5/G6; no automatic merge.
