from __future__ import annotations

import html
import json
import os
import re
from typing import Any

import httpx
from openai import AsyncOpenAI

from .models import FetchedPage, SearchResult, UsageEvent


MODEL_PRICES_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o-mini": (0.15, 0.60),
}

_openai_client: AsyncOpenAI | None = None


def get_openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client


def cost_for_usage(model: str | None, prompt_tokens: int = 0, completion_tokens: int = 0) -> float:
    prices = MODEL_PRICES_PER_1M.get(model or "")
    if not prices:
        return 0
    input_price, output_price = prices
    return (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000


def total_estimated_cost(usage: list[UsageEvent]) -> float:
    return sum(item.costUsd or 0 for item in usage)


def estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4


async def json_chat(
    *,
    label: str,
    model: str,
    system: str,
    user: str,
    usage: list[UsageEvent],
) -> dict[str, Any]:
    completion = await get_openai().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    model_usage = completion.usage
    prompt_tokens = model_usage.prompt_tokens if model_usage else 0
    completion_tokens = model_usage.completion_tokens if model_usage else 0
    usage.append(
        UsageEvent(
            label=label,
            model=model,
            promptTokens=prompt_tokens,
            completionTokens=completion_tokens,
            totalTokens=model_usage.total_tokens if model_usage else 0,
            costUsd=cost_for_usage(model, prompt_tokens, completion_tokens),
        )
    )
    content = completion.choices[0].message.content or "{}"
    parsed = json.loads(content)
    return parsed if isinstance(parsed, dict) else {}


async def search_web(query: str, max_results: int) -> list[SearchResult]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("Missing TAVILY_API_KEY.")

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
            },
        )
        response.raise_for_status()

    results: list[SearchResult] = []
    for item in response.json().get("results", []):
        url = item.get("url")
        if not isinstance(url, str) or not url:
            continue
        results.append(
            SearchResult(
                title=item.get("title") or "Untitled",
                url=url,
                snippet=(item.get("content") or "")[:800],
            )
        )
    return results


async def fetch_page_text(url: str) -> FetchedPage:
    async with httpx.AsyncClient(
        timeout=8,
        follow_redirects=True,
        headers={"user-agent": "TravelCompanionAgent/0.1 (+https://vercel.app)"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        raise ValueError(f"Unsupported content type: {content_type}")

    raw = response.text
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
    title = html.unescape(title_match.group(1).strip()) if title_match else url
    text = raw
    for tag in ("script", "style", "nav", "footer"):
        text = re.sub(rf"<{tag}\b[\s\S]*?</{tag}>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()[:12_000]
    return FetchedPage(url=url, title=title, text=text)
