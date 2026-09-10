"""
Response models (R20)

Every search endpoint (R15/R16/R17) must return `detected_language`,
`response_time_ms`, and `retrieval_mode` alongside its results — never a
bare result list (see .claude/rules/api-conventions.md).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchResponseMeta(BaseModel):
    detected_language: Literal["hu", "en"]
    response_time_ms: float
    retrieval_mode: str = "hybrid_rrf"
    total_count: int | None = Field(None, description="Total results before pagination")
    offset: int = Field(0, description="Current pagination offset")


class CategoryResult(BaseModel):
    category_id: str
    language: str
    narrative: str
    metadata: dict[str, Any]
    rrf_score: float
    cosine_similarity: float | None = None
    reranked_score: float | None = None


class CategorySearchResponse(SearchResponseMeta):
    results: list[CategoryResult]
    cross_language_fallback_triggered: bool = False


class CompanyResult(BaseModel):
    company_id: str
    language: str
    content_chunk: str
    chunk_index: int
    metadata: dict[str, Any]
    is_highlighted: bool
    rrf_score: float


class CompanyMatchResponse(SearchResponseMeta):
    results: list[CompanyResult]
    cross_language_fallback_triggered: bool = False


class SingleCompanySearchResponse(SearchResponseMeta):
    company_id: str
    results: list[CompanyResult]
    cross_language_fallback_triggered: bool = False


class RAGCitation(BaseModel):
    ref: int = Field(..., description="Citation number [1], [2], etc.")
    id: str = Field(..., description="Source document ID")
    type: str = Field(..., description="'category' or 'company'")
    language: str
    rrf_score: float


class RAGResponse(BaseModel):
    answer: str = Field(..., description="LLM-generated answer with [n] citations")
    citations: list[RAGCitation]
    detected_language: str
    retrieval_mode: str
    results_used: int
    response_time_ms: float


class HealthChecks(BaseModel):
    database: bool
    vector_index: bool
    bm25_index: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checks: HealthChecks
    response_time_ms: float = Field(..., description="Total time to run all health checks")
