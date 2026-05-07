# Agent Cache

- Contrary to Act, Agent does multi-step automation
- So you can just do agent.execute("Complete the entire job application form")
  - internally breaks it into multiple atomic steps -> navivates pages, fill forms, waits for elements to render, extracts information
- This makes an LLM call each time. This gets expensive. So caching is critical

## Agent Cache Context

- version
- instruction
- startURL
- options (max steps are apprently 10)
- configSignature hash of agent config (why?) -> tracks model_id, system prompt, temperature etc.
- steps: sequence of steps as a list of AgentReplayStep object
- result: final result
- timestamp

AgentReplayStep block looks like:

- { type: "goto", url, waitUntil? }
- { type: "act", instruction, actions?, timeout? }
- { type: "fillForm", actions?, observeResults? }
- { type: "scroll", deltaX?, deltaY?, anchor? }
- { type: "wait", timeMs }
- { type: "navback", waitUntil? }
- { type: "keys", playwrightArguments }
- { type: "done" | "extract" | "screenshot" | "ariaTree" }


## Agent Cache Flow

### Preparation:
 - Hash of (instructions, startURL, options, config_signature, varKeys)
 - Return AgentCacheContext

### Lookup (tryReplay)
 - Hit or Miss

### Replay (if cache hit)
 - Follow the set of actions 

### Recording (if cache miss) {beginRecording, recordStep, endRecording}
 - Every step is recorded for caching. The URL, the actions taken etc.



