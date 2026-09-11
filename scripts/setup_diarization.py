"""Explicit online Sortformer setup; never invoked by the application worker."""

import argparse
import json
import platform
import tarfile
from pathlib import Path

import httpx

from backend.pipeline.diarize import weight_digest


def ensure_file(path: Path, url: str, digest: str, *, check=False):
    if path.is_file() and weight_digest(path) == digest:
        return
    if check:
        raise ValueError(f"Artifact missing or checksum differs: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".download")
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            with partial.open("wb") as stream:
                for chunk in response.iter_bytes():
                    stream.write(chunk)
        if weight_digest(partial) != digest:
            raise ValueError(f"Downloaded artifact checksum differs: {path}")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", choices=["cpp", "nemo"], required=True)
    parser.add_argument("--check", action="store_true", help="Verify weights only; never download")
    parser.add_argument(
        "--install-mac-runtime",
        action="store_true",
        help="Install pinned NeMo-Speech.cpp Metal release under .local/",
    )
    args = parser.parse_args()
    if args.install_mac_runtime and (
        args.runtime != "cpp"
        or platform.system() != "Darwin"
        or platform.machine() != "arm64"
        or args.check
    ):
        parser.error(
            "--install-mac-runtime requires Apple Silicon, --runtime cpp, and online setup"
        )
    manifest = json.loads(Path(__file__).with_name("model_manifest.json").read_text())["sortformer"]
    spec = manifest[args.runtime]
    target = Path("models") / spec["filename"]
    url = (
        f"https://huggingface.co/{manifest['repository']}/resolve/"
        f"{manifest['revision']}/{spec['filename']}"
    )
    ensure_file(target, url, spec["sha256"], check=args.check)
    print(f"Verified {target}")
    if args.install_mac_runtime:
        release = manifest["mac_runtime"]
        archive = Path(".local/downloads") / release["filename"]
        url = (
            "https://github.com/NVIDIA/NeMo-Speech.cpp/releases/download/"
            f"{release['version']}/{release['filename']}"
        )
        ensure_file(archive, url, release["sha256"])
        with tarfile.open(archive) as bundle:
            bundle.extractall(".local", filter="data")
        print("Installed .local/nemo-speech/bin/nemo-speech")
    Path("models/diarization-installed.json").write_text(
        json.dumps(
            {
                "repository": manifest["repository"],
                "revision": manifest["revision"],
                "runtime": args.runtime,
                "weight": str(target),
                "sha256": spec["sha256"],
            },
            indent=2,
        )
        + "\n"
    )
    print("Set the Sortformer options documented in docs/DIARIZATION.md, then restart Megan.")


if __name__ == "__main__":
    main()
