# Approved implementation progress

Approval: canvas fb-65 and user message “approved plan”. Source of truth: `docs/CATTHEW-NOTE4C-PLAN.md`.

Workspace: `/Users/theduy/Repo/hearth-catthew-note4c`, branch `feat/catthew-note4c`, base `edd75fd7ea7e9879b141a84aa39ce2c74b6c92bc`. Fork: https://github.com/theduy3/hearth. Draft PR: https://github.com/theduy3/hearth/pull/1. No automatic merge.

## Verified delivery checkpoint

- Latest correction `41c302d` passes both SDK/native build and105 Linux host tests in [run43364193431](https://github.com/theduy3/hearth/actions/runs/43364193431). That artifact was reflashed without NVS erasure and all written regions verified. USB remains configured=false; private current log is `builds/41c302d/flash.log`. Firmware app SHA256: `d3519e1abf36059b60b31296b3def9a07ba41183356c00a8aad3ffc62208bcad`.
- Backend checkpoint `3776740`, projector firmware `ec40016`, lifecycle fixes `b20ab90` and provisioning/build recovery `d3acefa` were pushed.
- [Firmware run43360727456](https://github.com/theduy3/hearth/actions/runs/43360727456) built source `d3acefaaa294c93e97128c94b0afe5939f6ea1db` successfully with the digest-pinned ESP-IDF6.1 image. cJSON is an explicit pinned managed component; no compiled Wi-Fi or token settings.
- The actual backed-up Note4C was flashed from that artifact. Bootloader, partition table and application all passed hardware verify-flash. Local private log: `$HOME/.local/share/catthew-note4c/builds/d3acefa/flash.log`. USB application protocol answers with the expected MAC and `configured=false`.
- Full original flash remains private,16,777,216 bytes, SHA256 `5fdd603eb016137b4535ac9d169b58c4bf815580e6a3e0329b0e1431a93b6c41`; original hardware comparison and fresh local checksum/permission verification pass. No credentials have been provisioned yet.
- Current host suite: **105 tests pass in Linux CI** after deleting the obsolete standalone board/LAN/model/simulator stack and its dedicated tests. The current button timing coverage was preserved as a standalone native test. Immediately before that removal, all147 tests plus4 provisioning tests passed.
- `tools/setup-note4c.sh` passes `bash -n`. Provisioning tests verify identity before credential retrieval, capture SSH output privately, ignore serial echoes and emit only setup status.
- VPS release check passes: HTTPS/auth, exact30,000-byte frame/hash, next/previous headers, selected model/provider, unchanged SOUL, household tool policy, Catthew Telegram, speech, active units and exactly one terminal process owned by its service.
- Fresh post-reload synthetic voice request `2f8898cfdeed461587016d5c260c46c8` passed HTTPS→STT→Catthew→text/audio at16kHz with98,452 PCM bytes. It was a read-only greeting and changed no family records.

## Architecture and reviewed behavior

The VPS owns household data, English STT/TTS, agent calls and Unicode BWRY rendering. Device owns authenticated TLS, runtime NVS settings, buttons, exclusive codec ownership and immutable frame projection. It has separate display, audio, audio-download and network tasks; no recording/processing/clock-second panel refresh.

- Native packed BWRY:400×300; black00/white01/yellow10/red11; four pixels/byte, leftmost bits7–6, exactly30,000 bytes. Full refresh only with native sequence and bounded120-second BUSY cycle. Actual-driver trace tests cover commands, byte order, timeout, failure power-off and retry.
- Front hold records after a steady ready indicator, release submits, short press pages. Separate display owner coalesces navigation. Audio playback can be cancelled without waiting for its network reader. Only AudioTask owns codec teardown, including shutdown.
- Playback ACK follows complete valid WAV, successful speaker writes and drain. Failed transfers retry at most3 times with backoff and per-attempt IDs; explicit dismissal and played IDs remain excluded. Raw upload retries retain one client ID/audio body and expire; lost acceptance is reconciled.
- Provisioning validates complete settings, quiesces audio/display, cancels network work, gates NVS writes, and reboots after confirmed or failed save. Invalid input is rejected without quiescing a working device. Task/queue allocation failures restart before accepting dependent controls.
- Firmware reviewer found six lifecycle/resource findings; fixes were independently rechecked. A further failed-provisioning recovery issue was fixed in `d3acefa`. No partial/wrong-playback ACK path was found by that review. Whole-branch Standards/Spec source review and focused correction rechecks are complete; see `docs/NOTE4C-REVIEW.md` for coverage limits.
- Journal durably deduplicates, bounds queues/history/device count/audio budget and never replays an uncertain agent turn. Reply audio expiry/eviction retains textual results and dedupe identity.
- Household scope preserves Catthew SOUL and uses `openai-codex` / `gpt-6.1-sol`. `catthew` tasks include existing tasks/bugs/ideas; `kittyggup` reference notes span the vault. YAML date mistakes remain visible; symlinks are rejected. Calendar is fixed to Kittyggup Family in America/Vancouver.
- Calendar proposals bind exact quoted etag and payload; private one-use capability travels in a URL fragment then same-origin POST. Notification recovery invalidates/remints interrupted capabilities; mutation uncertainty is not replayed. Buttons/model cannot approve calendar edits/deletions.

## Production layout and supervision

Hermes container `hermes`, UID/GID1500, host networking. Host volume `/var/lib/docker/volumes/hermes_hermes-data/_data` mounts at `/home/hermes/.hermes`; vault host `/root/theduyvault` mounts at `/vault`.

- Application: `/home/hermes/.hermes/catthew-terminal`; profile: `/home/hermes/.hermes/profiles/catthew`.
- State: `/home/hermes/.hermes/catthew-terminal-state`, mode700; `terminal.env` mode600. Never print, commit or include its credentials in arguments.
- Selected profile SOUL SHA256 remains `4ef56b0716db7006c89862fa9019c430d6b7b7a93b0b058c682f46615e2702f0`.
- Terminal on loopback8790; speech on loopback8791 in `/opt/catthew-speech`, selected models `/opt/catthew-speech/models-base`. base.en int8 + Piper en_US-ljspeech-medium with16kHz resampling. Measured speech peak approximately681MB; service limited to768MiB RAM/128MiB swap/150% CPU.
- `catthew-terminal.service` uses `/usr/local/libexec/catthew-terminal` from `deploy/run-terminal.sh`: native nsenter retains systemd cgroup while entering the container namespaces. Do not supervise the daemon through `docker exec`; that previously left a stale child serving after stop. State lock is acquired before recovery.
- Caddy unit `caddy-photoframe.service`, `/etc/Caddyfile`. Only `zectrix.theduy.cloud` was added, with valid HTTPS; unrelated routes preserved. DNS-only A→129.121.100.233; no AAAA.
- Private profile/config backups retain manifests, including `.../backups/9c55872c52b14d2c84ca63afdec1a95a`. Source rollback archives include `/root/catthew-deploy-backups/app-before-frames.tgz` and state `backups/app-before-device-protocol.tgz`. Preserve corrected service supervision when reverting source.
- Gateway container reload completed; sequential Telegram initialization took about2minutes before the API listened. `/health` and `/p/catthew/health` then returned200; policy and voice checks passed. Runtime-recommended reload: `docker exec -u1500 hermes hermes -p default gateway restart`. The last invocation eventually cycled the container, interrupting an in-flight synthetic smoke test (exit137) and briefly causing502; terminal supervision recovered and fresh G1/G2/G4/G5A then passed. Wait for actual stable readiness and avoid active device turns during reload.
- Discovered existing entrypoint inefficiency: obsolete per-profile launch loops coexist with the new multiplex runtime and retry harmless “already serves profile” exits. No entrypoint modification is included in this delivery; the one host gateway serves the named profiles. Treat startup readiness separately from stale gateway_state data.

## Remaining work and human boundary

1. Draft PR1 is updated with source review, build/flash evidence and pending G5/G6. Preserve this workspace; the next required input is human pairing/physical acceptance.
2. User runs `./tools/setup-note4c.sh`: physically confirms labeled B/W/R/Y patches, privately enters Wi-Fi, checks English voice, navigation/interruption, and fresh voice delivery while Mac sleeps and Note4C uses wall power. The assistant cannot establish physical color/microphone/speaker correctness from software previews or synthetic speech.
3. Run the individually confirmed live test record for task/event creation, private approval/edit/delete, cleanup, shared Telegram/CLI reads and restart/reconnect. No actual family record has been created/edited/deleted during verification so far. Pairing does not authorize those mutations.
4. Fresh final product gates/review, PR update, authorized workspace preservation and durable finalization. Keep PR unmerged. Do not declare whole-product completion while human/live gates remain pending.

## Rollback limits

Restore only affected app/config/service/device state from recorded backups. Keep SOUL and selected model unless implicated in a verified failure. Never restore the entire vault/calendar or delete real records as software rollback. Preserve healthy unrelated services. The original full device image is available privately if an authorized hardware rollback is needed.
