"""
Admin config API (R24, R25 backend)

CRUD for app_config table: provider selection, system prompt editing.
All routes require JWT auth via `require_admin`.
"""

import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel

from search_api.db import get_connection
from search_api.routers.auth import require_admin

router = APIRouter(prefix="/admin/config", tags=["admin"], dependencies=[Depends(require_admin)])


def _check_provider_available(key: str, value: dict) -> None:
    active = value.get("active") if isinstance(value, dict) else None
    if not active:
        return

    if key == "llm_provider":
        required_keys = {
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "9router": "NINE_ROUTER_API_KEY",
            "cerebras": "CEREBRAS_API_KEY",
            "sambanova": "SAMBANOVA_API_KEY",
            "custom_openai": "CUSTOM_OPENAI_URL",
        }
        env_key = required_keys.get(active)
        if env_key and not os.getenv(env_key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot activate LLM provider '{active}': {env_key} is not set in .env",
            )

    if key == "embedding_provider":
        if active == "gemini" and not os.getenv("GEMINI_API_KEY"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GEMINI_API_KEY is not set")
        if active == "jina" and not os.getenv("JINA_API_KEY"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JINA_API_KEY is not set")
        if active == "9router" and not os.getenv("NINE_ROUTER_API_KEY"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="NINE_ROUTER_API_KEY is not set")
        if active == "local_bge_m3":
            try:
                import sentence_transformers  # noqa: F401
            except ImportError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot activate 'local_bge_m3': sentence-transformers is not installed",
                )


class ConfigValue(BaseModel):
    value: Any


class ConfigEntry(BaseModel):
    key: str
    value: Any


class ProviderAvailability(BaseModel):
    provider: str
    available: bool
    reason: str | None = None


@router.get("/providers/availability", response_model=list[ProviderAvailability])
def check_provider_availability():
    results = []
    llm_providers = {
        "groq": ("GROQ_API_KEY", None),
        "openrouter": ("OPENROUTER_API_KEY", None),
        "gemini": ("GEMINI_API_KEY", None),
        "9router": ("NINE_ROUTER_API_KEY", None),
        "cerebras": ("CEREBRAS_API_KEY", None),
        "sambanova": ("SAMBANOVA_API_KEY", None),
        "custom_openai": ("CUSTOM_OPENAI_URL", None),
    }
    for name, (env_key, _) in llm_providers.items():
        available = bool(os.getenv(env_key))
        results.append(ProviderAvailability(
            provider=f"llm:{name}",
            available=available,
            reason=None if available else f"{env_key} not set",
        ))

    emb_providers = [
        ("gemini", lambda: bool(os.getenv("GEMINI_API_KEY")), "GEMINI_API_KEY not set"),
        ("jina", lambda: bool(os.getenv("JINA_API_KEY")), "JINA_API_KEY not set"),
        ("9router", lambda: bool(os.getenv("NINE_ROUTER_API_KEY")), "NINE_ROUTER_API_KEY not set"),
    ]
    for name, check, reason in emb_providers:
        available = check()
        results.append(ProviderAvailability(
            provider=f"embedding:{name}", available=available, reason=None if available else reason,
        ))

    try:
        import sentence_transformers  # noqa: F401
        results.append(ProviderAvailability(provider="embedding:local_bge_m3", available=True))
    except ImportError:
        results.append(ProviderAvailability(
            provider="embedding:local_bge_m3", available=False, reason="sentence-transformers not installed",
        ))

    return results


@router.get("/", response_model=list[ConfigEntry])
def list_config():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM app_config ORDER BY key")
            rows = cur.fetchall()
    finally:
        conn.close()
    return [ConfigEntry(key=r[0], value=r[1]) for r in rows]


@router.get("/{key}", response_model=ConfigEntry)
def get_config(key: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM app_config WHERE key = %s", (key,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Config key '{key}' not found")
    return ConfigEntry(key=row[0], value=row[1])


@router.put("/{key}", response_model=ConfigEntry)
def set_config(key: str, body: ConfigValue):
    _check_provider_available(key, body.value)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_config (key, value, updated_at)
                VALUES (%s, %s, now())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                RETURNING key, value
                """,
                (key, json.dumps(body.value)),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    logger.info(f"EVIDENCE_ADMIN_CONFIG_UPDATE: key={key}")
    return ConfigEntry(key=row[0], value=row[1])


etl_router = APIRouter(tags=["etl"])

_etl_process = None


def _set_etl_status(new_status: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM app_config WHERE key = 'etl_progress'")
            row = cur.fetchone()
            if row:
                val = row[0]
                val["status"] = new_status
                cur.execute(
                    "UPDATE app_config SET value = %s WHERE key = 'etl_progress'",
                    (json.dumps(val),),
                )
                conn.commit()
    finally:
        conn.close()


@etl_router.get("/admin/etl/progress", dependencies=[Depends(require_admin)])
def get_etl_progress():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM app_config WHERE key = 'etl_progress'")
            row = cur.fetchone()
    finally:
        conn.close()
    progress = row[0] if row else {"status": "idle"}

    global _etl_process
    if _etl_process is not None:
        retcode = _etl_process.poll()
        if retcode is not None:
            _etl_process = None
            if progress.get("status") == "running":
                new_status = "complete" if retcode == 0 else "failed"
                progress["status"] = new_status
                _set_etl_status(new_status)
        else:
            progress["subprocess_alive"] = True
    elif progress.get("status") == "running":
        progress["status"] = "stopped"
        _set_etl_status("stopped")

    return progress


@etl_router.post("/admin/etl/start", dependencies=[Depends(require_admin)])
def start_etl(force_enrichment: bool = False):
    import subprocess
    import sys

    global _etl_process
    if _etl_process is not None and _etl_process.poll() is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ETL is already running")

    cmd = [sys.executable, "-m", "bilingual_etl.scripts.main_etl"]
    if force_enrichment:
        cmd.append("--force-enrichment")

    _etl_process = subprocess.Popen(cmd, cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    logger.info(f"EVIDENCE_ETL_START: pid={_etl_process.pid} force_enrichment={force_enrichment}")
    return {"status": "started", "pid": _etl_process.pid}


@etl_router.post("/admin/etl/stop", dependencies=[Depends(require_admin)])
def stop_etl():
    import signal

    global _etl_process
    if _etl_process is None or _etl_process.poll() is not None:
        _etl_process = None
        _set_etl_status("stopped")
        return {"status": "stopped", "pid": None}

    _etl_process.send_signal(signal.SIGTERM)
    try:
        _etl_process.wait(timeout=10)
    except Exception:
        _etl_process.kill()
    pid = _etl_process.pid
    _etl_process = None
    _set_etl_status("stopped")
    logger.info(f"EVIDENCE_ETL_STOP: pid={pid}")
    return {"status": "stopped", "pid": pid}


@etl_router.get("/admin/analytics", dependencies=[Depends(require_admin)])
def get_analytics():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables WHERE table_name = 'search_analytics'
                )
            """)
            if not cur.fetchone()[0]:
                return {"total_queries": 0, "zero_result_queries": [], "top_queries": [], "recent": []}

            cur.execute("SELECT COUNT(*) FROM search_analytics")
            total = cur.fetchone()[0]

            cur.execute("""
                SELECT query, COUNT(*) as cnt
                FROM search_analytics WHERE result_count = 0
                GROUP BY query ORDER BY cnt DESC LIMIT 10
            """)
            zero_results = [{"query": r[0], "count": r[1]} for r in cur.fetchall()]

            cur.execute("""
                SELECT query, COUNT(*) as cnt, ROUND(AVG(response_time_ms)::numeric, 1) as avg_ms
                FROM search_analytics
                GROUP BY query ORDER BY cnt DESC LIMIT 10
            """)
            top_queries = [{"query": r[0], "count": r[1], "avg_ms": float(r[2])} for r in cur.fetchall()]

            cur.execute("""
                SELECT query, endpoint, language, result_count, response_time_ms, created_at
                FROM search_analytics ORDER BY created_at DESC LIMIT 20
            """)
            recent = [{
                "query": r[0], "endpoint": r[1], "language": r[2],
                "result_count": r[3], "response_time_ms": round(r[4], 1),
                "created_at": r[5].isoformat() if r[5] else None,
            } for r in cur.fetchall()]
    finally:
        conn.close()

    return {"total_queries": total, "zero_result_queries": zero_results, "top_queries": top_queries, "recent": recent}
