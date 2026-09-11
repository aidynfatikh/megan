"""Count local text tokens without downloading or truncating meeting content."""

import json
from functools import lru_cache

from tokenizers import Tokenizer

from backend.config import Settings


@lru_cache(maxsize=2)
def load_tokenizer(path: str, modified_ns: int):
    tokenizer = Tokenizer.from_file(path)
    tokenizer.no_truncation()
    tokenizer.no_padding()
    return tokenizer


def prompt_tokens(messages: list[dict], settings: Settings) -> int:
    path = settings.llm_tokenizer_path
    if settings.ollama_model.startswith("qwen3.5:") and path.is_file():
        tokenizer = load_tokenizer(str(path.resolve()), path.stat().st_mtime_ns)
        # Count the actual message content. Reserve chat framing separately; generation
        # also leaves 256 tokens for the assistant prefix and a possible repair request.
        return sum(
            len(tokenizer.encode(m["content"], add_special_tokens=False).ids) + 16 for m in messages
        )
    # Unknown model/tokenizer: UTF-8 bytes are a deliberately strict fallback.
    # An average bytes/token ratio is not a bound for short words, numbers, or mixed text.
    return len(json.dumps(messages, ensure_ascii=False).encode("utf-8"))
