# Approved implementation progress

Approval: canvas verdict fb-65 (Approve), followed by user message "approved plan". Source plan: `docs/CATTHEW-NOTE4C-PLAN.md`.

Workspace: `/Users/theduy/Repo/hearth-catthew-note4c`; branch `feat/catthew-note4c`; base `edd75fd7ea7e9879b141a84aa39ce2c74b6c92bc`; fork remote `https://github.com/theduy3/hearth.git`. PR target: fork main, no automatic merge.

## Acceptance inventory

Real four-color Note4C output; front hold/release speech and short-press navigation; English STT and TTS on VPS; both text and spoken answers; existing Catthew SOUL and verified ChatGPT sol6.1; persistent separate device session; calendar Kittyggup Family in America/Vancouver; catthew tasks and kittyggup reference notes; shared Telegram/CLI source records; enforced household tool scope; explicit approvals for event edits/deletions and unrelated actions; authenticated zectrix.theduy.cloud; durable request/retry reconciliation; flash backup/recovery; Mac-independent runtime; reviewed fork PR.

## Sequenced commit boundaries

1. Preserve approved design, baseline and acceptance ledger. DONE: clean isolated baseline 59 tests passed. Fork created. Design and ledger commit `d2dfa18`.
2. Add durable request journal and gateway API client with loopback fake-server tests: SSE parsing, stable session headers, approval/run IDs, no auto retries, incomplete-stream outcome, bounded response/errors. IMPLEMENTED and passing focused tests; not yet integrated with the production hub. Review corrections cover redirects, error frames, required run identity, stream deadline, recording erasure, bounded dedupe history. Integration remains behind the household tool-policy boundary.
3. Replace standalone mutable board/profile subprocess with household projection and authenticated terminal API; remove obsolete profile installer and tests along with callers. Add scoped calendar/vault tools and enforce policy at their boundary. Focused mock integration tests, then regression.
4. Add private STT/TTS service interfaces and deployment artifacts; benchmark against VPS before final engine/resource settings. Do not change model/provider by guessed ID.
5. Port renderer/driver/simulator to BWRY; separate display refresh from event dispatch; TLS/device provisioning and reply playback; host tests then ESP-IDF build.
6. Back up verified device; provision and flash only a build that passes checks. Deploy scoped services without replacing unrelated services. Exercise live acceptance with clearly identified test data.
7. Independent whole-branch review, fresh checks, focused commits, push fork branch and open PR. Report exact completed/unmet gates and any blocker honestly.

## Prerequisite investigation and blockers

Read-only prerequisite agent `474fc092-acd8-4a5` completed; no remote mutations or credential contents were exposed.

- BLOCKER: Catthew's installed `resolve_codex_runtime_credentials(read_only=True)` raised `AuthError`. No usable ChatGPT/Codex identity was resolved. Model metadata includes `gpt-6.1-sol`, but account entitlement and the user's intended active connection are unverified. Do not create/sync credentials or silently use Grok.
- BLOCKER for public deployment: `dig` reports NXDOMAIN for both A and AAAA of `zectrix.theduy.cloud`. Parent domain nameservers are Cloudflare. DNS management access was not established.
- Calendar read succeeded against the configured family calendar: zero returned events for the sampled upcoming window. Event contents and calendar ID were not printed; write access remains untested.
- Existing API adapter is unconfigured and its default listener unavailable. API keys were absent in inspected config sources; no key was created.
- API platform toolsets can exclude native execution tools; explicit MCP allowlisting or `no_mcp` is necessary to avoid implicit broad MCP access. A narrow household tool/service must own fixed calendar/vault scope and enforce approvals before mutation; existing helper alone does not.
- Existing Caddy owns 80/443/8443; reuse its route configuration rather than start a conflicting proxy. No routes were changed.
- No STT/TTS binary found on inspected PATHs. VPS has two CPUs and limited spare memory; no model installed or benchmark claimed.

Resume prerequisites: connect/identify the user's ChatGPT/Codex account for this Catthew profile and verify its catalog; establish DNS management. Then finish scoped household tools and integration before enabling ingress or flashing.

## Current review and evidence

Independent review agent `2de817f2-ac42-48c` reviewed the complete new modules twice. Findings were fixed with negative regression tests. The second pass's remaining issues were addressed by private numeric-IP transport (no DNS resolution), rejecting error events before the completion sentinel, and bounding device registrations. Fresh gate execution passes; no final product review or live integration is claimed. Code graph review returned zero indexed changed symbols, so its zero risk score was not used as evidence.

## Known constraints

No ESP-IDF or esptool executable currently on PATH; uv available. Gateway default API listener unavailable at prior inspection. Saved model file may be stale relative to user-selected ChatGPT sol6.1. Existing API does not establish per-session serialization or streaming idempotency. VPS RAM is constrained. Exact household enforcement must be established before any device ingress is enabled.

## Current evidence

- Original and isolated baseline: 59 passing tests before changes; fresh full regression with new tests: 81 passing. Gate G1 reverified successfully.
- Journal: 10 focused tests; gateway: 12 focused tests. Gate G2A reverified successfully. RED observed for missing modules and introduced regression controls before fixes.
- Gateway transport deliberately accepts a private numeric IP origin, avoiding blocking DNS resolution and retaining a single connection deadline. Deployment must provide the gateway's actual private/loopback IP; HTTP redirects and environment proxies are never used.
- SQLite uses DELETE journaling + secure_delete. Reply/error text redacts after seven days; raw/reply audio expires within 24 hours when maintenance runs. Maximum 10,000 request records fails closed, preserving deduplication instead of silently forgetting old IDs. These policies are local implementation defaults; services are not running yet.
- Fork: https://github.com/theduy3/hearth
- No remote config edits, live agent turns, calendar/vault writes or flashing performed.
