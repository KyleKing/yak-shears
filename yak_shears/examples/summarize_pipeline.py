"""Summarizer with Pipeline Abstraction.

Source: https://huggingface.co/docs/transformers/main_classes/pipelines#transformers.SummarizationPipeline

```
from transformers import T5Tokenizer, T5Model

tokenizer = T5Tokenizer.from_pretrained("t5-base")
model = T5Model.from_pretrained("t5-base")

input_ids = tokenizer(
    "Studies have been shown that owning a dog is good for you", return_tensors="pt"
).input_ids  # Batch size 1
decoder_input_ids = tokenizer("Studies show that", return_tensors="pt").input_ids  # Batch size 1

# forward pass
outputs = model(input_ids=input_ids, decoder_input_ids=decoder_input_ids)
last_hidden_states = outputs.last_hidden_state
```

```
en_fr_translator = pipeline("translation_en_to_fr")
en_fr_translator("How old are you?")
```

"""  # noqa: INP001

import argparse
import sys
from pathlib import Path
from pprint import pprint
from typing import Any

from transformers import pipeline


def load_text(path: Path) -> str:
    """Load and clean text content from a file.

    Args:
        path: Path to a text file.

    Returns:
        File contents with minimal processing.
    """
    return path.read_text(encoding="utf-8").strip()


def summarize_file(path: Path) -> Any:  # list[Iterable[dict[str, str | int]]]:
    """Summarize a text file by processing it in chunks.

    Args:
        path: Path to the text file to summarize.

    Returns:
        List of Summaries
    """
    raw = load_text(path)
    summaries = [
        # use bart in pytorch (Defaults to `sshleifer/distilbart-cnn-12-6`)
        {
            "model": "sshleifer/distilbart-cnn-12-6",  # < Seems to be the best result
            "result": pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")(
                raw,
                # min_length=45,  # noqa: ERA001
                # max_length=256,  # noqa: ERA001
            ),
        },
        # ---
        # use t5 in tf
        {
            "model": "google-t5/t5-base",
            # pipeline("summarization", model="google-t5/t5-base", tokenizer="google-t5/t5-base", framework="tf")(
            "result": pipeline("summarization", model="google-t5/t5-base")(
                raw,
                # min_length=45,  # noqa: ERA001
                # max_length=256,  # noqa: ERA001
            ),
        },
        # ---
        {
            "model": "facebook/bart-large-cnn",
            "result": pipeline("summarization", model="facebook/bart-large-cnn")(
                raw,
                # min_length=45,  # noqa: ERA001
                # max_length=256,  # noqa: ERA001
            ),
        },
        # ---
        # From: https://huggingface.co/pszemraj/led-large-book-summary
        {
            "model": "pszemraj/led-large-book-summary (minimal modification)",
            # Better output
            "results": pipeline("summarization", "pszemraj/led-large-book-summary")(
                # pipeline("summarization", "pszemraj/led-base-book-summary")(
                raw,
                # min_length=45,  # noqa: ERA001
            ),
        },
        {
            "model": "pszemraj/led-large-book-summary",
            "results": pipeline("summarization", "pszemraj/led-large-book-summary")(
                # pipeline("summarization", "pszemraj/led-base-book-summary")(
                raw,
                # min_length=45,  # noqa: ERA001
                # max_length=256,  # noqa: ERA001
                no_repeat_ngram_size=3,
                encoder_no_repeat_ngram_size=3,
                repetition_penalty=3.5,
                num_beams=4,
                early_stopping=True,
            ),
        },
        # ----
        # https://huggingface.co/docs/transformers/main_classes/pipelines#transformers.QuestionAnsweringPipeline
    ]

    # Question-answering pipeline results (all mediocre)
    for _m in (
        "distilbert/distilbert-base-cased-distilled-squad",
        "deepset/roberta-base-squad2",
        "google-bert/bert-large-uncased-whole-word-masking-finetuned-squad",
    ):
        qa_pipeline = pipeline("question-answering", model=_m, tokenizer=_m)
        # TODO: what is a good question that these models can answer and would be useful?
        result = qa_pipeline(question="Why was the document written?", context=raw)
        summaries.append({"model": _m, "result": result})

    # TODO: remove dashes
    # TODO: make more unique by modeling similarity
    tags = (Path.home() / "Downloads/unique_blog_tags.csv").read_text().split("\n")
    for _m in (
        "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",  # < confuses single letter coding languages
        "facebook/bart-large-mnli",  # < but not necessarily better
    ):
        classifier = pipeline("zero-shot-classification", model=_m)
        result = classifier(raw, tags, multi_label=True)
        summaries.append(
            {
                "model": _m,
                "result": {key: value for key, value in zip(result["labels"][:5], result["scores"][:5], strict=False)},  # noqa: C416
            }
        )

    return summaries


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: Command line arguments to parse.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Summarize a text file")
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
    summaries = summarize_file(args.path)
    print("\n\nSummaries\n\n")  # noqa: T201
    pprint(summaries)  # noqa: T203
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
