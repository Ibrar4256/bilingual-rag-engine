"""
LLM Observability — trace every LLM and embedding call.

Stores provider, model, operation type, token counts, latency, and
estimated cost per call. The data feeds the admin Observability dashboard.
"""

import time
import threading

from loguru import logger

from search_api.db import get_connection

_TABLE_ENSURED = False
_lock = threading.Lock()

COST_PER_1K_TOKENS = {
    "gemini": {"input": 0.0, "output": 0.0},
    "groq": {"input": 0.0, "output": 0.0},
    "openrouter": {"input": 0.0, "output": 0.0},
    "jina": {"input": 0.0, "output": 0.0},
    "local_bge_m3": {"input": 0.0, "output": 0.0},
}


def _ensure_table():
    global _TABLE_ENSURED
    if _TABLE_ENSURED:
        return
    with _lock:
        if _TABLE_ENSURED:
            return
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS llm_traces (
                        id SERIAL PRIMARY KEY,
                        provider TEXT NOT NULL,
                        model TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        input_tokens INT DEFAULT 0,
                        output_tokens INT DEFAULT 0,
                        latency_ms FLOAT NOT NULL,
                        estimated_cost FLOAT DEFAULT 0.0,
                        status TEXT DEFAULT 'success',
                        error_message TEXT,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_llm_traces_created
                        ON llm_traces (created_at DESC)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_llm_traces_provider
                        ON llm_traces (provider)
                """)
            conn.commit()
            _TABLE_ENSURED = True
        except Exception as e:
            logger.warning(f"Could not create llm_traces table: {e}")
        finally:
            conn.close()


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def record_trace(
    provider: str,
    model: str,
    operation: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    status: str = "success",
    error_message: str | None = None,
    metadata: dict | None = None,
) -> None:
    _ensure_table()

    cost_rates = COST_PER_1K_TOKENS.get(provider, {"input": 0.0, "output": 0.0})
    estimated_cost = (
        (input_tokens / 1000) * cost_rates["input"]
        + (output_tokens / 1000) * cost_rates["output"]
    )

    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO llm_traces
                        (provider, model, operation, input_tokens, output_tokens,
                         latency_ms, estimated_cost, status, error_message, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        provider, model, operation, input_tokens, output_tokens,
                        round(latency_ms, 1), round(estimated_cost, 6),
                        status, error_message,
                        __import__("json").dumps(metadata or {}),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Failed to record LLM trace: {e}")


def traced_llm_generate(llm, prompt: str, system_prompt: str = "") -> str:
    """Wrap an LLM generate() call with tracing."""
    input_text = (system_prompt + "\n" + prompt) if system_prompt else prompt
    input_tokens = _estimate_tokens(input_text)

    start = time.perf_counter()
    try:
        result = llm.generate(prompt, system_prompt=system_prompt)
        elapsed = (time.perf_counter() - start) * 1000
        output_tokens = _estimate_tokens(result)
        record_trace(
            provider=llm.name,
            model=getattr(llm, "model", "unknown"),
            operation="generate",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=elapsed,
        )
        logger.info(
            f"EVIDENCE_LLM_TRACE: provider={llm.name} op=generate "
            f"in={input_tokens}tok out={output_tokens}tok latency={elapsed:.0f}ms"
        )
        return result
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        record_trace(
            provider=llm.name,
            model=getattr(llm, "model", "unknown"),
            operation="generate",
            input_tokens=input_tokens,
            output_tokens=0,
            latency_ms=elapsed,
            status="error",
            error_message=str(e)[:500],
        )
        raise


def traced_embed(provider, texts: list[str]) -> list[list[float]]:
    """Wrap an embedding embed() call with tracing."""
    input_tokens = sum(_estimate_tokens(t) for t in texts)

    start = time.perf_counter()
    try:
        result = provider.embed(texts)
        elapsed = (time.perf_counter() - start) * 1000
        record_trace(
            provider=provider.name,
            model=getattr(provider, "model", "local"),
            operation="embed",
            input_tokens=input_tokens,
            output_tokens=0,
            latency_ms=elapsed,
            metadata={"text_count": len(texts), "dimensions": provider.dimensions},
        )
        logger.info(
            f"EVIDENCE_EMBED_TRACE: provider={provider.name} op=embed "
            f"texts={len(texts)} in={input_tokens}tok latency={elapsed:.0f}ms"
        )
        return result
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        record_trace(
            provider=provider.name,
            model=getattr(provider, "model", "local"),
            operation="embed",
            input_tokens=input_tokens,
            output_tokens=0,
            latency_ms=elapsed,
            status="error",
            error_message=str(e)[:500],
        )
        raise


def get_observability_stats(hours: int = 24) -> dict:
    """Return aggregated observability stats for the dashboard."""
    _ensure_table()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_calls,
                    COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                    COALESCE(SUM(estimated_cost), 0) AS total_cost,
                    ROUND(AVG(latency_ms)::numeric, 1) AS avg_latency_ms,
                    COUNT(*) FILTER (WHERE status = 'error') AS error_count
                FROM llm_traces
                WHERE created_at > NOW() - INTERVAL '%s hours'
                """,
                (hours,),
            )
            row = cur.fetchone()
            summary = {
                "total_calls": row[0],
                "total_input_tokens": row[1],
                "total_output_tokens": row[2],
                "total_cost": float(row[3]),
                "avg_latency_ms": float(row[4]) if row[4] else 0,
                "error_count": row[5],
                "hours": hours,
            }

            cur.execute(
                """
                SELECT provider, model, operation,
                    COUNT(*) AS calls,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    ROUND(AVG(latency_ms)::numeric, 1) AS avg_latency,
                    ROUND(MAX(latency_ms)::numeric, 1) AS max_latency,
                    COALESCE(SUM(estimated_cost), 0) AS cost,
                    COUNT(*) FILTER (WHERE status = 'error') AS errors
                FROM llm_traces
                WHERE created_at > NOW() - INTERVAL '%s hours'
                GROUP BY provider, model, operation
                ORDER BY calls DESC
                """,
                (hours,),
            )
            by_provider = [
                {
                    "provider": r[0], "model": r[1], "operation": r[2],
                    "calls": r[3], "input_tokens": r[4], "output_tokens": r[5],
                    "avg_latency_ms": float(r[6]) if r[6] else 0,
                    "max_latency_ms": float(r[7]) if r[7] else 0,
                    "cost": float(r[8]), "errors": r[9],
                }
                for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT provider, model, operation, input_tokens, output_tokens,
                       latency_ms, status, error_message, created_at
                FROM llm_traces
                WHERE created_at > NOW() - INTERVAL '%s hours'
                ORDER BY created_at DESC
                LIMIT 50
                """,
                (hours,),
            )
            recent = [
                {
                    "provider": r[0], "model": r[1], "operation": r[2],
                    "input_tokens": r[3], "output_tokens": r[4],
                    "latency_ms": round(r[5], 1), "status": r[6],
                    "error": r[7], "created_at": r[8].isoformat() if r[8] else None,
                }
                for r in cur.fetchall()
            ]

    finally:
        conn.close()

    return {
        "summary": summary,
        "by_provider": by_provider,
        "recent_traces": recent,
    }
