from __future__ import annotations

from openai import OpenAI


def ask(*, api_key: str, model: str, prompt: str) -> str:
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    msg = resp.choices[0].message.content
    return (msg or "").strip()

