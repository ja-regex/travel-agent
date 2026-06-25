from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .config import (
    ANSWER_MODEL,
    BUDGET,
    FINAL_ANSWER_COST_RESERVE_USD,
    GUARDRAIL_MODEL,
    TRIAGE_MODEL,
)
from .languages import build_local_language_query, infer_local_languages, unique_strings
from .models import (
    Candidate,
    CandidateResponse,
    ChatMessage,
    FetchedPage,
    ResearchPlan,
    SearchResult,
    TriagePick,
    UsageEvent,
)
from .services import (
    cost_for_usage,
    estimate_tokens,
    fetch_page_text,
    get_openai,
    json_chat,
    search_web,
    total_estimated_cost,
)


def event_line(event_type: str, **payload: Any) -> str:
    return json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n"


def strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return unique_strings([item for item in value if isinstance(item, str)])


def text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def normalize_research_plan(value: Any, conversation: str) -> ResearchPlan:
    raw = value if isinstance(value, dict) else {}
    destinations = strings(raw.get("destinationsMentioned"))
    preferred_languages = strings(raw.get("preferredSourceLanguages"))
    inferred_languages = infer_local_languages(destinations)
    model_languages = strings(raw.get("localLanguages"))
    destination_languages = inferred_languages or model_languages

    return ResearchPlan(
        accepted=raw.get("accepted") is True,
        reason=text(raw.get("reason")),
        trip_summary=text(raw.get("tripSummary")) or conversation,
        criteria=strings(raw.get("criteria")),
        destinations_mentioned=destinations,
        comparison_places=strings(raw.get("comparisonPlaces")),
        preferred_source_languages=preferred_languages,
        local_languages=unique_strings(destination_languages + preferred_languages),
        local_language_would_help=(
            raw.get("localLanguageWouldHelp") is True or bool(preferred_languages)
        ),
        search_queries=strings(raw.get("searchQueries")),
    )


def conversation_text(messages: list[ChatMessage]) -> str:
    return "\n".join(f"{message.role}: {message.content}" for message in messages)


async def create_plan(messages: list[ChatMessage], usage: list[UsageEvent]) -> ResearchPlan:
    conversation = conversation_text(messages)
    raw_plan = await json_chat(
        label="input_guardrail_and_research_plan",
        model=GUARDRAIL_MODEL,
        usage=usage,
        system=" ".join(
            [
                "You are a travel-request input guardrail and research planner.",
                "Accept only requests for travel recommendations, itinerary ideas, destination comparisons, or follow-up travel planning.",
                "Reject unrelated, unsafe, or non-travel requests.",
                "Separate places the traveler intends to visit from places mentioned only as analogies, examples, memories, or comparisons.",
                "destinationsMentioned contains only intended or actively considered destinations. comparisonPlaces contains analogy places that shape the vibe but must not trigger local-language research.",
                "Example: 'Vietnam, starting in Hanoi, with small towns like Valle Sagrada in Peru' puts Vietnam and Hanoi in destinationsMentioned, and Valle Sagrada and Peru in comparisonPlaces.",
                "preferredSourceLanguages contains only languages the user explicitly requests for research, such as Japanese tourbooks.",
                "localLanguages contains languages useful for intended destinations plus explicitly preferred source languages. Never add a language solely because a comparisonPlace uses it.",
                "Set localLanguageWouldHelp true when non-English sources could add practical destination detail, or when preferredSourceLanguages is non-empty.",
                "Return strict JSON with keys: accepted, reason, tripSummary, criteria, destinationsMentioned, comparisonPlaces, preferredSourceLanguages, localLanguages, localLanguageWouldHelp, searchQueries.",
                "Produce 2-5 concise search queries including the user's dates, budget, pace, interests, and constraints.",
            ]
        ),
        user=conversation,
    )
    return normalize_research_plan(raw_plan, conversation)


async def triage_snippets(
    plan: ResearchPlan,
    query: str,
    results: list[SearchResult],
    usage: list[UsageEvent],
) -> list[TriagePick]:
    raw = await json_chat(
        label="snippet_triage",
        model=TRIAGE_MODEL,
        usage=usage,
        system=" ".join(
            [
                "You are a cheap triage model for a travel research agent.",
                "Read all snippets before choosing pages worth deeper investigation.",
                "Prefer official tourism, local media and blogs, transport operators, local-language sources, recent practical guides, and concrete evidence.",
                "Avoid thin SEO listicles unless no better source exists.",
                'Return strict JSON: {"picks":[{"url":"...","reason":"...","candidateDestination":"...","fetch":true|false}]}.',
            ]
        ),
        user=json.dumps(
            {
                "tripSummary": plan.trip_summary,
                "criteria": plan.criteria,
                "query": query,
                "snippets": [
                    {
                        "index": index,
                        "title": result.title,
                        "url": result.url,
                        "snippet": result.snippet,
                    }
                    for index, result in enumerate(results, start=1)
                ],
            },
            ensure_ascii=False,
        ),
    )
    picks = raw.get("picks", [])
    if not isinstance(picks, list):
        return []
    normalized = [
        TriagePick(
            url=text(item.get("url")),
            reason=text(item.get("reason")),
            candidate_destination=text(item.get("candidateDestination")),
            fetch=item.get("fetch") is True,
        )
        for item in picks
        if isinstance(item, dict)
    ]
    return [pick for pick in normalized if pick.fetch and pick.url][: BUDGET.fetches_per_search]


async def evaluate_pages(
    plan: ResearchPlan,
    pages: list[FetchedPage],
    usage: list[UsageEvent],
) -> CandidateResponse:
    raw = await json_chat(
        label="candidate_evaluation",
        model=TRIAGE_MODEL,
        usage=usage,
        system=" ".join(
            [
                "You evaluate fetched travel sources and extract destination candidates.",
                "A candidate is worth recommending only if it clearly matches user criteria.",
                "Do not invent evidence; use only the fetched pages.",
                "Return strict JSON with candidates, needMoreResearch, nextSearchQueries.",
                "Each candidate includes destination, countryOrRegion, matchedCriteria, strengths, cautions, evidenceUrls, and confidence from 0 to 1.",
                "Suggest at most 2 nextSearchQueries only when more research is needed.",
            ]
        ),
        user=json.dumps(
            {
                "tripSummary": plan.trip_summary,
                "criteria": plan.criteria,
                "pages": [page.model_dump() for page in pages],
            },
            ensure_ascii=False,
        ),
    )
    raw_candidates = raw.get("candidates", [])
    candidates: list[Candidate] = []
    for item in raw_candidates if isinstance(raw_candidates, list) else []:
        if not isinstance(item, dict):
            continue
        candidates.append(
            Candidate(
                destination=text(item.get("destination")),
                country_or_region=text(item.get("countryOrRegion")),
                matched_criteria=strings(item.get("matchedCriteria")),
                strengths=strings(item.get("strengths")),
                cautions=strings(item.get("cautions")),
                evidence_urls=strings(item.get("evidenceUrls")),
                confidence=number(item.get("confidence")),
            )
        )
    return CandidateResponse(
        candidates=candidates,
        need_more_research=raw.get("needMoreResearch") is True,
        next_search_queries=strings(raw.get("nextSearchQueries"))[:2],
    )


def merge_candidates(existing: list[Candidate], incoming: list[Candidate]) -> list[Candidate]:
    by_name: dict[str, Candidate] = {}
    for candidate in existing + incoming:
        if not candidate.destination:
            continue
        key = candidate.destination.lower()
        current = by_name.get(key)
        if current is None:
            by_name[key] = candidate
            continue
        by_name[key] = Candidate(
            destination=current.destination,
            country_or_region=current.country_or_region or candidate.country_or_region,
            matched_criteria=unique_strings(current.matched_criteria + candidate.matched_criteria),
            strengths=unique_strings(current.strengths + candidate.strengths)[:6],
            cautions=unique_strings(current.cautions + candidate.cautions)[:4],
            evidence_urls=unique_strings(current.evidence_urls + candidate.evidence_urls)[:5],
            confidence=max(current.confidence, candidate.confidence),
        )
    return sorted(
        by_name.values(),
        key=lambda item: (len(item.matched_criteria), item.confidence),
        reverse=True,
    )[: BUDGET.max_candidates]


def ready_to_recommend(candidates: list[Candidate]) -> bool:
    return sum(len(candidate.matched_criteria) >= 4 for candidate in candidates) >= 3


def estimated_search_cost_usd() -> float:
    try:
        value = float(os.getenv("WEB_SEARCH_COST_PER_CALL_USD", "0.01"))
        return value if value >= 0 else 0.01
    except ValueError:
        return 0.01


async def stream_final_answer(
    messages: list[ChatMessage],
    plan: ResearchPlan,
    candidates: list[Candidate],
    usage: list[UsageEvent],
    searches: int,
    web_fetches: int,
) -> AsyncIterator[str]:
    stream = await get_openai().chat.completions.create(
        model=ANSWER_MODEL,
        stream=True,
        stream_options={"include_usage": True},
        max_completion_tokens=1400,
        temperature=0.35,
        messages=[
            {
                "role": "system",
                "content": " ".join(
                    [
                        "You are a careful travel companion agent.",
                        "Recommend 2-5 destinations based on the research.",
                        "Be concise, practical, and transparent about tradeoffs.",
                        "Mention local-language research when it influenced the answer.",
                        "Cite source URLs inline in compact markdown links.",
                        "End with one useful follow-up question.",
                    ]
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "conversation": [message.model_dump() for message in messages],
                        "plan": plan.model_dump(),
                        "candidates": [candidate.model_dump() for candidate in candidates],
                        "budgetUsed": {
                            "searches": searches,
                            "webFetches": web_fetches,
                            "estimatedCostUsdBeforeFinal": total_estimated_cost(usage),
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield event_line("token", text=delta)
        if chunk.usage:
            usage.append(
                UsageEvent(
                    label="final_answer",
                    model=ANSWER_MODEL,
                    promptTokens=chunk.usage.prompt_tokens,
                    completionTokens=chunk.usage.completion_tokens,
                    totalTokens=chunk.usage.total_tokens,
                    costUsd=cost_for_usage(
                        ANSWER_MODEL,
                        chunk.usage.prompt_tokens,
                        chunk.usage.completion_tokens,
                    ),
                )
            )


async def run_travel_agent(messages: list[ChatMessage]) -> AsyncIterator[str]:
    usage: list[UsageEvent] = []
    searches = 0
    web_fetches = 0
    candidates: list[Candidate] = []
    seen_urls: set[str] = set()

    yield event_line("status", message="Checking that this is a travel recommendation request.")
    plan = await create_plan(messages, usage)

    if not plan.accepted:
        yield event_line(
            "token",
            text=(
                "I can help with travel recommendations and trip planning, "
                f"but this request looks outside that scope: {plan.reason}"
            ),
        )
        yield event_line(
            "usage",
            usage=[item.model_dump(exclude_none=True) for item in usage],
            totals={
                "estimatedCostUsd": total_estimated_cost(usage),
                "webFetches": web_fetches,
                "searches": searches,
            },
        )
        return

    queries = list(plan.search_queries)
    if plan.local_language_would_help and plan.local_languages:
        yield event_line(
            "status",
            message=(
                "Local-language sources may improve this answer, so I will include "
                f"{', '.join(plan.local_languages)} search terms."
            ),
        )
        queries.extend(
            build_local_language_query(query, plan.local_languages)
            for query in plan.search_queries[:2]
        )

    while (
        queries
        and searches < BUDGET.max_searches
        and web_fetches < BUDGET.max_web_fetches
        and total_estimated_cost(usage)
        < BUDGET.hard_ceiling_usd - FINAL_ANSWER_COST_RESERVE_USD
        and not ready_to_recommend(candidates)
    ):
        query = queries.pop(0)
        searches += 1
        yield event_line("status", message=f"Searching: {query}")
        results = await search_web(query, BUDGET.snippets_per_search)
        usage.append(
            UsageEvent(
                label="web_search_snippets",
                estimatedTokens=estimate_tokens(
                    json.dumps([item.model_dump() for item in results])
                ),
                costUsd=estimated_search_cost_usd(),
            )
        )

        yield event_line(
            "status",
            message=(
                f"Triage is reading {len(results)} snippets and choosing "
                "what is worth fetching."
            ),
        )
        picks = await triage_snippets(plan, query, results, usage)
        pages: list[FetchedPage] = []

        for pick in picks:
            if web_fetches >= BUDGET.max_web_fetches or pick.url in seen_urls:
                continue
            seen_urls.add(pick.url)
            web_fetches += 1
            yield event_line(
                "status",
                message=(
                    "Fetching a stronger source: "
                    f"{pick.candidate_destination or pick.url}"
                ),
            )
            try:
                pages.append(await fetch_page_text(pick.url))
            except (httpx.HTTPError, ValueError):
                yield event_line(
                    "status",
                    message="Skipped one source that could not be fetched cleanly.",
                )

        if not pages:
            continue

        yield event_line(
            "status",
            message="Evaluating fetched sources against the trip criteria.",
        )
        evaluation = await evaluate_pages(plan, pages, usage)
        candidates = merge_candidates(candidates, evaluation.candidates)
        if not ready_to_recommend(candidates) and evaluation.need_more_research:
            for next_query in evaluation.next_search_queries:
                if len(queries) + searches < BUDGET.max_searches:
                    queries.append(next_query)

    if ready_to_recommend(candidates):
        status = "Enough destinations meet the criteria. Writing recommendations."
    elif (
        total_estimated_cost(usage)
        >= BUDGET.hard_ceiling_usd - FINAL_ANSWER_COST_RESERVE_USD
    ):
        status = "Reached the cost ceiling. Writing the best-supported recommendations."
    else:
        status = "Reached the research budget. Writing the best-supported recommendations."
    yield event_line("status", message=status)

    async for line in stream_final_answer(
        messages, plan, candidates, usage, searches, web_fetches
    ):
        yield line

    yield event_line(
        "usage",
        usage=[item.model_dump(exclude_none=True) for item in usage],
        totals={
            "estimatedCostUsd": total_estimated_cost(usage),
            "webFetches": web_fetches,
            "searches": searches,
        },
    )
