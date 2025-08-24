"""Experiment with tiny models.

torch reference:
<https://github.com/rpytel1/dl-framework-comparison/blob/ee38afe9dbd3278ff410208398922e49c9b77dec/code/pytorch_example.py>

uv-torch reference: <https://docs.astral.sh/uv/guides/integration/pytorch/#using-a-pytorch-index>

Manage downloaded models with `huggingface-cli`:

```sh
uv add huggingface_hub --dev --extra=cli
source ./.venv/bin/python

hf cache scan
hf cache delete
```

"""

import torch  # noqa: F401 # indirectly required
from transformers import AutoModelForCausalLM, AutoTokenizer

checkpoint = "HuggingFaceTB/SmolLM-135M"

tokenizer = AutoTokenizer.from_pretrained(checkpoint)
tokenizer.chat_template = """<|user|> {user_message}\n<|assistant|>"""

model = AutoModelForCausalLM.from_pretrained(checkpoint)

tools = [
    {
        "name": "get_weather",
        "description": "Get the weather in a city",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "The city to get the weather for"}},
        },
    }
]

messages = [{"role": "user", "content": "Hello! How is the weather today in Copenhagen?"}]

# Set the pad_token_id to eos_token_id if not already set
if tokenizer.pad_token_id is None:
    tokenizer.pad_token_id = tokenizer.eos_token_id

# Update the inputs to include attention_mask
inputs = tokenizer.apply_chat_template(
    messages,
    enable_thinking=False,
    xml_tools=tools,
    add_generation_prompt=True,
    tokenize=True,
    return_tensors="pt",
)

# Add attention_mask to the model.generate call
outputs = model.generate(
    inputs["input_ids"],
    attention_mask=inputs["attention_mask"]
)
print(tokenizer.decode(outputs[0]))  # noqa: T201
