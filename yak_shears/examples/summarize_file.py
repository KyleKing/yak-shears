"""Proof of Concept Local File Summary.

```sh
uv run yak_shears/examples/summarize_file.py .github/copilot-instructions.md
```

"""  # noqa: INP001

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# from transformers.models.auto.modeling_auto import _BaseModelWithGenerate  # noqa: ERA001
from typing import Any

import torch

# from typing import TYPE_CHECKING  # noqa: ERA001
# if TYPE_CHECKING:
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedTokenizer

# MODEL_NAME = "HuggingFaceTB/SmolLM-135M"  # Too general purpose  # noqa: ERA001
# MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"  # About 1m  # noqa: ERA001
MODEL_NAME = "facebook/bart-large-cnn"  # PLANNED: Test
# MODEL_NAME = "pszemraj/led-large-book-summary"  # FYI: use 'pipeline' instead  # noqa: ERA001
MAX_INPUT_TOKENS = 700  # FYI: lowered to test chunking
MAX_NEW_TOKENS = 120


@dataclass(frozen=True)
class SummaryResult:
    """Result of text summarization containing the summary and token counts.

    Attributes:
        summary: The generated summary text.
        input_tokens: Total number of input tokens processed.
        generated_tokens: Total number of tokens generated for summaries.
    """

    summary: str
    input_tokens: int
    generated_tokens: int


def batch_tokens(tokens: list[int], max_len: int) -> list[list[int]]:
    """Split a list of tokens into batches of maximum length.

    Args:
        tokens: List of token IDs to split.
        max_len: Maximum length for each batch.

    Returns:
        List of token batches, each with at most max_len tokens.
    """
    if not tokens:
        return []
    batches: list[list[int]] = []
    start = 0
    while start < len(tokens):
        end = min(start + max_len, len(tokens))
        batches.append(tokens[start:end])
        start = end
    return batches


def load_text(path: Path) -> str:
    """Load and clean text content from a file.

    Args:
        path: Path to a text file.

    Returns:
        File contents with minimal processing.
    """
    return path.read_text(encoding="utf-8").strip()


def iter_chunks(text: str, tokenizer: PreTrainedTokenizer, max_tokens: int) -> Iterable[str]:
    """Split text into chunks of approximately max_tokens length.

    Args:
        text: The input text to chunk.
        tokenizer: HuggingFace tokenizer for encoding/decoding.
        max_tokens: Maximum number of tokens per chunk.

    Yields:
        Text chunks of approximately max_tokens length.
    """
    ids = tokenizer.encode(text)
    for batch in batch_tokens(ids, max_tokens):
        yield tokenizer.decode(batch)


def build_prompt(chunk: str, summary: str) -> str:
    """Build a chat-formatted prompt for instruction models.

    Args:
        chunk: Text chunk to summarize.
        summary: Existing summary to build upon (empty string for first chunk).

    Returns:
        Formatted prompt string in instruction format.
    """
    system = "<|im_start|>system\nYou are a helpful assistant that creates concise, accurate summaries.<|im_end|>"
    if summary:
        return f"""{system}
<|im_start|>user
I have a previous summary: {summary}

Please update this summary by incorporating the following additional text: {chunk}

Provide a comprehensive summary that combines both the previous summary and new information in 2-3 clear sentences.<|im_end|>
<|im_start|>assistant
"""  # noqa: E501
    return f"""{system}
<|im_start|>user
Please summarize the following text in 2-3 clear, informative sentences:

{chunk}<|im_end|>
<|im_start|>assistant
"""


def summarize(chunk: str, tokenizer: PreTrainedTokenizer, model: Any, summary: str) -> str:
    """Generate a summary for a text chunk using the language model.

    Args:
        chunk: Text chunk to summarize.
        tokenizer: HuggingFace tokenizer.
        model: HuggingFace language model.
        summary: Existing summary to build upon.

    Returns:
        Generated summary text with stop markers removed.
    """
    prompt = build_prompt(chunk, summary)
    inputs = tokenizer(prompt, return_tensors="pt")

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.1,
        )
    generated = output[0][inputs.input_ids.shape[1] :]
    text = tokenizer.decode(generated, skip_special_tokens=True).strip()

    # For instruction-tuned models, stop at natural end markers
    stop_markers = ["<|im_end|>", "\n\nUser:", "\n\nHuman:", "<|end|>"]
    for marker in stop_markers:
        if marker in text:
            print("Found marker!", text)  # noqa: T201
            text = text.split(marker)[0].strip()

    return text.strip()


def summarize_file(path: Path) -> SummaryResult:
    """Summarize a text file by processing it in chunks.

    Args:
        path: Path to the text file to summarize.

    Returns:
        SummaryResult containing the final summary and token statistics.
    """
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.float32)

    raw = load_text(path)

    total_input_tokens = 0
    total_generated_tokens = 0

    summary = ""
    for chunk in iter_chunks(raw, tokenizer, MAX_INPUT_TOKENS):
        summary_text = summarize(chunk, tokenizer, model, summary)
        total_input_tokens += len(tokenizer.encode(chunk))
        total_generated_tokens += len(tokenizer.encode(summary_text))
        summary = summary_text

    return SummaryResult(
        summary=summary,
        input_tokens=total_input_tokens,
        generated_tokens=total_generated_tokens,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: Command line arguments to parse.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description=f"Summarize a text file with {MODEL_NAME}")
    parser.add_argument("path", type=Path, help="Path to UTF-8 text file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the summarization script.

    Args:
        argv: Optional command line arguments. Uses sys.argv if None.

    Returns:
        Exit code (0 for success).
    """
    args = parse_args(argv or sys.argv[1:])
    result = summarize_file(args.path)
    print(f"Input tokens: {result.input_tokens} | Generated tokens: {result.generated_tokens}")  # noqa: T201
    print("Summary:\n" + result.summary)  # noqa: T201
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
