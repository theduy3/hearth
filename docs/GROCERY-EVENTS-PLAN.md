# Event completion and shared Grocery Shopping page

Latest user requirement: exactly two physical screens, **Tasks → Grocery Shopping**, with voice-only replies that leave the selected page in place. No chat page or extra pagination. Preserve Whisper base.en int8, Terra, Piper Joe, existing identity, private calendar approvals and device pairing.

## Authorized household changes

Sea Star closure notes are legacy `type: task` records. Add explicit `kind: event` while preserving type, dates, source, tags, calendar identifiers and body. Only explicitly classified, nonrecurring events expire: all-day events at their exclusive local end (next local midnight when no end is supplied), timed events only at a timezone-aware datetime end. Ordinary overdue tasks, including calendar-linked tasks, remain open.

Authorized classification targets are pending closures dated 2026-09-30, 2026-10-12, 2026-11-11 and 2026-11-20. Re-read exact current paths, revisions, source and metadata before writing. Complete the first three; keep November 20 pending. Preserve completed August/September records. Use existing atomic exchange, locks and history. No Google Calendar mutation.

Preserve cancelled `/vault/Tasks/tasks/grocery-list.md` and its five items. The new canonical list is `/vault/Tasks/tasks/grocery-shopping.md`, created on the first real addition, with `type: grocery-list` and exact frontmatter catthew/grocery tags. Begin empty; no fabricated live groceries. Actual Markdown checkboxes are authoritative; comments/code examples are ignored. Stable hidden item IDs make additions idempotent, exact full-note revisions guard updates, and purchased items remain available for reuse. Text, item count, file size, symlinks and unresolved Markdown boundaries are guarded.

## Implementation and delivery

1. Household storage provides explicit event expiry, shared grocery read/add/update/check, existing atomic writes and private history. Ordinary task/calendar contracts remain intact.
2. Scoped MCP exposes `household_grocery_read`, `household_grocery_add` and `household_grocery_update`. Calendar edits/deletions retain private one-use approval.
3. Terminal periodically completes known elapsed events and refreshes grocery records after voice turns; MCP reads do not mutate. Grocery data joins the derived offline cache.
4. Renderer provides only `today` and `groceries`, with bounded previews and visible-pixel ETags. Replies are spoken. Compact request, speech, data-source and approval warnings remain visible.
5. Firmware removes automatic navigation to the answer page. Existing independent capture/playback ownership, retry bounds, fast status polling and full-playback acknowledgement remain unchanged. Build using pinned CI and flash only verified regions with identity checks and NVS preserved.
6. Deploy source with private backups and an idle request journal. Refresh only the household MCP child using its supervised reconnect lifecycle; verify actual updated discovery and a read-only grocery call. Do not restart the whole gateway/container. Verify public two-page navigation, grocery state, corrected Sea Star records, unchanged cancelled list, model/SOUL/security and selected speech stack. Update the existing draft PR; no merge.

## Gates

- [x] E1: Event expiry and ordinary-task/recurrence preservation regressions pass, including rejection of date-only ends on timed events.
- [x] E2: Temporary-vault and MCP handler tests cover grocery additions/edits/check-offs, retries, conflicts, symlinks, metadata authorization, Markdown context and readable size limits.
- [ ] E3: Final two-screen contract, voice-only behavior, previews and pinned firmware build/identity-checked flash verified.
- [ ] E4: Final review/full suite, live MCP discovery, public pages/status/security, authorized Sea Star corrections, commit/push and draft PR updated.

Local validation before the final two-screen change: 131 tests passed. Log `/tmp/catthew-grocery-tests.log`; interpreter `/Users/theduy/.local/share/catthew-note4c/test-venv/bin/python` (Python 3.14.7 with markdown-it-py 4.3.0). Requirements declare markdown-it-py >=3,<5. Prior P2 review findings were reproduced and fixed; follow-up review is running.

MCP research: attach read-only to the existing owner using `discover_gateway_endpoint(profile_home).endpoint` and `connect_gateway(endpoint=...)`; the discovery wrapper itself is not an endpoint. `reload.mcp` only reconciles config and leaves unchanged healthy servers alive. `tools/mcp_tool_server_run.py:329–473` supervises transport drops with reconnect/backoff and rediscovery. Validate a new household child PID and actual tool visibility after a scoped restart. Do not assume a fresh standalone process proves the active model's catalog.

Rollback: restore backed-up code and verified prior firmware if necessary; preserve pairing, records, history and concurrent edits. Never resurrect cancelled groceries. No force push, merge, paid service, VPS upgrade, credentials or unrelated calendar mutation is authorized.
