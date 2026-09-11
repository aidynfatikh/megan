"""Offline child entry point for an existing NeMo environment; no Megan imports.

Adapted from Fatikh's diarize_local.py: same checkpoint and streaming parameters,
one recording per process, no cropping, concatenation, or download fallback.
"""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], required=True)
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error("Local .nemo checkpoint is missing; no downloads are allowed here")
    os.environ.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        NEMO_LOG_LEVEL="ERROR",
    )
    import torch
    from nemo.collections.asr.models import SortformerEncLabelModel

    model = SortformerEncLabelModel.restore_from(str(args.model), map_location=args.device)
    model = model.to(args.device).eval()
    module = model.sortformer_modules
    module.chunk_len = 124
    module.chunk_right_context = 1
    module.fifo_len = 124
    module.spkcache_update_period = 124
    module.spkcache_len = 188
    module._check_streaming_parameters()
    with torch.inference_mode():
        predicted = model.diarize(audio=[str(args.audio)], batch_size=1, verbose=False)
    if len(predicted) != 1:
        raise ValueError("Expected one recording's diarization result")
    turns = []
    for segment in predicted[0]:
        start, end, speaker = str(segment).split()
        turns.append({"start": float(start), "end": float(end), "speaker": speaker})
    args.output.write_text(
        json.dumps(
            {
                "segments": turns,
                "runtime": f"NeMo {importlib.metadata.version('nemo_toolkit')} / torch {torch.__version__} / {args.device}",
            }
        )
    )


if __name__ == "__main__":
    main()
