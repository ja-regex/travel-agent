from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)


class ResearchPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    accepted: bool = False
    reason: str = ""
    trip_summary: str = ""
    criteria: list[str] = Field(default_factory=list)
    destinations_mentioned: list[str] = Field(default_factory=list)
    comparison_places: list[str] = Field(default_factory=list)
    preferred_source_languages: list[str] = Field(default_factory=list)
    local_languages: list[str] = Field(default_factory=list)
    local_language_would_help: bool = False
    search_queries: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class TriagePick(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str = ""
    reason: str = ""
    candidate_destination: str = ""
    fetch: bool = False


class FetchedPage(BaseModel):
    url: str
    title: str
    text: str


class Candidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    destination: str = ""
    country_or_region: str = ""
    matched_criteria: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    evidence_urls: list[str] = Field(default_factory=list)
    confidence: float = 0


class CandidateResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidates: list[Candidate] = Field(default_factory=list)
    need_more_research: bool = False
    next_search_queries: list[str] = Field(default_factory=list)


class UsageEvent(BaseModel):
    label: str
    model: str | None = None
    promptTokens: int | None = None
    completionTokens: int | None = None
    totalTokens: int | None = None
    estimatedTokens: int | None = None
    costUsd: float | None = None
