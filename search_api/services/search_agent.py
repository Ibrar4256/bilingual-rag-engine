"""
Search Agent — LLM-driven tool-use pattern for intelligent query routing.

The agent receives a natural language question, decides which search tool(s)
to call (category search, company match, single-company lookup), executes
them, and synthesizes the results into a final answer.

This demonstrates the "tool-use" / "function-calling" pattern used in
production AI agents — the LLM doesn't search directly, it plans which
tools to use based on the user's intent.
"""

import time

from loguru import logger

from bilingual_etl.providers.llm_provider import get_llm_provider, generate_with_retry
from bilingual_etl.providers.guardrails import validate_json_response
from search_api.services.search import search_table

TOOLS_DESCRIPTION = """You have access to these search tools:

1. search_categories(query, language, limit) — Search product/service categories.
   Use when: the user asks about types of products, services, or categories.

2. search_companies(query, language, limit) — Find matching companies.
   Use when: the user asks about companies, suppliers, or manufacturers.

3. search_single_company(company_id, query, language) — Search within one company's data.
   Use when: the user asks about a specific company by ID.

Rules:
- You may call multiple tools if the question spans both categories and companies.
- Set language to "hu" for Hungarian queries, "en" for English, or null for auto-detect.
- Return your plan as JSON with this schema:
  {"tools": [{"name": "search_categories"|"search_companies"|"search_single_company", "args": {"query": "...", "language": "..."|null, "limit": 5, "company_id": "..."}}]}
"""

SYNTHESIS_PROMPT = """You are a B2B search assistant for a Hungarian industrial marketplace.
Using the search results below, answer the user's question.
Be concise. Cite specific category IDs or company IDs when relevant.
If results are empty, say so honestly.
If the question is in Hungarian, answer in Hungarian. If in English, answer in English.
"""


def _plan_tools(query: str) -> list[dict]:
    """Ask the LLM which tools to call for this query."""
    llm = get_llm_provider()

    plan_prompt = (
        f"{TOOLS_DESCRIPTION}\n\n"
        f"User question: {query}\n\n"
        f"Return ONLY a JSON object with your tool plan. No explanation."
    )

    raw = generate_with_retry(llm, plan_prompt, system_prompt="You are a search planning agent.")

    data, errors = validate_json_response(raw, required_fields=["tools"])
    if errors or data is None:
        logger.warning(f"Agent plan validation failed: {errors}. Falling back to category search.")
        return [{"name": "search_categories", "args": {"query": query, "language": None, "limit": 5}}]

    tools = data.get("tools", [])
    if not tools or not isinstance(tools, list):
        return [{"name": "search_categories", "args": {"query": query, "language": None, "limit": 5}}]

    return tools


def _execute_tool(tool: dict) -> dict:
    """Execute a single tool call and return results."""
    name = tool.get("name", "")
    args = tool.get("args", {})

    if name == "search_categories":
        table = "category_vectors"
    elif name == "search_companies":
        table = "company_vectors"
    elif name == "search_single_company":
        table = "company_vectors"
    else:
        return {"tool": name, "error": f"Unknown tool: {name}", "results": []}

    try:
        raw = search_table(
            table=table,
            query=args.get("query", ""),
            limit=args.get("limit", 5),
            lang_override=args.get("language"),
            rerank=True,
        )
        id_col = "category_id" if table == "category_vectors" else "company_id"
        text_col = "narrative" if table == "category_vectors" else "content_chunk"

        summaries = []
        for r in raw["results"][:5]:
            summaries.append({
                "id": str(r.get(id_col, "?")),
                "text": r.get(text_col, "")[:300],
                "language": r.get("language", ""),
                "score": r.get("rrf_score", 0),
            })

        return {
            "tool": name,
            "query": args.get("query", ""),
            "result_count": len(raw["results"]),
            "results": summaries,
            "detected_language": raw.get("detected_language", ""),
        }
    except Exception as e:
        logger.warning(f"Agent tool execution failed: {name} — {e}")
        return {"tool": name, "error": str(e), "results": []}


def _synthesize(query: str, tool_results: list[dict]) -> str:
    """Ask the LLM to synthesize tool results into a final answer."""
    llm = get_llm_provider()

    context_parts = []
    for tr in tool_results:
        if tr.get("error"):
            context_parts.append(f"Tool '{tr['tool']}' failed: {tr['error']}")
            continue

        context_parts.append(f"Tool '{tr['tool']}' returned {tr['result_count']} results:")
        for r in tr["results"]:
            context_parts.append(
                f"  - [{r['id']}] ({r['language']}, score={r['score']:.4f}): {r['text'][:200]}"
            )

    context = "\n".join(context_parts)

    synthesis_prompt = (
        f"Search results:\n\n{context}\n\n"
        f"---\n"
        f"User question: {query}\n\n"
        f"Answer the question based on the search results above."
    )

    return generate_with_retry(llm, synthesis_prompt, system_prompt=SYNTHESIS_PROMPT)


def run_search_agent(query: str) -> dict:
    """Full agent loop: plan → execute → synthesize."""
    start = time.perf_counter()

    logger.info(f"EVIDENCE_AGENT_START: query={query!r}")

    plan = _plan_tools(query)
    plan_time = (time.perf_counter() - start) * 1000

    logger.info(f"EVIDENCE_AGENT_PLAN: tools={[t['name'] for t in plan]}")

    tool_results = []
    for tool in plan:
        result = _execute_tool(tool)
        tool_results.append(result)

    exec_time = (time.perf_counter() - start) * 1000 - plan_time

    answer = _synthesize(query, tool_results)

    total_time = (time.perf_counter() - start) * 1000

    logger.info(
        f"EVIDENCE_AGENT_COMPLETE: query={query!r} "
        f"tools_used={len(plan)} plan_ms={plan_time:.0f} "
        f"exec_ms={exec_time:.0f} total_ms={total_time:.0f}"
    )

    return {
        "answer": answer,
        "plan": plan,
        "tool_results": [
            {
                "tool": tr["tool"],
                "query": tr.get("query", ""),
                "result_count": tr.get("result_count", 0),
                "error": tr.get("error"),
            }
            for tr in tool_results
        ],
        "timing": {
            "plan_ms": round(plan_time, 1),
            "execution_ms": round(exec_time, 1),
            "synthesis_ms": round(total_time - plan_time - exec_time, 1),
            "total_ms": round(total_time, 1),
        },
    }
