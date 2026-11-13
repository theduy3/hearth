# Note4C projector protocol

The VPS owns Catthew, household integrations, layout, Unicode fonts and speech. The Note4C owns physical controls, microphone/speaker, encrypted transport, cached pixels and native SSD2683 refresh. It contains no family task database or agent persona. Changing the Python layout does not require a firmware update.

All `/v1/*` requests require the dedicated `Authorization: Bearer …` device credential. It is provisioned privately into NVS, never compiled or committed. HTTPS certificate and hostname verification are mandatory; synchronize time before TLS. Do not follow redirects with credentials.

## Frames and navigation

`GET /v1/frame?page=today` returns `application/vnd.catthew.bwry2`, exactly30,000 bytes: 400×300, row-major100 bytes/row, leftmost pixel in bits7–6. Indices are black00, white01, yellow10, red11. Thus black/white/red/yellow pack as `0x1e`; solid black/white/yellow/red are `00/55/aa/ff`.

Headers: quoted `ETag` is SHA256 of the body; `X-Hearth-Page` is the resolved opaque page ID; `X-Hearth-Next` and `X-Hearth-Previous` are neighboring IDs; `X-Hearth-Pages` is always2: `today` is the daily task screen, `groceries` is the Grocery Shopping screen. Both next and previous point to the other screen. Each screen is a bounded preview; long lists never create additional pages. IDs are bounded32-character ASCII values. Send `If-None-Match` only for the matching cached page; unchanged frames return304 with no body. A removed page resolves to Today. Replies use audio only. Unrelated chat never changes the selected page; explicit task and grocery requests can select their corresponding screen.

The front short press advances pages; side up/down navigate previous/next. Buttons never approve actions. A recognized hold records until release or30seconds; an empty/short recording is not converted into a page turn. Give immediate indicator feedback; steady illumination means capture is ready.

Use one display task, immutable buffers and a bounded latest-frame mailbox. Coalesce navigation during a full refresh; never repaint for listening, uploading, processing or clock seconds. Commit displayed metadata only after successful refresh. Native four-color refresh uses the reference E9:01 path, no monochrome OTP/LUT initialization, and a120second active-low BUSY deadline. Timeout is failure, with panel power safely removed.

Preserve the last frame during outages. Its reserved footer rectangle x304..383/y280..295 holds the80×16 OFFLINE badge (320 packed bytes). Keep an unmodified base frame so reconnect can remove the badge even when the server content ETag is unchanged. NVS cache writes must not interrupt live audio DMA.

## Voice and delivery

`GET /v1/device` is compact JSON: `request` is null or contains `id`, `client_id`, `status`, `speech_status`, `error`, `created`, plus `page`: an empty string, `today` or `groceries`. A page directive is recorded by `note4c_show_page(request_id, page)` only while that exact Note4C request is processing, and published only after the household projection has refreshed and the request has completed. Apply it once per request; otherwise retain the current page. Large source lists and reply text are rendered on the VPS, not parsed by firmware.

`POST /v1/utterance` accepts mono signed16bit little-endian16kHz WAV up to30seconds. Set `Content-Type: audio/wav` and a stable `X-Hearth-Request-Id`. Preserve that upload ID and identical bytes across transport retries; conflicting reuse is409, capacity is429. Acceptance is202 with `request_id`. This is not a successful household action.

`GET /v1/requests/<32hexid>` exposes durable status. States: queued, transcribing, processing, completed, failed, uncertain. Never automatically resubmit uncertain agent work. The device can reconcile a lost acceptance response using the compact request's `client_id`.

When completed, apply a nonempty page directive once, independently of speech readiness. When speech is ready, independently fetch `/v1/requests/<id>/audio`. It returns a canonical44-byte PCM WAV header followed by mono16kHz signed16bit little-endian PCM, at most4MiB total. Validate header, length, rate, alignment and exact completion; preserve split samples across network reads. One audio task exclusively owns the codec. A hold cancels playback before capture; a separate bounded audio network reader must not delay capture readiness.

POST exactly `{}` to `/v1/requests/<id>/audio-ack` only after the entire reply has played and output DMA has drained. Persist the last played request ID to avoid replay after reboot. Interrupted or failed playback is not acknowledged. Ready audio is temporary: ACK,24hour expiry or the32MiB aggregate audio budget removes it; request outcomes remain independently journaled.

## Private approvals and operations

The model exposes proposal-only calendar edit/delete tools. Private Telegram links use `/approval/#<capability>`; browsers remove the fragment and send the secret only in same-origin POST bodies. No capability is provided to the device or model. One-use consumption precedes the exact etag-guarded calendar mutation.

The terminal daemon uses the existing Hermes namespaces and UID1500 while retaining its own systemd cgroup through native nsenter. Do not supervise it with docker exec: stopping that client leaves its Python process alive. `terminal.lock` prevents competing workers. The speech process has its own bounded systemd environment. All runtime remains on Bluehost when the Mac is off.
