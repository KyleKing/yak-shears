"""Minimal example: summarize a text file with HuggingFaceTB/SmolLM-135M.

Usage (after installing project deps):

    uv run python -m yak_shears.examples.summarize_file path/to/doc.txt

The script keeps memory small and avoids downloading weights repeatedly by
leveraging local HF cache (default ~/.cache/huggingface/). It performs a very
simple prompt-based "summarization" via greedy decoding. For larger / higher
quality summaries, swap to an instruction tuned model or use a proper
summarization pipeline.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections.abc import Iterable
from dataclasses import dataclass

# PLANNED: import accelerate  # Indirect dependency
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "HuggingFaceTB/SmolLM-135M"
# DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MAX_INPUT_TOKENS = 700  # leave room for generation within 1K ctx
MAX_NEW_TOKENS = 120


@dataclass
class SummaryResult:
    summary: str
    input_tokens: int
    generated_tokens: int


def batch_tokens(tokens: list[int], max_len: int) -> list[list[int]]:
    if not tokens:
        return []
    batches: list[list[int]] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_len, len(tokens))
        batches.append(tokens[start:end])
        start = end
    return batches


def load_text(path: pathlib.Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.strip()


def iter_chunks(text: str, tokenizer, max_tokens: int) -> Iterable[str]:  # type: ignore[no-untyped-def]
    ids = tokenizer.encode(text)
    for batch in batch_tokens(ids, max_tokens):
        yield tokenizer.decode(batch)


def build_prompt(chunk: str) -> str:
    return (
        "Summarize the following text in 2-3 concise sentences focusing on the core ideas.\n\n"
        f"Text:\n{chunk}\n\nSummary:"
    )


def summarize(chunk: str, tokenizer, model) -> str:  # type: ignore[no-untyped-def]
    prompt = build_prompt(chunk)
    print("\n" * 20)
    print("prompt", prompt)
    inputs = tokenizer(prompt, return_tensors="pt")  # PLANNED: issues with MPS/CPU: .to(DEVICE)
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    generated = output[0][inputs.input_ids.shape[1] :]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


def summarize_file(path: pathlib.Path) -> SummaryResult:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.float32) # PLANNED: device_map="auto"

    raw = load_text(path)

    # If file is huge, just take the first chunk of MAX_INPUT_TOKENS tokens to keep runtime tiny
    first_chunk = next(iter(iter_chunks(raw, tokenizer, MAX_INPUT_TOKENS)), "")
    print("\n"*20)
    print("first_chunk", first_chunk)
    if not first_chunk:
        return SummaryResult(summary="(empty file)", input_tokens=0, generated_tokens=0)

    # TODO: what happens to the other chunks?
    summary_text = summarize(first_chunk, tokenizer, model)
    input_ids_len = len(tokenizer.encode(first_chunk))
    gen_len = len(tokenizer.encode(summary_text))
    return SummaryResult(summary=summary_text, input_tokens=input_ids_len, generated_tokens=gen_len)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Summarize a text file with {MODEL_NAME}")
    parser.add_argument("path", type=pathlib.Path, help="Path to UTF-8 text file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    result = summarize_file(args.path)
    print("\n" * 20)
    print("Summary:\n" + result.summary)
    print()
    print(f"Input tokens: {result.input_tokens} | Generated tokens: {result.generated_tokens}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
