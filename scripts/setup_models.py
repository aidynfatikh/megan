"""Explicit ONLINE setup. Never called by a recording job."""

import argparse
import hashlib
import json
import os
import platform
from pathlib import Path

import httpx

from backend.config import Settings


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=["mac", "cuda"],
        default="mac" if platform.system() == "Darwin" else "cuda",
    )
    parser.add_argument(
        "--check", action="store_true", help="Verify existing artifacts only; do not download"
    )
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name("model_manifest.json").read_text())
    spec = manifest[args.profile]
    directory = Path(spec["directory"])
    weight = directory / spec["weight"]
    directory.mkdir(parents=True, exist_ok=True)
    if not args.check:
        # The online setup process alone opts into downloads. API workers force offline mode.
        os.environ.pop("HF_HUB_OFFLINE", None)
        from huggingface_hub import hf_hub_download

        for filename in spec["files"]:
            target = directory / filename
            if filename == spec["weight"] and target.is_file() and sha256(target) == spec["sha256"]:
                print(f"Verified existing {target}", flush=True)
                continue
            hf_hub_download(
                spec["repository"], filename, revision=spec["revision"], local_dir=directory
            )
    if (
        not all((directory / name).is_file() for name in spec["files"])
        or sha256(weight) != spec["sha256"]
    ):
        raise SystemExit(
            "ASR artifact is missing or its checksum differs from the pinned manifest."
        )
    settings = Settings()
    with httpx.Client(base_url=settings.ollama_base_url, timeout=30, trust_env=False) as client:
        response = client.get("/api/tags")
        response.raise_for_status()
        models = response.json()["models"]
        if not any(m["name"] == settings.ollama_model for m in models) and not args.check:
            last_status = None
            with client.stream(
                "POST",
                "/api/pull",
                json={"model": settings.ollama_model, "stream": True},
                timeout=None,
            ) as pull:
                pull.raise_for_status()
                for line in pull.iter_lines():
                    entry = json.loads(line)
                    if "error" in entry:
                        raise SystemExit(entry["error"])
                    if entry.get("status") != last_status:
                        last_status = entry.get("status")
                        print(last_status, flush=True)
            response = client.get("/api/tags")
            response.raise_for_status()
            models = response.json()["models"]
    model = next((m for m in models if m["name"] == settings.ollama_model), None)
    if model is None:
        raise SystemExit("The selected Ollama model is not downloaded.")
    actual = {
        "profile": args.profile,
        "asr": spec,
        "llm": settings.ollama_model,
        "llm_digest": model["digest"],
    }
    if (
        settings.ollama_model == manifest["ollama"]["model"]
        and model["digest"] != manifest["ollama"]["tested_digest"]
    ):
        print(
            "Ollama tag digest differs from the tested artifact. Re-evaluate accuracy and memory on this build."
        )
    Path("models/installed.json").write_text(json.dumps(actual, indent=2) + "\n")
    print("Local model files verified. Run megan preflight, then process a real recording.")


if __name__ == "__main__":
    main()
