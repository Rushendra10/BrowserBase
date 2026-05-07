import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from stagehand import AsyncStagehand
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("STAGEHAND_MODEL_NAME", "google/gemini-2.5-flash")

SEARCH_QUERY = "AI Engineer"
LOCATION = "United States"
NUM_JOBS = 10

CACHE_FILE = Path("linkedin_simple_cache.json")


def load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "search_query": SEARCH_QUERY,
        "location": LOCATION,
        "jobs": [],
    }


def save_cache(cache: dict) -> None:
    cache["updated_at"] = datetime.now(timezone.utc).isoformat()

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


async def main() -> None:
    cache = load_cache()

    if cache.get("jobs"):
        print(f"Loaded {len(cache['jobs'])} jobs from cache: {CACHE_FILE}")
        print(json.dumps(cache["jobs"], indent=2))
        return

    client = AsyncStagehand()

    session = await client.sessions.start(
        model_name=MODEL_NAME
    )

    try:
        search_url = (
            "https://www.linkedin.com/jobs/search/"
            f"?keywords={quote_plus(SEARCH_QUERY)}"
            f"&location={quote_plus(LOCATION)}"
        )

        print(f"Navigating to: {search_url}")
        await session.navigate(url=search_url)

        page_state_response = await session.extract(
            instruction=(
                "Determine whether this page is showing LinkedIn job search results, "
                "a login page, a security checkpoint, or an error page."
            ),
            schema={
                "type": "object",
                "properties": {
                    "pageType": {
                        "type": "string",
                        "enum": [
                            "job_results",
                            "login_required",
                            "security_checkpoint",
                            "error",
                            "unknown",
                        ],
                    },
                    "message": {"type": "string"},
                },
                "required": ["pageType"],
            },
        )

        page_state = page_state_response.data.result
        cache["page_state"] = page_state
        save_cache(cache)

        print("Page state:")
        print(json.dumps(page_state, indent=2))

        if page_state.get("pageType") != "job_results":
            print(
                "\nLinkedIn did not show job results directly. "
                "You may need an authenticated browser session or manual login."
            )
            return

        jobs_response = await session.extract(
            instruction=(
                f"Extract the first {NUM_JOBS} AI Engineer job listings visible on this LinkedIn jobs page. "
                "For each job, return the job title, company name, LinkedIn job URL, and apply URL if visible. "
                "If the apply URL is not visible, return null. "
                "Only include real job listings."
            ),
            schema={
                "type": "object",
                "properties": {
                    "jobs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "company": {"type": "string"},
                                "jobUrl": {"type": "string"},
                                "applyUrl": {"type": ["string", "null"]},
                            },
                            "required": ["title", "company", "jobUrl"],
                        },
                    }
                },
                "required": ["jobs"],
            },
        )

        jobs = jobs_response.data.result.get("jobs", [])[:NUM_JOBS]

        cache["jobs"] = jobs
        cache["search_url"] = search_url
        save_cache(cache)

        print(f"\nSaved {len(jobs)} jobs to {CACHE_FILE}")
        print(json.dumps(jobs, indent=2))

    finally:
        await session.end()
        print("\nSession ended.")


if __name__ == "__main__":
    asyncio.run(main())