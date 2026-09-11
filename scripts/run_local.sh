#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export PYANNOTE_METRICS_ENABLED=0
if [[ "$(uname -s)" == Linux ]]; then
  megan_cuda_libs="$(.venv/bin/python - <<'PY'
import importlib.util
from backend.config import Settings
if Settings().asr_backend == 'faster_whisper' and Settings().asr_device == 'cuda':
    paths = []
    for name in ('nvidia.cublas.lib', 'nvidia.cudnn.lib'):
        spec = importlib.util.find_spec(name)
        if spec and spec.submodule_search_locations:
            paths.extend(spec.submodule_search_locations)
    print(':'.join(paths))
PY
)"
  export LD_LIBRARY_PATH="${megan_cuda_libs}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
exec .venv/bin/megan serve "$@"
