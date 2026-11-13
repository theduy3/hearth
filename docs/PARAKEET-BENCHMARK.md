# Parakeet Unified English Q8_0 on Bluehost

## Outcome

The requested candidate was downloaded, verified and tested successfully. It is **not active**: it measured slower than the existing Whisper base.en int8 recognizer on this VPS and used substantially more resident memory. Existing Whisper/Joe services were restored and verified. Activating Q8 despite these results is a product/resource tradeoff requiring user direction; do not treat preparation as a completed backend migration.

## Pinned candidate

- Model: `handy-computer/parakeet-unified-en-0.6b-gguf`, revision `843b1b175ace04f5a89d379c79e2518c0d065b25`.
- Artifact: `parakeet-unified-en-0.6b-Q8_0.gguf`,731357568bytes, SHA256 `4b50b6dd862bf6e346929aaf4f5eaacec003bfa3f56462d6c874b41ef2f38795`.
- Installed model directory: `/opt/catthew-speech/parakeet-q8`; manifest covers model, LICENSE, NOTICE and model card. License: NVIDIA Open Model License.
- Runtime: `transcribe-cpp==0.4.2` and `transcribe-cpp-native==0.4.2`, installed with binary-only and hash verification from `deploy/requirements-parakeet.txt`. Native manylinux2.27/2.28 wheel runs on host glibc2.34 and selected its CPU zen4 backend. No production compilation, PyTorch/NeMo/CUDA SDK, paid service or VPS upgrade.

## Measurement

Host has2vCPUs,3.8GiB RAM and existing swap pressure. Both engines used2threads and a150% CPU quota. Synthetic fixtures were generated once through the existing Joe voice at16kHz mono PCM16, then reused byte-for-byte. No family recordings, model/agent calls or household writes were used for this comparison.

| Audio | Whisper samples, seconds | Whisper warm median | Parakeet samples, seconds |
|---|---|---:|---|
| Short greeting,3.425s |0.684,0.472,0.409|0.441|1.883,1.905,1.310|
| Longer sentence,10.704s |0.690,0.900,0.884|0.892|1.797 (one sample)|
| Narrative,27.527s |3.716,1.782,1.667|1.725|5.955 (one sample)|

"Warm median" excludes the first sample. Parakeet's second/third short samples have median1.608seconds, about3.6times the Whisper warm median. Longer Q8 cases are single measurements, not warm medians or general performance guarantees. Baseline went through loopback HTTP; Q8 used the resident native Python session directly, excluding HTTP and PCM conversion from its reported inference time. This favors Q8 in the comparison. Host load can vary; this is not a population benchmark or a full-device latency measurement.

Q8 model/session initialization took1.298seconds; `ru_maxrss` peaked1004.8MiB for recognition alone, including memory-mapped model pages. This is not all private memory and is not directly equivalent to cgroup charge. The restored combined Whisper/Piper process later showed340.4MiB high-water RSS. Existing production service has a768MiB memory limit. Q8 plus Piper has not been proven suitable within that budget.

The Q8 trial ran under a temporary isolated DynamicUser unit, CPU150%,1GiB memory/64MiB swap ceilings and35s runtime deadline. Trial completed successfully in14.54seconds. The reported systemd memory peak was inconsistent with process RSS; use process high-water RSS rather than interpreting the systemd summary as a1MiB workload.

## Safe trial and restoration

Before maintenance, a read-only journal query confirmed no queued/transcribing/processing or pending-speech requests. Terminal and speech services were paused to avoid loading both recognizers simultaneously; a shell EXIT trap restarted speech, waited for its health endpoint, then restarted the terminal. Device credentials, conversation journal, profile/SOUL, Terra selection, vault and calendar were untouched.

Two initial starts failed before model execution because passing a redirected regular log file through `systemd-run --pipe` caused a D-Bus peer-disconnection error on this host. A harmless `/usr/bin/true` positive/negative control reproduced the file-descriptor issue. Running with the SSH output stream succeeded; the failed starts restored the original services too. Do not redirect the remote `--pipe` output to a regular file; capture it outside that call if needed.

After the successful trial, actual loopback transcription and Joe16kHz speech synthesis passed. All111 host tests and all `tools.verify_vps` checks passed, including Terra/provider, unchanged SOUL, household policy, speech, male voice selection, authenticated frames/TLS, Telegram and owned supervision.

## Reproduction and next step

Current baseline fixtures/results and trial scripts are private under `/root/catthew-parakeet-benchmark-v2`; public synthetic copies for the sandbox are under `/opt/catthew-speech/benchmark-v2`. `tools/benchmark_speech.py` now benchmarks a running loopback service with reusable public synthetic fixtures. The old repeated-sentence maximum-length fixture was replaced by a varied narrative before the comparison above; repeated text can trigger Whisper compression-ratio fallback and distort performance comparisons.

The published runtime API is `transcribe_cpp.Model(path,backend="cpu")`, one lifetime `model.session(n_threads=2)`, repeated `session.run(float32_mono,timestamps="none").text`. It accepts standard-library `array('f')`; decode/validate PCM16 first. Preserve the existing service request serialization,30second limit, in-memory recordings and fail-closed behavior. Close session before model. A full Parakeet/Piper integration and an appropriate combined memory budget remain unimplemented pending the speed/quality tradeoff decision.

Recommendation: retain Whisper for latency on this host. Do not silently select a smaller Q5/Q6 model or increase paid infrastructure; those are different choices from the requested Q8 candidate.
