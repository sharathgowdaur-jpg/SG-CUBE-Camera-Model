# SG CUBE — REAL-VOICE EXECUTION FAILURE ROOT-CAUSE ANALYSIS

## 1. Executive Summary
During real manual user testing of SG CUBE using real voice commands into the microphone, multiple commands with wake phrases failed to execute properly:
- `"Hey SG CUBE, set volume to 50 percent."`
- `"Hey SG CUBE, open settings."`
- `"Hey SG CUBE, search the web for latest AI news."`
- `"Hey SG CUBE, what did you just open?"`

The observed behaviors included:
- Refusal messages ("I cannot open applications")
- Incorrect/hallucinated conversational replies from Gemini Live
- Local routing returning `None` instead of executing Windows automation actions
- Disconnect between reported simulated test PASSes and actual microphone behavior

---

## 2. Root Cause 1: Lack of Speech Preprocessing & Wake Phrase Stripping
In [`CommandRouter.route_intent()`](file:///D:/VisionClaw-main/assistive/command_router.py#L111-L125), incoming speech transcripts were converted directly using `clean_text = text.strip().lower()`.
- Leading wake words (`"hey sg cube"`, `"sg cube"`, `"vision claw"`, `"jarvis"`, `"computer"`) were never stripped from the input string.
- Polite prefixes (`"please"`, `"could you please"`, `"can you"`, `"i want you to"`) were also left in place.
- Consequently, regex patterns anchored at line start (`^open\s+`, `^search\s+`, `^calculate\s+`) failed completely whenever the user included the wake word or polite words in their spoken sentence.
- Example: `"Hey SG CUBE, open settings."` $\to$ routed to `GENERAL` instead of `AUTOMATION_OPEN_APP`.

---

## 3. Root Cause 2: Trailing Punctuation Collisions with Strict Regex Anchors
Real-time Speech-to-Text (STT) engines append punctuation to finalized sentences (e.g. periods, question marks, commas):
- Regex patterns using end-of-string anchors `$` (e.g. `ordinal_res_match = re.search(r'...(?:\s+result)?$', clean_text)`) failed to match utterances ending with a period (`.`) or question mark (`?`).
- Patterns capturing final text into parameters (e.g. `r'^search\s+for\s+(.+)$'`) captured the trailing punctuation directly into search queries (e.g. `"latest AI news."`), resulting in malformed web searches and database queries.

---

## 4. Root Cause 3: Preemption by Cloud LLM (Gemini Live) Fallback
In [`visionclaw_gui.py`](file:///D:/VisionClaw-main/visionclaw_gui.py#L16034-L16260):
- When `VisionEngine.process_user_speech_query()` returned `None` (due to `GENERAL` intent routing), control fell back to Gemini Live.
- Gemini Live was initialized with only 6 perception tools (`get_ambient_status`, `scan_product_details`, `enroll_person_face`, `save_reminder_note`, `recall_user_memory`, `manage_voice_security`).
- It lacked declarations for system control (`open_application`, `set_system_volume`, `search_web`, `get_last_action`).
- Consequently, Gemini Live had no way to control Windows or search the web locally, producing conversational refusals such as *"I cannot open applications on your computer"* or fabricating plausible text.

---

## 5. Root Cause 4: Lack of Real-World OS State Verification
In [`AutomationManager._exec_open_app()`](file:///D:/VisionClaw-main/assistive/automation_manager.py#L848-L895):
- Applications were marked as `SUCCESS` without verifying that the process actually remained running and did not crash or exit with an error code.
- Actions reported success without allowing an observation window (300ms) to check actual Windows process creation.

---

## 6. Root Cause 5: Premature Substring Matching in Memory Query Cleaner
In [`MemoryManager.recall_memory()`](file:///D:/VisionClaw-main/assistive/memory_manager.py#L671-L675):
- The regex `r'^(?:where did i say|...)\s+(?:my|the|a|an|about)?\s*'` had `'a'` before `'about'`.
- When querying `"what did i say about my laptop"`, the `'a'` matched the first character of `'about'`, leaving `'bout my laptop'` as the search term, causing memory retrieval to fail.
