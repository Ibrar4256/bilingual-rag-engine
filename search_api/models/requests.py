"""
Request models for search endpoints (R15, R16, R17).
"""

from typing import Literal

from pydantic import BaseModel, Field


class CategorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="Free-text search query")
    limit: int = Field(10, ge=1, le=100)
    offset: int = Field(0, ge=0, description="Pagination offset")
    language: str | None = Field(None, description="Force language ('hu'/'en'); auto-detected if omitted")
    filters: dict | None = Field(None, description="JSONB metadata pre-filters (e.g. {'ai_type': 'Product'})")
    rerank: bool = Field(False, description="Re-rank results using cosine similarity blending")


class CompanyMatchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="RFQ/need description")
    limit: int = Field(10, ge=1, le=100)
    offset: int = Field(0, ge=0, description="Pagination offset")
    language: str | None = Field(None)
    filters: dict | None = Field(None, description="JSONB metadata pre-filters (e.g. {'status': 'OK'})")
    rerank: bool = Field(False, description="Re-rank results using cosine similarity blending")


class SingleCompanySearchRequest(BaseModel):
    company_id: str = Field(..., description="Scope search to this company")
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(10, ge=1, le=50)
    offset: int = Field(0, ge=0, description="Pagination offset")
    language: str | None = Field(None)
    rerank: bool = Field(False, description="Re-rank results using cosine similarity blending")


class RAGRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Question to answer using RAG")
    table: Literal["category_vectors", "company_vectors"] = Field("category_vectors", description="Which table to search")
    limit: int = Field(5, ge=1, le=20, description="Number of documents to retrieve for context")
    language: str | None = Field(None, description="Force language ('hu'/'en'); auto-detected if omitted")
    stream: bool = Field(False, description="Stream the response token-by-token via SSE")
