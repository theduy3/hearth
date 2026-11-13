# Gates: Catthew Note4C household terminal

OWNS: hub/**, firmware/**, tests/**, sim/**, tools/**, docs/**, assets/**, deploy/**, .github/**, requirements*.txt, .env.example, .gitignore, README.md, GATES.md

Scope: Implement the approved color voice terminal, preserving Catthew identity and household sources, and deliver a fork PR with verified VPS/device operation.

- [x] G1: Current host regression suite verifies household scope, durable voice requests, approvals, audio and four-color frame projection
  CHECK: python3 -m unittest discover -s tests -v
  EXPECT: /^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=12a88a106df0a0405160214aa2c4016fb2fd05a99cb6821de7676919ffb5c8ed; exit=0; EXPECT=matched; output-sha256=365a9bbc8d54445136c7b0cea185f38b2255e253009a2c60e3091dd067c725fa; output-bytes=22335; shell=/bin/sh; cwd=/Users/theduy/Repo/hearth-catthew-note4c; path=20e18ba3d3ca/32 entries

- [x] G2: The live authenticated HTTPS voice path recognizes speech, invokes Catthew and returns text plus valid16kHz speaker audio
  CHECK: ssh -o BatchMode=yes -o ConnectTimeout=10 bluehost 'docker exec --user 1500 --workdir /home/hermes/.hermes/catthew-terminal hermes /home/hermes/.hermes/hermes-agent/venv/bin/python -m tools.voice_smoke'
  EXPECT: VOICE_PATH_VERIFIED
  EVIDENCE: automatic-evidence=v1; definition-sha256=b5a29841315a55cc21418f0b801e2c00f6edfad52f35deb0d883df731b4a5b7f; exit=0; EXPECT=matched; output-sha256=5ac9c47e5afcb96d2e4e6d77eec105573826b624fadd95fa70834907e4bea43c; output-bytes=198; shell=/bin/sh; cwd=/Users/theduy/Repo/hearth-catthew-note4c; path=20e18ba3d3ca/32 entries

- [ ] G3: Color firmware compiles and host checks verify native2bpp display commands, navigation, capture and cancellable reply playback
  EVIDENCE: pending; use pinned ESP-IDFv6.1 public GitHub Actions builder

- [x] G4: Supervised VPS services use selected ChatGPT sol6.1, unchanged SOUL, restricted tools and authenticated TLS color frames
  CHECK: python3 tools/verify_vps.py --soul-sha256 4ef56b0716db7006c89862fa9019c430d6b7b7a93b0b058c682f46615e2702f0
  EXPECT: VPS_VERIFIED
  EVIDENCE: automatic-evidence=v1; definition-sha256=4c4c9ef613040c8b5ac2f8188b32be9633a76f96b27e7203ee30f42b6a988060; exit=0; EXPECT=matched; output-sha256=284ebec8519289318c790062e87c3de0af5a0da17b47ea8d56111f9c171dd76e; output-bytes=318; shell=/bin/sh; cwd=/Users/theduy/Repo/hearth-catthew-note4c; path=20e18ba3d3ca/32 entries

- [x] G5A: The private16MiB original image retains its checksum and recorded successful hardware verify-flash result
  CHECK: python3 tools/verify_factory_backup.py
  EXPECT: FACTORY_BACKUP_VERIFIED
  EVIDENCE: automatic-evidence=v1; definition-sha256=e179404318a665ae4ceab0adb965052028de1d4c0de1feb6d25c9d4457c5dfe2; exit=0; EXPECT=matched; output-sha256=64a118b2abbb2aca60dc3377f8c505ed448cc92a9cd4a98c388f2509f07d182c; output-bytes=24; shell=/bin/sh; cwd=/Users/theduy/Repo/hearth-catthew-note4c; path=20e18ba3d3ca/32 entries

- [ ] G5: Physical Note4C accepts verified firmware and passes color, microphone, speaker, gesture and reconnect checks
  EVIDENCE: pending; no firmware WRITE has occurred

- [ ] G6: Individually confirmed live task/event tests, private approvals, source sharing with Telegram/CLI and Mac-off operation pass
  EVIDENCE: pending; no real household records have been changed by verification

- [ ] G7: Whole-branch independent review is resolved and the fork PR is ready for human review
  EVIDENCE: draft PR1 exists; final product review and PR update pending; no automatic merge
