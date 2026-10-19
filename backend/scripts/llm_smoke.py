"""Gọi DeepSeek thật: python -m scripts.llm_smoke [--json|--stream]. Có dùng API credits.

Phụ trách: TV3 · [S1] Xác nhận DeepSeek
"""

import argparse
import asyncio
import json
from contextlib import aclosing

from openai.types.chat import ChatCompletionMessageParam

from app.adapters.llm import DeepSeekLLM, LLMError


async def main(mode: str) -> None:
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": "You are IndexBeast. Keep answers short."},
        {"role": "user", "content": "Say hello in Vietnamese in one sentence."},
    ]
    async with DeepSeekLLM() as llm:
        if mode == "json":
            print(json.dumps(await llm.complete_json(messages, max_tokens=128), ensure_ascii=False))
        elif mode == "stream":
            async with aclosing(llm.stream(messages, max_tokens=128)) as tokens:
                async for token in tokens:
                    print(token, end="", flush=True)
            print()
        else:
            result = await llm.complete(messages, max_tokens=128)
            print(result.content)
            print(f"Model: {result.model}; tokens: {result.prompt_tokens} in / {result.completion_tokens} out")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Call the live DeepSeek API (uses API credits).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true")
    group.add_argument("--stream", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(main("json" if args.json else "stream" if args.stream else "text"))
    except LLMError as exc:
        parser.exit(1, f"{exc}\n")
