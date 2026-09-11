# Offline verification

Installation and model downloads require connectivity. Recording jobs must work after setup with external connectivity disabled. The regular startup scripts set model helpers to offline mode and disable Ollama cloud features. Those flags alone are not proof of isolation.

## Demo-machine rehearsal

1. Finish model setup, build the frontend, and record `megan preflight` plus `models/installed.json`. If speaker separation is enabled, also finish [Sortformer setup](DIARIZATION.md), preserve its runtime and weights, and record `models/diarization-installed.json`.
2. Stop the API and project Ollama server. Disconnect Wi-Fi/Ethernet and external VPN routes; retain loopback. Avoid disconnecting a machine you control only remotely.
3. Start local PostgreSQL, `bash scripts/run_ollama.sh`, and `bash scripts/run_local.sh`.
4. In a fresh browser tab, open `http://127.0.0.1:8000`. Load the actual recording through the file picker. Do not rely on the illustrative example or a previously generated report.
5. Check all mandatory sections, play a source, edit a task, export JSON/CSV/ICS, and ask a question. With Sortformer enabled, inspect recurring voices, unknown attribution, and the speaker filter. Repeat with another recording.
6. Restart the API. Confirm completed jobs and edited revisions persist. Inspect browser Network for remote requests, including fonts and scripts.
7. Save the reports, stage timings, runtime/model versions, and GPU/system-memory observations. Restore connectivity only after the rehearsal.

Fatikh must run this on the RTX demo machine. A Mac result does not establish CUDA readiness or Kazakh/Russian ASR accuracy.

## Additional macOS process isolation

Where `sandbox-exec` is available, the checked-in profile blocks outbound connections except loopback for a process and its children. It is a development verification harness, not a deployment requirement. Stop the project's existing API/Ollama instances before launching replacements on the same ports:

```bash
sandbox-exec -f scripts/loopback-only.sb bash scripts/run_ollama.sh
# In another terminal:
sandbox-exec -f scripts/loopback-only.sb bash scripts/run_local.sh
```

Keep PostgreSQL on loopback. Verify the harness itself: a test connection to a local service should succeed, while a direct external TCP connection should fail with a permission error. Then process a real recording through the API. This covers the API's ASR and optional Sortformer subprocesses and the isolated Ollama process. The browser needs its own network inspection or OS-level network disconnection; the profile does not isolate a browser that was already running.

For Linux, prefer the complete disconnected rehearsal above. A CLI-only `unshare -n` cannot reach PostgreSQL/Ollama on the host loopback. An automated namespace harness would need to launch all services and the test client together; that harness is deferred.
