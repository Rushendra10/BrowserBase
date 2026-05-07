# Caching in Stagehand

- Two parallel caching systems:
  - ActCache - for individual act() calls (single, deterministic steps)
  - AgentCache - for agent.execute() calls (multi-step workflows)

- Two storage options:
  - File system (writes to disk)
  - In-Memory Store (mostly for use on servers)

- Storage Methods:
  - readJson(filename)
  - writeJson(filename, data)
  - getter method

- Flow for stagehand.act()
  - Preparing the context to be cached
    - cleaning instruction (no whitespaces)
    - Flattening all variable names in json and sorting them
    - get current page URL
    - create a SHA56 hash using (instruction, url, var_names)
    - return cachekey

  - Lookup
    - check if cache is enabled
    - prepare context as done in prev step
    - Look for that cachekey in memory/file
    - Hit validation:
      - version check
      - actions array not empty
      - all variables match and present
      - if all yes, then hit else return NULL
    - Replay Phase:
      - For each cached action:
        - selector picks it
        - execute the action
        - collect results
      - self-healing:
        - Compare original vs updated actions
        - If any change, then refresh cache entry
        - log saying act cache entry has been updated after self-heal

            return ActResult()

  - Storage
    - If cache had missed, then we store the results: create CachedActEntry (version, instruction, url, varkeys, actions etc)
    - log "act cache stored"

## Cache Miss Scenario

- User calls stagehand.act("Click on the Submit button")
- Check cache: no entry found
- Call LLM: "What selector is the Submit button?"
- LLM points to the selector
- Execute: Click on that button
- STORE in cache: {"selector": < id >, "method": "click"}

## Cache Hit (Same Instruction, Same URL)

- User calls stagehand.act("Click on the Submit button")
- Check cache: Entry found
  - REPLAY:
    - Retrieve the cached selector
    - Find elem in DOM
    - Click it
      - If it works, happy case
      - If selector does not exist, fail gracefuly
  - If replay succeeded and selector is the same, then cache stays the same
  - If reply succeeses but selector changes, the cache is updated (They call this Self Heal)
  