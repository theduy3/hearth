# Hearth · Catthew Note4C

A four-color household voice terminal for the existing Catthew Hermes profile. The Zectrix Note4C handles buttons, microphone, speaker and display. Bluehost runs Hermes, speech recognition, speech synthesis, household tools and screen rendering, so the Mac is needed only for setup and development.

This fork targets the **ESP32-S3 N16R8 Note4C with a real 400 × 300 black/white/red/yellow panel**. Firmware contains no Wi-Fi password, device token or model credential.

## Controls

- **Hold the front button:** interrupt reply playback and record once the indicator turns steady.
- **Release:** submit the recording. The maximum recording is 30 seconds.
- **Short-press the front button or Down:** advance a page.
- **Short-press Up:** return to the previous page.
- **Hold Down:** stop audio/display work safely and enter deep sleep. The front button wakes the device.

The panel uses full refreshes. Navigation presses during a refresh are combined; recording and reply playback run independently. Recording and processing use the indicator rather than additional screen refreshes. An offline badge distinguishes a cached page from current data.

## Household scope

Catthew keeps its existing SOUL and uses `openai-codex` / `gpt-6.1-sol`. Note4C has a separate persistent conversation while sharing the same underlying records with Telegram and CLI.

- Calendar: **Kittyggup Family**, timezone **America/Vancouver**.
- Tasks: exact `catthew` tag in existing `Tasks/tasks`, `Tasks/bugs` and `Tasks/ideas`.
- Reference notes: exact `kittyggup` tag anywhere in the vault.
- Calendar edits/deletions create proposals. A private, expiring, one-use human confirmation authorizes the exact version and change. Device buttons cannot approve changes.

The household MCP exposes scoped record operations. It does not expose a shell, arbitrary paths, calendar selection or an approval/apply tool to the model. The terminal checks the native Hermes tool policy before every turn and refuses unexpected capabilities.

## Current verified checkpoint

The firmware at `d3acefaaa294c93e97128c94b0afe5939f6ea1db` built with the pinned ESP-IDF 6.1 toolchain in [Actions run 43360727456](https://github.com/theduy3/hearth/actions/runs/43360727456). Its bootloader, partition table and application were flashed and verified on the backed-up Note4C. USB reports the expected device identity and an unconfigured device.

The HTTPS backend, native color frames, restricted model path, unchanged SOUL, speech service and Catthew Telegram connection pass release checks. A fresh synthetic English voice round trip returns text and 16 kHz speaker audio. **Physical color/audio/button acceptance and individually confirmed live household write/approval tests remain pending.** See [GATES.md](GATES.md) for the distinction between automatic and human evidence.

## Pair the already-flashed device

On the approved Mac, with the Note4C connected by USB:

```bash
./tools/setup-note4c.sh
```

The wizard checks the four labeled calibration patches before pairing. Enter the 2.4 GHz network name and hidden Wi-Fi password in that terminal. The helper verifies the device against the private backup record and retrieves its dedicated device token privately through the existing `bluehost` SSH alias. Credentials are sent over USB into device NVS; they are not written to a local `.env`, printed, or committed.

It then guides a read-only English greeting, page navigation, playback interruption and a reply while the Mac sleeps and the tablet uses wall power. A fresh VPS job and full-playback acknowledgement are checked for voice tests. Physical acceptance evidence stays under `$HOME/.local/share/catthew-note4c/`.

If a color, audio or gesture check fails, stop at that stage and report the observed behavior. Live family write tests require their separately confirmed record and cleanup; pairing does not authorize test calendar/task mutations.

## Build and verify

Host tests need Python and [requirements.txt](requirements.txt):

```bash
python3 -m unittest discover -s tests -v
```

Native C++ tests compile the actual e-paper driver against trace stubs and check BWRY byte order, command sequencing, power removal, timeout and retry. The PCM decoder tests fragmented WAV input, format/length limits and cancellation. Backend tests cover source scope, concurrency, durable requests, uncertain outcomes, expiry, private approvals, Unicode projection and HTTP boundaries.

[The firmware workflow](.github/workflows/firmware.yml) pins the ESP-IDF 6.1 container by digest and emits a checksummed manifest with build artifacts. It requires no credentials. Avoid installing a large SDK on the Mac or compiling on the production VPS.

Verify a downloaded artifact before writing:

```bash
python3 -m tools.flash_note4c \
  --artifact-dir /private/path/to/note4c-firmware \
  --expect-commit FULL_COMMIT_SHA
```

Writing additionally requires `--write`, a private verified full factory backup, and matching physical device identity. Use `--initial-provision` only for the first layout installation; it erases the new NVS region. Updates preserve pairing unless explicitly erased. The original full 16 MiB image remains private and is never an Actions artifact.

## VPS operation

The production endpoint is `https://zectrix.theduy.cloud`. Caddy terminates TLS; terminal and speech listeners remain loopback-only. The terminal is a supervised systemd service using `deploy/run-terminal.sh` to enter the Hermes container namespaces while retaining its own service cgroup. Do not replace that daemon launcher with `docker exec`: stopping its client can leave the server running stale code.

`tools/configure_catthew.py` performs backed-up profile configuration. Device/API credentials belong in private service state, not this repository. Deployment units and the dedicated Caddy site are under [deploy/](deploy/). Existing unrelated proxy routes and Hermes profiles remain outside this change.

Release checks:

```bash
python3 tools/verify_vps.py --soul-sha256 EXPECTED_SOUL_SHA256
ssh bluehost 'docker exec --user 1500 \
  --workdir /home/hermes/.hermes/catthew-terminal hermes \
  /home/hermes/.hermes/hermes-agent/venv/bin/python -m tools.voice_smoke'
```

The voice smoke test uses a synthetic greeting and creates no family records. After an intentional gateway reload, allow its messaging adapters to initialize before checking `/p/catthew/health`; startup can take minutes.

## Design, protocol and delivery

- [Approved design and delivery plan](docs/CATTHEW-NOTE4C-PLAN.md)
- [Implementation ledger](docs/CATTHEW-IMPLEMENTATION-PROGRESS.md)
- [Device protocol and native pixel format](docs/NOTE4C-PROTOCOL.md)
- [Acceptance gates](GATES.md)
- [Draft PR #1](https://github.com/theduy3/hearth/pull/1), with no automatic merge

Unmodified DejaVu fonts and their attribution are in [assets/fonts/](assets/fonts/). Speech dependencies and pinned model provenance are maintained separately by the speech preparation tools; the Piper engine is GPLv3 and is not vendored into the firmware.
