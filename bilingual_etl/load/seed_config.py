import json

from bilingual_etl.load.db import get_connection
from bilingual_etl.providers.prompt_store import DEFAULT_ENRICHMENT_PROMPT, DEFAULT_TRANSLATION_PROMPT

# Prompt text is imported from prompt_store.py rather than duplicated here —
# two copies of the same default drifting apart is exactly how a previous
# version of this file ended up seeding a stale enrichment prompt (missing
# the "match the input's language for every field" instruction) into the DB.
DEFAULT_CONFIG = {
    "llm_provider": {
        "active": "gemini",
        "options": ["groq", "openrouter", "gemini"],
    },
    "embedding_provider": {
        "active": "gemini",
        "options": ["gemini", "jina", "local_bge_m3"],
    },
    "prompt_translation": {
        "system_prompt": DEFAULT_TRANSLATION_PROMPT,
    },
    "prompt_enrichment": {
        "system_prompt": DEFAULT_ENRICHMENT_PROMPT,
    },
}


def seed_config(force=False):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for key, value in DEFAULT_CONFIG.items():
                if force:
                    cur.execute(
                        """
                        INSERT INTO app_config (key, value, updated_at)
                        VALUES (%s, %s, now())
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                        """,
                        (key, json.dumps(value)),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO app_config (key, value, updated_at)
                        VALUES (%s, %s, now())
                        ON CONFLICT (key) DO NOTHING
                        """,
                        (key, json.dumps(value)),
                    )
        conn.commit()
        print("Config seeded successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed_config()
