import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from stagehand import AsyncStagehand

load_dotenv()


CACHE_DIR = "./stagehand-cache/open-source-hype"
OUTPUT_PATH = Path("top_open_source_hype.json")

MODEL_NAME = os.getenv("STAGEHAND_MODEL_NAME", "openai/gpt-4.1-mini")


EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tools": {
            "type": "array",
            "description": "Top 5 currently hyped open-source tools/libraries/software projects.",
            "items": {
                "type": "object",
                "properties": {
                    "rank": {"type": "integer"},
                    "name": {"type": "string"},
                    "category": {"type": "string"},
                    "homepage_or_repo": {"type": "string"},
                    "why_it_is_trending": {"type": "string"},
                    "short_summary": {"type": "string"},
                    "what_it_does_differently": {"type": "string"},
                    "ideal_user": {"type": "string"},
                    "evidence_seen_on_page": {"type": "string"},
                },
                "required": [
                    "rank",
                    "name",
                    "category",
                    "homepage_or_repo",
                    "why_it_is_trending",
                    "short_summary",
                    "what_it_does_differently",
                    "ideal_user",
                    "evidence_seen_on_page",
                ],
            },
        }
    },
    "required": ["tools"],
}


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_session_id(session_response: Any) -> str:
    """
    Handles small SDK response-shape differences across Stagehand versions.
    """
    if hasattr(session_response, "id"):
        return session_response.id

    data = getattr(session_response, "data", None)
    if data is not None:
        for attr in ("session_id", "sessionId", "id"):
            if hasattr(data, attr):
                return getattr(data, attr)

        if isinstance(data, dict):
            return data.get("session_id") or data.get("sessionId") or data.get("id")

    if isinstance(session_response, dict):
        data = session_response.get("data", {})
        return data.get("session_id") or data.get("sessionId") or data.get("id")

    raise RuntimeError(f"Could not determine session id from response: {session_response}")


def get_result(response: Any) -> Any:
    """
    Handles response.data.result style and dict style.
    """
    data = getattr(response, "data", None)
    if data is not None:
        if hasattr(data, "result"):
            return data.result
        if isinstance(data, dict):
            return data.get("result")

    if isinstance(response, dict):
        return response.get("data", {}).get("result")

    return response


async def main() -> None:

    browserbase_api_key = require_env("BROWSERBASE_API_KEY")
    model_api_key = require_env("MODEL_API_KEY")
    browserbase_project_id = os.getenv("BROWSERBASE_PROJECT_ID")

    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

    client_kwargs = {
        "browserbase_api_key": browserbase_api_key,
        "model_api_key": model_api_key,
    }

    if browserbase_project_id:
        client_kwargs["browserbase_project_id"] = browserbase_project_id

    async with AsyncStagehand(**client_kwargs) as client:
        # Stagehand v3 Python supports extra_body for not-yet-typed request fields.
        # The official caching docs describe file-based cache via cacheDir.
        # If your installed version/server accepts this field, this enables Stagehand's local file cache.
        session_response = await client.sessions.start(
            model_name=MODEL_NAME,
            browser={"type": "browserbase"},
            verbose=1,
            extra_body={
                "cacheDir": CACHE_DIR,
                "selfHeal": True,
            },
        )

        session_id = get_session_id(session_response)
        print(f"Started Stagehand session: {session_id}")
        print(f"Using cache dir: {CACHE_DIR}")

        try:
            # Source 1: GitHub Trending gives current repository momentum.
            await client.sessions.navigate(
                session_id,
                url="https://github.com/trending?since=weekly",
            )

            github_extract = await client.sessions.extract(
                session_id,
                instruction=(
                    "From this GitHub Trending weekly page, identify open-source repositories "
                    "that appear especially hyped right now. Focus on developer tools, AI tools, "
                    "libraries, frameworks, infrastructure software, coding agents, databases, "
                    "and productivity tools. Extract candidates with repo names, links, categories, "
                    "and visible evidence such as stars today, descriptions, or ranking."
                ),
                schema={
                    "type": "object",
                    "properties": {
                        "candidates": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "repo_url": {"type": "string"},
                                    "description": {"type": "string"},
                                    "language": {"type": "string"},
                                    "visible_evidence": {"type": "string"},
                                },
                                "required": [
                                    "name",
                                    "repo_url",
                                    "description",
                                    "visible_evidence",
                                ],
                            },
                        }
                    },
                    "required": ["candidates"],
                },
            )

            github_candidates = get_result(github_extract)

            # Source 2: Hacker News front page gives extra hype/context signal.
            await client.sessions.navigate(
                session_id,
                url="https://news.ycombinator.com",
            )

            hn_extract = await client.sessions.extract(
                session_id,
                instruction=(
                    "Extract posts on the Hacker News front page related to open-source tools, "
                    "developer libraries, AI software, programming frameworks, infrastructure, "
                    "databases, browsers, agents, or dev productivity. Include title, URL if visible, "
                    "points/comments if visible, and why the item seems relevant."
                ),
                schema={
                    "type": "object",
                    "properties": {
                        "posts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "url": {"type": "string"},
                                    "visible_evidence": {"type": "string"},
                                    "relevance": {"type": "string"},
                                },
                                "required": ["title", "visible_evidence", "relevance"],
                            },
                        }
                    },
                    "required": ["posts"],
                },
            )

            hn_candidates = get_result(hn_extract)

            # More than basic: ask Stagehand's agent to synthesize across both extracted sources.
            # This is intentionally not just scraping a single page.
            synthesis_prompt = f"""
            You are building a concise developer intelligence report.

            Use these two extracted evidence sets:

            GitHub Trending candidates:
            {json.dumps(github_candidates, indent=2)}

            Hacker News candidates:
            {json.dumps(hn_candidates, indent=2)}

            Pick the top 5 open-source tools/libraries/software projects that seem most hyped now.
            Prefer projects that are clearly open-source and relevant to developers.
            Avoid generic companies unless the tool/library itself is open-source.

            For each, explain:
            - what it is
            - why it seems hyped
            - what it does differently from older/common alternatives
            - who should care about it

            Return only structured data matching the requested schema.
            """

            final_extract = await client.sessions.extract(
                session_id,
                instruction=synthesis_prompt,
                schema=EXTRACTION_SCHEMA,
            )

            result = get_result(final_extract)

            output = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "model": MODEL_NAME,
                "cache_dir": CACHE_DIR,
                "result": result,
            }

            OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

            print("\nTop 5 open-source hype report")
            print("=" * 40)

            tools = result.get("tools", []) if isinstance(result, dict) else []
            for tool in tools:
                print(f"\n{tool['rank']}. {tool['name']} — {tool['category']}")
                print(f"Repo/Homepage: {tool['homepage_or_repo']}")
                print(f"Summary: {tool['short_summary']}")
                print(f"What is different: {tool['what_it_does_differently']}")
                print(f"Why trending: {tool['why_it_is_trending']}")

            print(f"\nSaved structured output to: {OUTPUT_PATH.resolve()}")

        finally:
            await client.sessions.end(session_id)
            print("Ended Stagehand session.")


if __name__ == "__main__":
    asyncio.run(main())