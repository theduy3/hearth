# Approved implementation progress

Approval: canvas verdict fb-65 (Approve), followed by user message "approved plan". Source plan: `docs/CATTHEW-NOTE4C-PLAN.md`.

Workspace: `/Users/theduy/Repo/hearth-catthew-note4c`; branch `feat/catthew-note4c`; base `edd75fd7ea7e9879b141a84aa39ce2c74b6c92bc`; fork remote `https://github.com/theduy3/hearth.git`. PR target: fork main, no automatic merge.

## Acceptance inventory

Real four-color Note4C output; front hold/release speech and short-press navigation; English STT and TTS on VPS; both text and spoken answers; existing Catthew SOUL and verified ChatGPT sol6.1; persistent separate device session; calendar Kittyggup Family in America/Vancouver; catthew tasks and kittyggup reference notes; shared Telegram/CLI source records; enforced household tool scope; explicit approvals for event edits/deletions and unrelated actions; authenticated zectrix.theduy.cloud; durable request/retry reconciliation; flash backup/recovery; Mac-independent runtime; reviewed fork PR.

## Sequenced commit boundaries

1. Preserve approved design, baseline and acceptance ledger. DONE: clean isolated baseline 59 tests passed. Fork created. Design and ledger commit pending.
2. Add durable request journal and gateway API client with loopback fake-server tests: SSE parsing, stable session headers, approval/run IDs, no auto retries, incomplete-stream outcome, bounded response/errors. RED then GREEN. Integrate only after tool-policy prerequisites are established.
3. Replace standalone mutable board/profile subprocess with household projection and authenticated terminal API; remove obsolete profile installer and tests along with callers. Add scoped calendar/vault tools and enforce policy at their boundary. Focused mock integration tests, then regression.
4. Add private STT/TTS service interfaces and deployment artifacts; benchmark against VPS before final engine/resource settings. Do not change model/provider by guessed ID.
5. Port renderer/driver/simulator to BWRY; separate display refresh from event dispatch; TLS/device provisioning and reply playback; host tests then ESP-IDF build.
6. Back up verified device; provision and flash only a build that passes checks. Deploy scoped services without replacing unrelated services. Exercise live acceptance with clearly identified test data.
7. Independent whole-branch review, fresh checks, focused commits, push fork branch and open PR. Report exact completed/unmet gates and any blocker honestly.

## Active investigation

Read-only prerequisite agent `474fc092-acd8-4a5`: effective model identifier, Google access, API adapter config/auth presence, API tool boundary/approvals, DNS/ingress, available speech tooling/resources. No tokens exposed and no remote mutations authorized to this agent.

## Known constraints

No ESP-IDF or esptool executable currently on PATH; uv available. Gateway default API listener unavailable at prior inspection. Saved model file may be stale relative to user-selected ChatGPT sol6.1. Existing API does not establish per-session serialization or streaming idempotency. VPS RAM is constrained. Exact household enforcement must be established before any device ingress is enabled.

## Current evidence

- Original and isolated baseline: `python3 -m unittest discover -s tests -v`: 59 passing tests.
- Fork: https://github.com/theduy3/hearth
- No remote config edits, live agent turns, calendar/vault writes or flashing performed.
