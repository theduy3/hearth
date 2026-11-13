# Note4C source review checkpoint

Reviewed snapshot: `a053e1f`; corrections independently rechecked at `41c302d`. Base: `edd75fd7ea7e9879b141a84aa39ce2c74b6c92bc`. Reviewers were read-only and had no access to credentials, cloud actions or hardware. Parent verification supplies test/build/deployment evidence separately.

## Standards

No hard violation of the supplied modularity, obsolete-path removal, credential or lifecycle standards was established in the inspected source.

One substantive validation-ownership finding was reported: calendar create/edit repeated interval validation, while approval proposals checked each timestamp separately. Mixed date/timed or non-increasing intervals could become private confirmations, only to fail locally after spending the capability. Fixed at `41c302d` with the shared `event_interval()` validator used before proposal persistence and before calendar writes. A regression test was observed failing, then passing for equal/reversed/mixed intervals with no proposal left pending. Reviewer recheck confirms resolution and found no introduced concrete bug in the changed files.

Coverage was selective across the large diff: journal, gateway, household/calendar, approval store, MCP boundary, renderer, firmware main/config/network/audio, configuration helper and selected terminal paths/tests. This is not a claim that every line or firmware interleaving was independently exercised.

## Spec

Two findings were reported and independently confirmed resolved at `41c302d`:

1. **P2:** completed text presentation waited for TTS readiness/failure. The approved plan requires completed text to remain available independently of TTS. Firmware now selects the reply page on completed status, including pending speech. Playback retains a separate ready-audio condition and the existing cancellation/replay exclusions.
2. **P3:** protocol documentation called the intermediate recognition state `stt`; production uses `transcribing`. Documentation now matches the journal.

No concrete P1 or unrequested scope creep was established within reviewed paths. Coverage included native BWRY projection, navigation, audio cancellation/ACK, upload identity/retries, approvals, household scope and runtime credentials. Reviewer recheck found no introduced concrete bug in the correction.

## Focused voice correction review

A separate read-only reviewer inspected9fd1f98 and found no concrete P1/P2, privacy, lifecycle or contract bug. Matching requests use the polling policy independently of the completed-text processing flag, preserving500ms polling while speech is pending. The boundary regression checks the actual pure policy; it does not establish real network/task/playback timing. Joe selection and pinned-manifest validation were checked, and added timing output excludes transcripts/replies/tokens. SDK build,108 Linux host tests, hardware flash verification and network readiness were observed separately. User confirmation of perceived latency and the new voice remains necessary.

## Current grocery/event and request-routing review

Independent read-only review of the initial grocery/event change found two P2 issues: timed events accepted date-only end values, and regex-only grocery parsing treated comments/code examples as items while appends could be hidden by open Markdown boundaries. Both were reproduced and fixed. Follow-up review found that source-staleness warnings suppressed uncertain-request warnings after removal of the chat page; request uncertainty now takes priority, with a combined saved-data warning and regression coverage.

The subsequent user-requested09d1fa2 increment limits Tasks to the local day, excludes grocery records, removes the empty grocery prompt and introduces a typed, per-request page directive. Self-review checked active Note4C request scoping, bounded journal history, completion-before-publication, fresh projection-before-completion, enum validation, once-per-request firmware navigation and independent audio ownership.137tests, Linux CI, pinned SDK compile, identity-checked flash, network readiness and actual backend task-speech routing passed. Actual model invocation of the new grocery read also succeeded without live test items.

The final self-review also reproduced local-date underflow and all-day exclusive-end overflow at datetime boundaries. Both parsers now fail closed, and the today-only rendering regression covers these cases so an extreme date cannot block the page or household projection.

Fresh independent review of this final routing increment remains unavailable: the review service failed with upstream502 before doing any work, and a no-tools CLI fallback failed with invalid_params. Those attempts provide no review evidence. Keep G7 open and PR1 draft; do not claim an independent whole-branch review of the final routing increment. Physical button/speaker/refresh and a real grocery-write pilot remain separate acceptance.

## Historical two-screen display review

Focused read-only review found no concrete renderer/layout/spec/privacy defect in the exact2screen change. It identified a verification false positive from substring matching a model path; this was corrected by reading actual service process arguments, requiring exact paths and base.en repository, and verifying model.bin against the pinned manifest. New tests reject path suffixes, wrong repositories, unverified hashes and voice suffixes. Reviewer independently rechecked the finding resolved; all115 host tests and fresh live VPS checks pass. Selection evidence does not claim new runtime precision introspection; existing SpeechEngine still configures int8. Physical panel/gesture results remain separate acceptance.

## Remaining acceptance

Source review does not establish panel colors, microphone/speaker behavior, human gestures, real private notification/confirmation, shared live-record behavior or Mac-independent operation. Those remain explicit G5/G6 acceptance gates. No live family records were mutated by automated verification. The PR remains a draft and must not be merged automatically.
