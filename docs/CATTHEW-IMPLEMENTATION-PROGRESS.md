# Approved implementation progress

Approval: canvas fb-65 and user message "approved plan". Original design: `docs/CATTHEW-NOTE4C-PLAN.md`.

Workspace `/Users/theduy/Repo/hearth-catthew-note4c`, branch `feat/catthew-note4c`, base `edd75fd7ea7e9879b141a84aa39ce2c74b6c92bc`. Fork https://github.com/theduy3/hearth. Draft PR https://github.com/theduy3/hearth/pull/1 targets fork main; no automatic merge.

## Settled requirements

Existing Catthew SOUL; ChatGPT `gpt-6.1-sol`; English voice and displayed replies; front hold-to-talk/release-to-send/short-press pages; actual BWRY color; all runtime on Bluehost; Kittyggup Family in America/Vancouver; `catthew` tasks and `kittyggup` reference notes; same profile for Telegram/CLI with a separate persistent Note4C conversation; household tool scope; explicit approval for calendar edits/deletions; domain zectrix.theduy.cloud.

## Completed and verified

- Commits `d2dfa18` approved design/ledger and `ecbb507` durable request/gateway foundations were pushed. Further backend work below is not committed yet.
- DNS A record resolves zectrix.theduy.cloud to 129.121.100.233. No AAAA record.
- User completed Codex OAuth. Read-only credential resolver succeeds through `api_key`; GET-only account catalog includes exact `gpt-6.1-sol`.
- Scoped, private API is running at `127.0.0.1:8642/p/catthew`. Profile bearer authentication succeeds. A real model turn returned exactly `Catthew Note4C connection verified.` No household writes were requested.
- Catthew config deliberately selects openai-codex / gpt-6.1-sol. SOUL hash remains `4ef56b0716db7006c89862fa9019c430d6b7b7a93b0b058c682f46615e2702f0`. Root profile model and existing Telegram tool selections were preserved.
- After a graceful gateway reload, root and all named Telegram adapters reported connected, including Catthew. API was initially slow to become ready while existing MCP servers initialized; do not confuse that with a failed restart.
- Existing Hermes injects x_search for bare MCP-only lists and auto-enables previously unknown plugins. Configuration now records installed known builtin/plugin catalogs and selects zero-tool `stt` plus exact `catthew-household` MCP. The live native tool inventory reports only stt enabled with **zero tools**. Gateway checks this before EVERY agent turn and refuses unexpected native capabilities. Do not remove this guard or silently patch the installed Hermes source.
- Fresh local full suite: **141 tests passed** (20.28 s). Includes frame packing/navigation, projection restart recovery, literal sharing scopes, original workflow task/bug/idea folders, date-typo preservation, bounded reply audio, approval origin/single-use handling, and prior regression cases. Final whole-product verification remains required after firmware changes.
- Speech dependencies installed in an isolated host environment `/opt/catthew-speech/venv`, using existing `/usr/bin/python3.11`; Hermes dependencies were not changed.
- Public model artifacts are pinned by Hugging Face commit and SHA-256 manifests. Tiny English model benchmark had an inaccurate run. Selected **base.en int8** plus Piper **en_US-ljspeech-medium**, public-domain LJ Speech dataset; Piper library GPLv3 dependency is not vendored. 16 kHz output uses soxr resampling.
- Selected speech benchmark: load 2.22 s, TTS 0.15 s, STT 0.70 s, peak RSS 462.8 MiB, synthetic sentence accurately recognized. This is synthetic audio, NOT physical microphone or real-household quality validation.
- Speech candidates stored at `/opt/catthew-speech/models` (tiny) and `/opt/catthew-speech/models-base` (selected). Both new systemd services are enabled. Existing Caddy serves the added zectrix hostname with a valid public TLS certificate; unrelated sites were preserved.
- Authenticated HTTPS voice round trip succeeded: synthetic WAV → English STT → actual Catthew → text and 16 kHz speaker WAV (98,452 PCM bytes). This was a greeting/connection check and made no household-record changes.
- Authenticated HTTPS four-color frame now returns exactly 30,000 bytes, valid ETag, opaque next-page ID, and bodyless304 when unchanged. Live sources are healthy: 0 events, 13 active task/bug/idea records, 0 shared reference notes. Calendar access role is owner. These are read-only checks.
- Renderer uses indexed black00/white01/yellow10/red11 pixels and licensed, unmodified DejaVu fonts. Unicode previews and a public calibration/setup card are generated. Screen composition belongs on the VPS; the Note4C projects frames and owns controls/audio only. No listening/processing/clock-second screen refreshes.
- Attached Note4C identified by esptool 5.6: ESP32-S3 rev0.2, 8 MiB PSRAM, 16 MiB quad flash. Original full flash dumped and hardware verify-flash passed. Private status: `$HOME/.local/share/catthew-note4c/backups/<device>/status.json`; image is outside Git, 16,777,216 bytes, SHA-256 `5fdd603eb016137b4535ac9d169b58c4bf815580e6a3e0329b0e1431a93b6c41`. No firmware WRITE performed. Backup worker finished and reset the original firmware normally.

## Actual remote paths and runtime

Hermes container `hermes`, UID1500, host network. Named volume host `/var/lib/docker/volumes/hermes_hermes-data/_data` mounts at `/home/hermes/.hermes`. Vault host `/root/theduyvault` mounts at `/vault`.

- Deployed source: container `/home/hermes/.hermes/catthew-terminal`; latest backend and frame API are live. Existing MCP child processes may still hold older imported household code: reload the supported gateway once at the final tool deployment boundary and verify all adapters; do not silently patch Hermes.
- State/secrets: `/home/hermes/.hermes/catthew-terminal-state`, mode700. `terminal.env` mode600 contains dedicated device token and scoped profile API credential; NEVER print or copy these into Git or tool output.
- Scoped config tool: run from project cwd as `python -m tools.configure_catthew --root ... --project ... --python /home/hermes/.hermes/hermes-agent/venv/bin/python --state ... --apply`. Preserve the virtualenv interpreter symlink; resolving it loses site-packages.
- Private backups include manifests for root/profile config, both .env files and terminal.env. Latest applied backup: `.../backups/9c55872c52b14d2c84ca63afdec1a95a`. Initial untouched baseline backup: `.../backups/5b1e313341cf42c78015c0dff6e0f3f8`.
- Existing Caddy unit `caddy-photoframe.service`: `/usr/local/bin/caddy run --config /etc/Caddyfile`; reload supported. Added only the approved zectrix site; validated and gracefully reloaded. Original config SHA `a737813699948f13645d9b65b2405fa8c29370438f4c7197c7ad67c321c1cf21`, backup `/root/catthew-deploy-backups/Caddyfile-6799707536ee4a61a5833c4d7b717fb2`.
- Host systemd252: speech has 768M RAM/128M swap/150% CPU and loopback8791. Terminal serves loopback8790 through `deploy/run-terminal.sh`, entering Hermes mount/PID/network namespaces via native nsenter while retaining the terminal unit's own cgroup. **Do not revert to docker exec for daemon supervision:** its Python child survived docker-client stop and left stale code serving. Actual stop was verified to close8790, then restart restored live frames. Terminal also locks its state before recovery to prevent a second worker from reclassifying live requests.

## Current implementation and review

- `hub/journal.py`: durable requests, bounded queue/history/devices, crash recovery never repeats uncertain agent work, raw-audio deletion, reply audio TTL and acknowledgement. Delivered speech is terminal and cannot be resurrected by late synthesis.
- `hub/gateway.py`: private numeric-IP transport with no redirects/proxies, socket deadlines, SSE validation, run identity, exact profile sessions, per-turn native tool policy check.
- `hub/household.py`: exact tag-scoped reads, existing task fields, deterministic operation/task IDs, linked calendar writes, partial success reconciliation. Existing status is `completed`; links are `google_event_id` / `google_calendar_id`.
- Calendar adapter is fixed to configured calendar ID, rejects primary, uses exact quoted etags (no wildcard/list), preserves exclusive all-day dates, and serializes Google httplib2 access.
- Vault writes use native atomic file exchange (Linux renameat2/macOS renamex_np) and preserve displaced versions under the task directory's `.catthew-history`. Concurrent edit produces conflict without discarding versions. Archive is bounded and requires operator review when full; no silent destructive pruning. An already changed task is not reconciled from stale create arguments.
- `household_mcp.py`: ONLY reads, scoped create/complete, and prepare-proposal tools. No shell/path/calendar selector or direct calendar edit/delete/apply/approve tool. Preparation reads current event and binds exact etag/payload.
- `approvals.py`: private one-use random capabilities with 10-minute expiry, consumed BEFORE external mutation; interrupted mutation becomes uncertain and is not replayed. Notification has notifying→pending delivery state; interrupted/failed sends invalidate old capabilities and retry boundedly. Final retry transition regression fixed after two review passes.
- `terminal.py`: bounded authenticated WAV submission, asynchronous serial agent queue, persistent/rebuildable source cache with stale flags, paginated diagnostics, compact device state, conditional four-color frames, request status/audio/ack. Human approvals use URL fragments and POST bodies so capability secrets do not enter proxy URLs; Origin, CSP, escaping and one-use checks remain enforced. Machine identifiers stay off confirmation pages. Dead worker threads fail the service for supervised restart.
- `speech.py` / `speech_server.py`: private bounded STT/TTS, raw mic input in memory, thread/absolute body deadlines, recording limits, reuse existing positive TELEGRAM_ALLOWED_USERS for private approvals via Hermes send. Verification has not sent ad hoc Telegram messages; actual private delivery and user approval await the individually confirmed live test.
- Backend independent reviews: initial source/config review (4 findings fixed); terminal/approval review and re-review (notification recovery, audio ack race, slow-body resource issue, final failed-notification transition fixed with regressions). No final whole-product review claimed.

## Next concrete work

1. Commit and push the reviewed working backend/frame slice, with fresh gates and focused Linux checks. Verify the new supervised service and real HTTPS voice path with the provided helpers. Keep source-only rollback `/root/catthew-deploy-backups/app-before-frames.tgz`; retain fixed cgroup supervision when rolling code back.
2. Port the SSD2683 to the reference native2bpp sequence (E9:01, no monochrome OTP/LUT initialization), 120-second BUSY failure deadline, 400×300 BWRY. Implement a display worker separate from buttons and an exclusive audio owner for capture/cancellable playback.
3. Replace the obsolete local household model/screens/network protocol with authenticated TLS frame projection, compact asynchronous request status, fixed16kHz PCM reply streaming and delivery ACK. Provision Wi-Fi and device token through private NVS; no compiled credentials. Short press pages, hold talks, release sends; no approval gesture.
4. Build in public GitHub Actions using pinned ESP-IDF v6.1 image digest `sha256:81893c71bb5e570088901f21def8684c25cd2a9020281bd01b843a7655edb18c` and standard free Linux runner. The image exists and Actions is enabled on the public fork. Avoid local SDK installation (~2GiB Mac free) or further load on the small VPS.
5. Verify factory backup again before any flash. Provide a setup wizard for private Wi-Fi entry and physical color/button/microphone/speaker checks; do not read Mac keychain. No firmware write has happened yet.
6. Use the individually confirmed test record for actual task/event creation, private approval, cleanup, source sharing with Telegram/CLI, reconnect/restart and Mac-off checks. Then whole-branch independent review, fresh verification, documentation and draft PR update; no automatic merge.

## Rollback and limits

Stop only new terminal/speech services; remove only this Caddy site and reload after validation. Restore specific profile integration settings from private manifests if needed, without replacing unrelated services or healthy family source data. Preserve user-selected ChatGPT and unchanged SOUL unless that specific change caused a verified failure. Restore original full device image if authorized/needed after a failed flash. Never roll back the entire vault/calendar or delete real records to undo software.

Public HTTPS voice and frame routes are live. No firmware write exists yet. Calendar/vault writes have been exercised with fixtures only; live calendar GET/owner access and actual ChatGPT inference are verified. No family records were created/edited/deleted during verification. Remaining major work: actual color firmware, physical acceptance, individually confirmed live write/approval checks, final review and PR completion.
