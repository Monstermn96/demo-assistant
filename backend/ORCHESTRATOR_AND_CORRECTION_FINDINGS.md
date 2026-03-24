# Orchestrator, Knowledge Retriever, and Correction/Cleanup Flow — Findings

## Fixes applied (implementation summary)

The following changes were implemented based on this document and arim_empty_rules_profile_and_cleanup_findings.md:
- System prompt (system.md) and fallback (prompts.py): added correction/cleanup instruction block.
- Calendar tool: extended descriptions for fix duplicates/clean up; added delete_events batch action.
- Calendar API: added bulk-delete endpoint.
- load_user_context: documented that all procedural rules are loaded (no category filter).
- Learning agent: added data_management to category examples; observe_interaction awaited; learning_observe prompt updated for cleanup preference.
- Orchestrator: correction keyword detection and injection of cleanup instruction block.

## 1. How the orchestrator uses the knowledge_retriever (get_rules / get_profile)

### Where the “knowledge_retriever” lives

- The **knowledge_retriever** is the **KnowledgeAgent** (`app/agents/knowledge_agent.py`), which has `name = "knowledge_retriever"`.
- The orchestrator does **not** expose `get_rules` or `get_profile` to the **main** LLM. Those tools exist only inside the KnowledgeAgent.

### When get_rules / get_profile are used

**A. Always, before any LLM call (user context)**

- In `run_orchestrated_agent` the orchestrator first loads **user context** and appends it to the system prompt:
  - It calls `MemoryClient.load_user_context(user_id)` (orchestrator, ~line 88).
  - `load_user_context` (in `app/memory/client.py`) internally calls:
    - `MemoryClient.get_profile(user_id)`
    - `MemoryClient.get_procedural_rules(user_id)` (top 10 rules)
  - That text is added as:  
    `[User context from memory — use this to personalize your responses]\n{user_context}`  
  So **profile and procedural rules are always injected into the main system prompt** before the first turn; the main LLM never “decides” to call get_rules/get_profile — they are already in context.

**B. Optionally, via the knowledge agent (enrichment)**

- If `enable_knowledge` is true and there is at least one user message, the orchestrator then calls:
  - `knowledge_agent.enrich_context(last_user_msg, ctx, on_event=on_event)` (orchestrator, ~94–104).
- Inside `enrich_context`:
  - A **separate** LLM run is performed for the knowledge agent with a single user message like:  
    `Find any relevant knowledge, rules, or preferences for this query: {query}`  
    (from the `knowledge_query` prompt, with `{query}` = last user message).
  - That knowledge-agent LLM **can** call tools: `search_knowledge`, `get_rules`, `get_profile` (up to `max_rounds=3`).
  - So **get_rules** and **get_profile** are called **only when the knowledge-agent LLM decides** to use those tools during this enrichment step.
- The result of enrichment is appended to the system prompt as:  
  `[Relevant knowledge from memory]\n{knowledge_context}`  
  and the **main** chat then runs with this enriched system prompt.

### Summary for (1)

| What | When | Who decides |
|------|------|-------------|
| Profile + procedural rules in main prompt | **Before** every main LLM turn | Orchestrator always (via `load_user_context`) |
| get_rules / get_profile as tools | Only during **knowledge enrichment** | Knowledge-agent LLM (only when it chooses to call them) |

So: **get_rules/get_profile are not “before handling a query” in the sense of the main agent — they are (1) always baked in via load_user_context, and (2) optionally used again by the knowledge sub-agent when it decides to call those tools during enrichment.**

---

## 2. How the orchestrator handles user corrections (“you scheduled duplicates”, “fix that”, “clean up the mess”)

### No dedicated correction or cleanup step

- The orchestrator has **no** separate “correction” or “cleanup” phase.
- Flow is: **user context → optional knowledge enrichment → system prompt + conversation → loop**: main LLM generates response and/or tool calls → orchestrator executes tools → repeat until no more tool calls or limit.

So when the user sends a correction:

1. **Infer what went wrong** — The main LLM infers this only from conversation history and tool results (no dedicated step).
2. **Plan full cleanup** — There is no code or phase that (a) detects “user is asking for a correction/cleanup”, (b) enumerates all affected items (e.g. all duplicates), or (c) forces a full cleanup plan.
3. **Execute** — The main LLM can call the `calendar` tool with `action: list` and then `action: delete` (one `event_id` per call). The calendar tool only supports **single-event delete**; there is no batch delete or “delete all duplicates” API.

So:

- **Correction/cleanup is entirely emergent** from the main LLM choosing to list events and then delete some.
- There is **no** guarantee the model will (a) list a wide enough range to find all duplicates, (b) delete **all** duplicates, or (c) avoid leaving “partial” cleanup. Partial fix is expected if the model stops after one or a few deletes or lists a narrow window.

---

## 3. Documentation or prompts that say to “clean up completely”

- **None found.**  
- Checked:
  - `backend/app/llm/prompts.py` — fallback system prompt: no mention of corrections, duplicates, or “clean up completely”.
  - `backend/prompts/system.md` — main system prompt (orchestrator): same; no correction/cleanup guidance.
  - `backend/prompts/knowledge_agent.md`, `knowledge_query.md` — no cleanup/correction instructions.
  - Learning agent prompts mention “corrections” only in the sense of **recording** user corrections/preferences for learning, not for **performing** full cleanup.
  - `backend/app/tools/calendar.py` — no description text telling the LLM to “remove all duplicates” or “clean up completely” when the user asks to fix or clean up.

So the absence of any instruction to “clean up completely” or “fix all duplicates” when the user corrects or asks to clean up is a plausible reason why the AI often does only a **partial** fix.

---

## 4. Summary and suggested changes

### (1) Exact flow for get_rules / get_profile

- **Main prompt (every turn)**  
  - Orchestrator calls `MemoryClient.load_user_context(user_id)`.  
  - That calls `get_profile(user_id)` and `get_procedural_rules(user_id)`, formats them, and appends to system prompt.  
  - Main LLM never sees get_rules/get_profile as tools; it just sees the pre-filled “[User context from memory]” block.

- **Knowledge enrichment (when enable_knowledge and messages exist)**  
  - Orchestrator calls `knowledge_agent.enrich_context(last_user_msg, ctx, on_event)`.  
  - Knowledge agent runs its own LLM with tools: `search_knowledge`, `get_rules`, `get_profile`.  
  - get_rules/get_profile are invoked **only when the knowledge-agent LLM** chooses to call them (up to 3 rounds).  
  - Result is appended as “[Relevant knowledge from memory]” and the main chat runs with that.

### (2) Correction/cleanup flow and full cleanup

- **Current:** Single loop: main LLM + calendar (list/delete one-by-one). No dedicated correction step; no enforcement of “clean up all”.
- **Full cleanup is not enforced** — no code or prompt that (a) infers “user wants full cleanup”, (b) plans “list all affected, then delete all”, or (c) requires the model to continue until everything is fixed.

### (3) Suggested code and prompt changes so corrections “clean up the mess”

**Prompts (lowest friction)**

1. **System prompt (orchestrator)**  
   In `backend/prompts/system.md` (and the fallback in `backend/app/llm/prompts.py`), add a short block, e.g.:

   - When the user corrects you or asks to fix/clean up something (e.g. “you scheduled duplicates”, “fix that”, “clean up the mess”):
     - First **list** the relevant items (e.g. calendar events in the affected time range or that match the description) so you see the full picture.
     - Then **remove or fix every** duplicate or mistaken item; do not stop after one or two — clean up completely and confirm when done.

2. **Calendar tool description**  
   In `backend/app/tools/calendar.py`, in the tool schema, extend the `description` (and optionally the `action` / `list` description) to say that for user requests to “fix duplicates” or “clean up” events, the assistant should list the relevant range first, then delete **all** duplicate or unwanted events (one delete per event), and not stop until the cleanup is complete.

**Optional code improvements**

3. **Batch delete (convenience)**  
   Add a calendar action (e.g. `delete_events` with `event_ids: list[int]`) so the main LLM can delete many events in one tool call instead of N separate `delete` calls. This reduces the chance it stops after one delete and makes “delete all duplicates” a single, explicit step.

4. **Correction hint in context (optional)**  
   If the last user message looks like a correction (e.g. keywords: “duplicate”, “fix that”, “clean up”, “wrong”, “remove them”), append a one-line instruction to the system or user block: “The user is asking for a correction/cleanup; list all affected items then fix or remove every one.”

5. **Structured “cleanup” step (larger change)**  
   Add an optional phase before or alongside the first main-LLM turn: when the last user message is classified as a correction/cleanup (e.g. simple keyword or classifier), inject a short system line: “This turn is a correction/cleanup: you must list all affected items, then remove or fix every one, and confirm when done.” This keeps the existing architecture but makes the expectation explicit for the model.

Implementing (1) and (2) in the prompts and (optionally) (3) in the calendar tool should already push the assistant toward “clean up the mess” behavior; (4) and (5) can be added if partial fixes persist.
