# What is it?

- Browserbase is an end-to-end platform to build and deploy agents that can browse and inteact with the web easily.

## Offerings

- Browser API (creating, controlling and observing browser sessions)
- Search API
- Fetch API
- Functions that deploy and run agents on demand or by schedule
- Model Gateway: routing requests depending on which LLM you want to use for agents

## Highlights

- Can integrate with existing web-scraping/interaction tools like Playwright, Selenium (check how they integrate)
- Stagehand is a better alternative for Selenium and Playwright because the latter ones are brittle.
  - Stagehand is better for AI-native workflows. Playwright better for traditional workflows and has extensive API support. Better when you need standard testing capabilities.
- Also connects with agent frameworks like CrewAI, LangChain and Mastra (in that case, do these functions/features comes up as tools? # TODO: Check)

## Stagehand

- Right balance betwen traditional tools (brittle) and fully agentic (unpredictable, hard to debug)
- Why not just use Claude Computer Use? -> Claude Computer Use takes screenshots at each step and extracts information. Stagehand on the other hand has its core functionality is built on top of Playwright. Better control.
    - Playwright also integrates with Clause Computer Use. Hard to find/handle iframe components using playwright along. So at that point, you can use computer use integration 
- Handles captchas, scaling up playwright instances, proxies etc.
- 
