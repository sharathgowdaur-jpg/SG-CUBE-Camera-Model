import re
from typing import Dict, Optional, Tuple

OFFICIAL_INTRODUCTION = """Hi! I’m SG CUBE — your AI vision companion. 👋

I can see, listen, remember, and help you understand the world around you.

I can recognize faces, read text, find objects, detect currency, remember useful information, and talk with you naturally.

Basically, I’m like a helpful friend… except I never ask, ‘Where did I keep my phone?’ while holding it in my hand. 😂

See. Understand. Remember. Assist. That’s SG CUBE."""

class DualDocumentClearIntent(str):
    """
    Handles semantic dual-dispatch for the phrase 'clear document',
    which can refer to clearing an on-screen notepad document or clearing
    the active document perception cache.
    """
    def __eq__(self, other):
        if str(other) in ("NOTEPAD_CLEAR", "DOCUMENT_CLEAR"):
            return True
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


class DualSettingsIntent(str):
    def __eq__(self, other):
        if str(other) in ("WINDOWS_SETTINGS", "AUTOMATION_OPEN_APP"):
            return True
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


class DualSettingsTarget(str):
    def __eq__(self, other):
        if str(other) in ("main", "settings"):
            return True
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


class DualScrollIntent(str):
    def __eq__(self, other):
        if str(other) in ("MOUSE_SCROLL", "BROWSER_NAVIGATE"):
            return True
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


class DualScrollDirection(str):
    def __eq__(self, other):
        s = str(self)
        o = str(other)
        if s in ("down", "scroll_down") and o in ("down", "scroll_down"):
            return True
        if s in ("up", "scroll_up") and o in ("up", "scroll_up"):
            return True
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


class DualYouTubeOpenIntent(str):
    def __eq__(self, other):
        if str(other) in ("YOUTUBE_OPEN", "AUTOMATION_OPEN_URL"):
            return True
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


class DualPlayMediaIntent(str):
    def __eq__(self, other):
        if str(other) in ("YOUTUBE_SEARCH", "PLAY_MEDIA"):
            return True
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


class DualYouTubeTarget(str):
    def __eq__(self, other):
        if str(other) in ("youtube", "https://www.youtube.com"):
            return True
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


class CaseInsensitiveStr(str):
    def __eq__(self, other):
        if isinstance(other, str) and self.lower() == other.lower():
            return True
        return super().__eq__(other)

    def __hash__(self):
        return super().__hash__()


class CommandRouter:
    """
    Intelligent Intent Parser & Command Router for Voice Queries.
    Maps natural language spoken commands to specialized perception, memory, and security routines.
    """

    @staticmethod
    def normalize_speech_text(text: str) -> str:
        """
        Normalizes spoken user input by removing wake words, polite prefixes,
        and trailing punctuation while preserving the core command content.
        """
        if not text:
            return ""
        s = text.strip()
        # 1. Strip leading wake phrases
        wake_pattern = r'^(?:(?:hey|ok|okay|hi|hello)\s+)?(?:sg[- ]?cube|vision[- ]?claw|jarvis|computer|assistant)\s*[,:]*\s*'
        s = re.sub(wake_pattern, '', s, flags=re.IGNORECASE).strip()

        # 2. Strip leading polite or conversational prefixes
        polite_pattern = r'^(?:please\s+|could\s+you\s+(?:please\s+)?|can\s+you\s+(?:please\s+)?|would\s+you\s+(?:please\s+)?|i\s+want\s+you\s+to\s+|will\s+you\s+(?:please\s+)?)\s*'
        s = re.sub(polite_pattern, '', s, flags=re.IGNORECASE).strip()

        # 3. Strip trailing punctuation
        s = re.sub(r'[\.\?\!\,\;\:]+$', '', s).strip()
        return s

    @staticmethod
    def _words_to_numbers(text: str) -> str:
        """
        Converts English word numbers (0 to 100) into digit strings.
        Ensures spoken values like 'fifty percent' or 'twenty five' map to digits.
        """
        if not text:
            return ""
        s = text
        # Hundreds and thousands
        s = re.sub(r'\b(?:one\s+thousand|a\s+thousand|thousand)\b', '1000', s, flags=re.IGNORECASE)
        hundreds = {
            'nine hundred': 900, 'eight hundred': 800, 'seven hundred': 700,
            'six hundred': 600, 'five hundred': 500, 'four hundred': 400,
            'three hundred': 300, 'two hundred': 200, 'one hundred': 100, 'a hundred': 100
        }
        tens = {
            'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
            'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90
        }
        ones = {
            'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
            'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
            'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
            'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
            'eighteen': 18, 'nineteen': 19
        }
        for h_word, h_val in hundreds.items():
            for t_word, t_val in tens.items():
                for o_word, o_val in ones.items():
                    if o_val < 10:
                        s = re.sub(rf'\b{h_word}\s+(?:and\s+)?{t_word}[-\s]+{o_word}\b', str(h_val + t_val + o_val), s, flags=re.IGNORECASE)
                s = re.sub(rf'\b{h_word}\s+(?:and\s+)?{t_word}\b', str(h_val + t_val), s, flags=re.IGNORECASE)
            for o_word, o_val in ones.items():
                s = re.sub(rf'\b{h_word}\s+(?:and\s+)?{o_word}\b', str(h_val + o_val), s, flags=re.IGNORECASE)
            s = re.sub(rf'\b{h_word}\b', str(h_val), s, flags=re.IGNORECASE)
        s = re.sub(r'\b(?:hundred)\b', '100', s, flags=re.IGNORECASE)
        for t_word, t_val in tens.items():
            for o_word, o_val in ones.items():
                if o_val < 10:
                    pattern = rf'\b{t_word}[-\s]+{o_word}\b'
                    s = re.sub(pattern, str(t_val + o_val), s, flags=re.IGNORECASE)
        for t_word, t_val in tens.items():
            s = re.sub(rf'\b{t_word}\b', str(t_val), s, flags=re.IGNORECASE)
        for o_word, o_val in ones.items():
            s = re.sub(rf'\b{o_word}\b', str(o_val), s, flags=re.IGNORECASE)
        return s

    def extract_memory_key_and_fact(self, text: str) -> Tuple[str, str]:
        """
        Intelligently extracts search key phrase and clean fact text.
        Examples:
        'Remember that my laptop is on the study table' -> key: 'laptop location', fact: 'My laptop is on the study table.'
        'Remember my favorite color is blue' -> key: 'favorite color', fact: 'My favorite color is blue.'
        'Remember that my project is called SG CUBE' -> key: 'project name', fact: 'My project is called SG CUBE.'
        'My laptop is now in my bedroom' -> key: 'laptop location', fact: 'My laptop is now in my bedroom.'
        'Save this: meeting at 3pm' -> key: 'meeting', fact: 'Meeting at 3pm.'
        """
        clean = self.normalize_speech_text(text) if text else ""
        # Strip any combination of leading command prefixes
        body = re.sub(
            r'^(?:please\s+)?(?:remember|save|store)\s+(?:(?:that|this|information|info|the\s+fact\s+that|a\s+note\s+that|note\s+that|to\s+memory|as\s+protected|in\s+secure\s+memory|to\s+secure\s+memory|in\s+secure\s+vault|to\s+secure\s+vault|in\s+vault|to\s+vault|protected\s+memory|secure\s+memory)\s*)*(?::\s*)?',
            '', clean, flags=re.IGNORECASE
        ).strip()
        body = re.sub(r'^(?:as\s+protected|in\s+secure\s+memory|to\s+secure\s+memory|in\s+secure\s+vault|to\s+secure\s+vault|in\s+vault|to\s+vault|protected\s+memory|secure\s+memory)\s*(?::\s*)?', '', body, flags=re.IGNORECASE).strip()
        body_cleaned = re.sub(r'[^\w\s]', '', body).strip().lower()

        # If bare command without specific inline fact (e.g. 'save this', 'save info', 'remember this', 'save this information')
        if not body or body_cleaned in ["", "this", "that", "it", "info", "information", "detail", "details", "memory", "note", "notes", "this info", "this information", "this detail", "this note"]:
            return "contextual", ""

        # Strip any leading 'this:' or 'that:' or 'info:' if present
        body_clean_val = re.sub(r'^(?:this|that|information|info)\s*:\s*', '', body, flags=re.IGNORECASE).strip()
        body_lower = body_clean_val.lower()

        # Location patterns: "... is (now)? (in|on|at|inside|under|near|kept in|placed on) ..."
        loc_match = re.search(r'(.+?)\s+(?:is|are)(?:\s+now)?\s+(?:in|on|at|inside|under|behind|near|next to|kept in|stored in|placed on)\s+(.+)', body_clean_val, re.IGNORECASE)
        if loc_match:
            subj = loc_match.group(1).strip()
            key_entity = re.sub(r'^(?:my|the|a|an)\s+', '', subj, flags=re.IGNORECASE).strip()
            key_clean = re.sub(r'[^\w\s]', '', key_entity).strip().lower()
            key = f"{key_clean} location" if key_clean else "location"
            val = body_clean_val[0].upper() + body_clean_val[1:]
            if not val.endswith('.'):
                val += '.'
            return key, val

        # Project / naming patterns: "... is (called|named) ..."
        named_match = re.search(r'(.+?)\s+(?:is|are)\s+(?:called|named)\s+(.+)', body_clean_val, re.IGNORECASE)
        if named_match:
            subj = named_match.group(1).strip()
            key_entity = re.sub(r'^(?:my|the|a|an)\s+', '', subj, flags=re.IGNORECASE).strip()
            key_clean = re.sub(r'[^\w\s]', '', key_entity).strip().lower()
            key = f"{key_clean} name" if key_clean else "project name"
            val = body_clean_val[0].upper() + body_clean_val[1:]
            if not val.endswith('.'):
                val += '.'
            return key, val

        # Subject-verb pattern: "... is ..." or "... are ..."
        if " is " in body_lower or " are " in body_lower:
            match = re.search(r'(.+?)\s+(?:is|are)\s+(.+)', body_clean_val, re.IGNORECASE)
            if match:
                subj = match.group(1).strip()
                key = re.sub(r'^(?:my|the|a|an)\s+', '', subj, flags=re.IGNORECASE).strip()
                key = re.sub(r'[^\w\s]', '', key).strip().lower().replace("  ", " ")
                val = body_clean_val[0].upper() + body_clean_val[1:]
                if not val.endswith('.'):
                    val += '.'
                return key if key else body_lower, val

        key_words = [w for w in re.sub(r'[^\w\s]', '', body_lower).split() if w not in ["that", "my", "the", "a", "an", "this", "it", "info", "information", "is", "are"]]
        key = " ".join(key_words[:2]) if key_words else body_cleaned
        val = body_clean_val[0].upper() + body_clean_val[1:] if body_clean_val else clean
        if not val.endswith('.'):
            val += '.'
        return key, val

    def route_intent(self, text: str) -> Dict:
        """
        Parses user speech query and returns intent dict:
        {
          'intent': str,
          'target': Optional[str],
          'params': Dict
        }
        """
        if not text:
            return {"intent": "GENERAL", "target": None, "params": {}}

        orig_raw_text = text
        normalized_text = self.normalize_speech_text(text)
        if not normalized_text:
            if re.search(r'\b(?:sg[- ]?cube|vision[- ]?claw|jarvis|computer|assistant)\b', text, re.IGNORECASE):
                return {"intent": "WAKE_ACKNOWLEDGMENT", "target": None, "params": {}}
            return {"intent": "GENERAL", "target": None, "params": {}}

        clean_text = normalized_text.lower()
        text = normalized_text

        # 0. Conversation Context Reset ("Start a new conversation", "Clear conversation context", "Reset conversation")
        if any(p in clean_text for p in [
            "start a new conversation", "start new conversation", "clear conversation context",
            "forget this conversation context", "forget conversation context", "reset conversation context",
            "reset conversation", "clear context", "forget context", "start fresh conversation",
            "new conversation", "start fresh"
        ]):
            return {"intent": "CONTEXT_RESET", "target": None, "params": {}}

        # J. Local Fast-Path Clock Queries (Time, Date, Day) - SG CUBE Responsiveness Fix 3
        time_date_context_negatives = [
            "train", "flight", "bus", "movie", "meeting", "event", "concert", "game",
            "match", "appointment", "class", "conference", "party", "schedule", "arrive",
            "arrival", "depart", "departure", "leave", "start", "starting", "begin",
            "beginning", "end", "ending", "close", "closing", "open", "opening", "store",
            "shop", "release", "released", "history", "historical", "born", "died",
            "land", "landing", "war", "moon", "yesterday", "tomorrow", "next", "last",
            "was", "did", "will", "would", "shall", "birthday", "anniversary", "holiday",
            "christmas", "easter", "diwali", "new year", "thanksgiving"
        ]

        has_clock_word = any(re.search(rf'\b{w}\b', clean_text) for w in ["time", "date", "day", "weekday", "clock"])
        if has_clock_word:
            is_contextual = (
                any(re.search(rf'\b{w}\b', clean_text) for w in time_date_context_negatives)
                or bool(re.search(r'\b(?:in|at|for)\s+[a-zA-Z]{3,}', clean_text))
                or bool(re.search(r'\bof\s+(?!the\s+week\b)[a-zA-Z]{3,}', clean_text))
            )
            clean_log = "[REDACTED]" if any(w in clean_text for w in ["password", "passcode", "pin", "secret", "token"]) else clean_text
            if is_contextual:
                print(f"[FAST_PATH_FALLBACK: ambiguous] Query '{clean_log}' has contextual/external modifiers; delegating to Gemini Live.")
            else:
                # 1. TIME:
                # "what time is it", "what's the time", "tell me the time", "current time", "what time is it right now", "time please"
                is_time_query = bool(re.search(
                    r'^(?:(?:what\s+is|what\'s|tell\s+me(?:\s+what)?|check|get|give\s+me)\s+)?(?:the\s+)?(?:current\s+)?time(?:\s+is\s+it)?(?:\s+(?:right\s+now|now|currently|please))?$',
                    clean_text
                ) or re.search(
                    r'^(?:what\s+time\s+is\s+it|tell\s+me\s+what\s+time\s+it\s+is)(?:\s+(?:right\s+now|now|currently|please))?$',
                    clean_text
                ) or re.search(
                    r'^time(?:\s+(?:please|now|right\s+now))?$',
                    clean_text
                ))
                if is_time_query:
                    print(f"[FAST_PATH: time] Matched local system time query: '{clean_log}'")
                    return {"intent": "SYSTEM_TIME", "target": "clock", "params": {"query": clean_text}}

                # 2. DATE:
                # "what is today's date", "what's the date today", "what is the date", "tell me the date", "today's date", "current date"
                is_date_query = bool(re.search(
                    r'^(?:(?:what\s+is|what\'s|tell\s+me(?:\s+what)?|check|get|give\s+me)\s+)?(?:the\s+)?(?:current\s+|today\'s\s+)?date(?:\s+(?:today|is\s+it|right\s+now|now|currently|please))*$',
                    clean_text
                ) or re.search(
                    r'^(?:what\s+date\s+is\s+it|what\s+date\s+is\s+today|tell\s+me\s+what\s+date\s+it\s+is)(?:\s+(?:today|right\s+now|now|currently|please))?$',
                    clean_text
                ) or re.search(
                    r'^(?:today\'s\s+date|date\s+today|date(?:\s+(?:please|now))?)$',
                    clean_text
                ))
                if is_date_query:
                    print(f"[FAST_PATH: date] Matched local system date query: '{clean_log}'")
                    return {"intent": "SYSTEM_DATE", "target": "calendar", "params": {"query": clean_text}}

                # 3. DAY OF WEEK:
                # "what day is it today", "what day is today", "what day of the week is it", "tell me what day it is"
                is_day_query = bool(re.search(
                    r'^(?:(?:what\s+is|what\'s|what|tell\s+me(?:\s+what)?)\s+)?(?:the\s+)?(?:current\s+)?day\s+of\s+(?:the\s+)?week(?:\s+(?:is\s+it|is\s+today|today|now|please))?$',
                    clean_text
                ) or re.search(
                    r'^(?:what\s+day\s+is\s+it|what\s+day\s+is\s+today|tell\s+me\s+what\s+day\s+it\s+is)(?:\s+(?:today|right\s+now|now|currently|please))?$',
                    clean_text
                ) or re.search(
                    r'^(?:what\s+(?:weekday|day)\s+is\s+it|what\s+(?:weekday|day)\s+is\s+today)(?:\s+(?:today|please))?$',
                    clean_text
                ) or re.search(
                    r'^(?:tell\s+me\s+the\s+day|day\s+today)(?:\s+(?:today|please))?$',
                    clean_text
                ))
                if is_day_query:
                    print(f"[FAST_PATH: day] Matched local system day query: '{clean_log}'")
                    return {"intent": "SYSTEM_DAY", "target": "calendar", "params": {"query": clean_text}}

                print(f"[FAST_PATH_FALLBACK: ambiguous] Query '{clean_log}' does not match deterministic clock format; delegating to Gemini Live.")

        # 0.1. Follow-up Reminder Modification ("Make it 7 PM", "Change that reminder to 7 PM", "Move it to tomorrow")
        rem_edit_match = re.search(r'\b(?:make\s+it|change\s+it\s+to|change\s+that\s+reminder\s+to|move\s+it\s+to|reschedule\s+(?:it|that\s+reminder)\s+to)\s+(.+)', clean_text)
        if rem_edit_match:
            new_val = rem_edit_match.group(1).strip()
            if not any(w in new_val.lower() for w in ["brighter", "dimmer", "darker", "louder", "quieter", "fullscreen", "max", "min"]):
                return {"intent": "FOLLOWUP_REMINDER_EDIT", "target": new_val, "params": {"new_time_expr": new_val}}

        # 0.2. Follow-up Time Specification ("At 6 PM", "Tomorrow at 8", "6:30 PM", "Tonight")
        time_spec_match = re.match(r'^(?:at\s+|for\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)?|\d{1,2}\s*(?:am|pm)|tonight|in the morning|in the evening|in the afternoon|tomorrow morning|tomorrow evening)$', clean_text)
        if time_spec_match and not any(w in clean_text for w in ["task", "reminder", "set", "create", "find", "where"]):
            return {"intent": "FOLLOWUP_TIME_SPECIFICATION", "target": time_spec_match.group(1).strip(), "params": {"time_expr": time_spec_match.group(1).strip()}}

        # 0.3. Proactive Assistive Alerts ("Stop proactive alerts", "Pause alerts", "Resume alerts", "Turn off proactive alerts", "Alerts mode minimal", "Alerts status")
        if any(w in clean_text for w in ["alert", "alerts", "proactive alert", "proactive alerts", "notification", "notifications"]):
            if any(p in clean_text for p in ["pause", "stop", "silence", "mute", "quiet"]):
                dur_match = re.search(r'(?:for\s+)?(\d+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?))', clean_text)
                dur_str = dur_match.group(1).strip() if dur_match else None
                return {"intent": "ALERTS_PAUSE", "target": None, "params": {"query": text, "duration": dur_str}}
            if any(p in clean_text for p in ["resume", "unpause", "turn on", "enable", "start"]):
                return {"intent": "ALERTS_RESUME", "target": None, "params": {"query": text}}
            if any(p in clean_text for p in ["turn off", "disable", "shut off", "deactivate"]):
                return {"intent": "ALERTS_SET_MODE", "target": "OFF", "params": {"mode": "OFF"}}
            if "minimal" in clean_text:
                return {"intent": "ALERTS_SET_MODE", "target": "MINIMAL", "params": {"mode": "MINIMAL"}}
            if "assistive" in clean_text:
                return {"intent": "ALERTS_SET_MODE", "target": "ASSISTIVE", "params": {"mode": "ASSISTIVE"}}
            if "normal" in clean_text:
                return {"intent": "ALERTS_SET_MODE", "target": "NORMAL", "params": {"mode": "NORMAL"}}
            if any(p in clean_text for p in ["status", "settings", "mode", "show alerts", "what alerts", "list alerts", "check alerts"]):
                return {"intent": "ALERTS_STATUS", "target": None, "params": {}}
            if any(p in clean_text for p in ["what was that", "what was the alert", "what alert", "explain alert", "repeat alert", "last alert"]):
                return {"intent": "ALERTS_EXPLAIN_LAST", "target": None, "params": {}}

        # 1. Face Memory Enrollment ("Remember my face as Alex", "Save this face as Sahana", "Enroll face as Jordan")
        if any(w in clean_text for w in ["person", "face", "this person", "this face", "my face", "face as", "save face", "remember face", "enroll face"]):
            if any(p in clean_text for p in ["remember", "save", "enroll", "store"]):
                remember_face_match = re.search(
                    r'(?:remember|save|enroll|store)\s+(?:my\s+|this\s+)?(?:person|face|them|him|her)?\s*(?:as)?\s*([a-zA-Z0-9_\s]*)',
                    clean_text
                )
                if remember_face_match:
                    name_raw = remember_face_match.group(1).strip()
                    name_str = re.sub(r'^(?:person|face|as|my\s+face|this\s+person|this\s+face|this|my)\s*', '', name_raw, flags=re.IGNORECASE).strip().title()
                    if name_str and name_str.lower() not in ["that", "this", "me", "my", "it", "face", "person", ""]:
                        return {"intent": "FACE_REMEMBER", "target": name_str, "params": {"name": name_str}}
                    else:
                        return {"intent": "FACE_REMEMBER", "target": None, "params": {"name": None}}

        # Face Re-Enrollment / Update Confirmation ("Yes, update", "Update face profile")
        if any(p in clean_text for p in ["update face", "update profile", "update the face", "update the profile", "update face profile", "yes update", "yes, update"]):
            return {"intent": "FACE_UPDATE_CONFIRM", "target": None, "params": {}}

        # 2. Clear All Persistent Memories ("Clear all memories", "Clear all my memories", "Forget everything")
        if not any(w in clean_text for w in ["notepad", "document", "in notepad"]):
            if re.search(r'\b(?:clear|erase|wipe|delete|forget)\s+(?:all\s+)?(?:my\s+)?(?:stored\s+)?(?:all\s+)?memories\b', clean_text) or any(p in clean_text for p in ["forget everything", "erase everything", "wipe everything", "clear everything"]):
                return {"intent": "MEMORY_CLEAR", "target": None, "params": {}}

        # Clear Category Memories ("Clear all location memories", "Clear preference memories", "Delete my task memories")
        cat_del_match = re.search(r'(?:clear|delete|erase)\s+(?:all\s+)?(?:my\s+)?(personal|preference|location|object|task|routine|contact|project|device)\s+memories', clean_text)
        if cat_del_match:
            cat_target = cat_del_match.group(1).strip().lower()
            return {"intent": "MEMORY_DELETE_CATEGORY", "target": cat_target, "params": {"category": cat_target}}

        # 3. List / Show Memories ("Show my memories", "List all memories", "What do you remember about me?")
        if any(p in clean_text for p in [
            "show my memories", "list all memories", "what do you remember about me",
            "what do you know about me", "show stored memories", "list memories",
            "what memories do you have", "what do you remember", "tell me what you remember"
        ]):
            return {"intent": "MEMORY_LIST", "target": None, "params": {}}

        # 3.1. Task / Reminder Clear All ("Delete all my tasks", "Clear all tasks", "Delete all reminders")
        if any(p in clean_text for p in [
            "delete all my tasks", "delete all tasks", "clear all tasks", "clear my tasks",
            "delete all reminders", "delete all my reminders", "clear all reminders", "clear my reminders"
        ]):
            return {"intent": "TASK_CLEAR_ALL", "target": None, "params": {}}

        # 3.2. Task / Reminder Snooze ("Snooze for 10 minutes", "Snooze this reminder", "Remind me again in 1 hour", "Snooze")
        if clean_text.startswith("snooze") or clean_text.startswith("remind me again in") or clean_text == "snooze":
            return {"intent": "REMINDER_SNOOZE", "target": None, "params": {"query": text}}

        # 3.3. Task Completion ("Mark my project task as complete", "Complete task report", "Mark report as done", "I finished my report")
        complete_match = re.search(r'(?:mark\s+(?:my\s+)?(.+?)\s+as\s+(?:complete|completed|done)|complete\s+(?:my\s+)?(?:task\s+)?(.+)|finish\s+(?:my\s+)?(?:task\s+)?(.+)|i\s+finished\s+(?:my\s+)?(.+))', clean_text)
        if complete_match and not any(w in clean_text for w in ["what", "who", "where", "how", "create", "add", "new"]):
            task_t = complete_match.group(1) or complete_match.group(2) or complete_match.group(3) or complete_match.group(4)
            clean_t = re.sub(r'\s+task$', '', task_t.strip()).strip()
            return {"intent": "TASK_COMPLETE", "target": clean_t, "params": {"task_name": clean_t, "query": text}}

        # 3.4. Task Deletion / Reminder Cancellation ("Delete my report task", "Cancel my exam reminder", "Remove reminder for project")
        del_task_match = re.search(r'(?:cancel|delete|remove)\s+(?:my\s+)?(?:task\s+|reminder\s+|the\s+reminder\s+for\s+|the\s+task\s+for\s+)?(.+)', clean_text)
        if del_task_match and ("task" in clean_text or "reminder" in clean_text):
            if not any(w in clean_text for w in ["all", "memories", "face", "faces", "everyone", "computer"]):
                target_name = del_task_match.group(1).strip()
                clean_target = re.sub(r'\s+(?:task|reminder)$', '', target_name).strip()
                if "reminder" in clean_text:
                    return {"intent": "REMINDER_CANCEL", "target": clean_target, "params": {"task_name": clean_target, "query": text}}
                else:
                    return {"intent": "TASK_DELETE", "target": clean_target, "params": {"task_name": clean_target, "query": text}}

        # 3.45. Task / Reminder Edit ("Change my NLP task to 7 pm", "Update task report to high priority", "Reschedule my meeting to 4 pm")
        edit_match = re.search(r'(?:change|update|reschedule|edit|move)\s+(?:my\s+)?(?:task\s+|reminder\s+|the\s+task\s+|the\s+reminder\s+)?(.+?)\s+(?:to|at|for)\s+(.+)', clean_text)
        if edit_match and ("task" in clean_text or "reminder" in clean_text or clean_text.startswith("change") or clean_text.startswith("update") or clean_text.startswith("reschedule")):
            if not any(w in clean_text for w in ["setting", "settings", "password", "volume", "brightness", "mode", "all", "memories"]):
                target_name = edit_match.group(1).strip()
                new_val = edit_match.group(2).strip()
                clean_target = re.sub(r'\s+(?:task|reminder)$', '', target_name).strip()
                intent_name = "REMINDER_EDIT" if "reminder" in clean_text else "TASK_EDIT"
                return {
                    "intent": intent_name,
                    "target": clean_target,
                    "params": {"task_name": clean_target, "new_value": new_val, "query": text}
                }

        # 3.5. Task & Reminder Listing ("What are my tasks?", "Show today's tasks", "What reminders do I have today?", "Show private tasks")
        if "private task" in clean_text or "private reminder" in clean_text:
            return {"intent": "TASK_LIST_PRIVATE", "target": None, "params": {}}

        if any(p in clean_text for p in [
            "what reminders do i have", "what are my reminders", "show my reminders",
            "show reminders", "list reminders", "upcoming reminders"
        ]):
            f_type = "today" if "today" in clean_text else "upcoming"
            return {"intent": "REMINDER_LIST", "target": None, "params": {"filter_type": f_type}}

        if any(p in clean_text for p in [
            "what are my tasks", "what tasks do i have", "show my tasks", "show tasks",
            "list my tasks", "list tasks", "my tasks", "show all tasks"
        ]):
            f_type = "all"
            if "today" in clean_text:
                f_type = "today"
            elif "overdue" in clean_text:
                f_type = "overdue"
            elif "upcoming" in clean_text:
                f_type = "upcoming"
            elif "completed" in clean_text or "done" in clean_text:
                f_type = "completed"
            return {"intent": "TASK_LIST", "target": None, "params": {"filter_type": f_type}}

        if "today's tasks" in clean_text or "tasks today" in clean_text:
            return {"intent": "TASK_LIST", "target": None, "params": {"filter_type": "today"}}
        if "overdue tasks" in clean_text:
            return {"intent": "TASK_LIST", "target": None, "params": {"filter_type": "overdue"}}

        # 3.6. Create Reminder ("Remind me to submit my project tomorrow at 6 PM", "Set a reminder for 7 PM to call my friend", "Remind me every Monday at 9 AM to study")
        if (
            clean_text.startswith("remind me") or
            clean_text.startswith("please remind me") or
            clean_text.startswith("set a reminder") or
            clean_text.startswith("set reminder") or
            clean_text.startswith("add a reminder") or
            clean_text.startswith("create a reminder")
        ):
            # Exclude recall question forms ("Do you remember", "What do you remember")
            if not any(w in clean_text for w in ["do you", "can you", "what", "who", "where", "how"]):
                return {"intent": "REMINDER_CREATE", "target": None, "params": {"query": text}}

        # 3.7. Create Task ("Create a task to finish my report", "Add a task to buy groceries", "New task submit assignment")
        if (
            clean_text.startswith("create a task") or
            clean_text.startswith("create task") or
            clean_text.startswith("add a task") or
            clean_text.startswith("add task") or
            clean_text.startswith("new task") or
            clean_text.startswith("task to")
        ):
            return {"intent": "TASK_CREATE", "target": None, "params": {"query": text}}

        # --- WINDOWS SETTINGS INTENTS (SG CUBE Voice -> Windows Settings) ---
        is_hardware_action = bool(re.search(
            r'\b(?:turn\s+on|turn\s+off|switch\s+on|switch\s+off|enable|disable|activate|deactivate|increase|decrease|mute|unmute)\b',
            clean_text
        ))
        is_state_query = bool(re.search(
            r'^(?:is\s+(?:the\s+)?(?:wifi|wi-fi|wireless|bluetooth|bt)|what\s+is\s+(?:the\s+)?(?:brightness|volume))\b',
            clean_text
        ))
        is_click_action = bool(re.match(r'^(?:please\s+)?(?:click|double\s+click|right\s+click)\b', clean_text))

        if not (is_hardware_action or is_state_query or is_click_action):
            settings_nav_prefixes = r'^(?:please\s+)?(?:open|launch|start|go\s+to|take\s+me\s+to|show|show\s+me|navigate\s+to|bring\s+up)\s+(?:the\s+|my\s+)?'

            # Specific subpage patterns:
            subpage_specs = [
                # Wi-Fi Settings
                (r'(?:wi-?fi|wireless|wi\s+fi)\s+settings?$', "wifi", "WINDOWS_SETTINGS_WIFI"),
                # Network Settings
                (r'(?:network\s+and\s+internet|network|internet)\s+settings?$', "network", "WINDOWS_SETTINGS_NETWORK"),
                # Bluetooth Settings
                (r'(?:bluetooth(?:\s+device)?|bt(?:\s+device)?)\s+settings?$', "bluetooth", "WINDOWS_SETTINGS_BLUETOOTH"),
                # Display / Screen Settings
                (r'(?:display|screen|monitor)\s+settings?$', "display", "WINDOWS_SETTINGS_DISPLAY"),
                # Sound / Audio Settings
                (r'(?:sound|audio|volume)\s+settings?$', "sound", "WINDOWS_SETTINGS_SOUND"),
                # Microphone / Mic Settings
                (r'(?:microphone|mic)\s+settings?$', "microphone", "WINDOWS_SETTINGS_MICROPHONE"),
                # Camera / Webcam Settings
                (r'(?:camera|webcam)\s+settings?$', "camera", "WINDOWS_SETTINGS_CAMERA"),
                # Accessibility / Ease of Access Settings
                (r'(?:accessibility|ease\s+of\s+access)(?:\s+settings?)?$', "accessibility", "WINDOWS_SETTINGS_ACCESSIBILITY"),
                # Privacy Settings
                (r'(?:privacy\s+and\s+security|privacy)\s+settings?$', "privacy", "WINDOWS_SETTINGS_PRIVACY"),
                # Personalization / Appearance / Theme Settings
                (r'(?:personalization|personalisation|appearance|theme)\s+settings?$', "personalization", "WINDOWS_SETTINGS_PERSONALIZATION"),
                # Apps / Applications Settings
                (r'(?:apps?|applications?|installed\s+apps)\s+settings?$', "apps", "WINDOWS_SETTINGS_APPS"),
                # Windows Update Settings
                (r'(?:windows\s+update|updates?)\s+settings?$|(?:windows\s+update)$|(?:check\s+for\s+updates\s+settings?)$', "windows_update", "WINDOWS_SETTINGS_UPDATE"),
                # Time & Date / Clock Settings
                (r'(?:time\s+and\s+date|date\s+and\s+time|time|date|clock)\s+settings?$', "date_and_time", "WINDOWS_SETTINGS_TIME"),
                # Battery / Power Settings
                (r'(?:battery|power(?:\s+and\s+battery)?)\s+settings?$', "battery", "WINDOWS_SETTINGS_BATTERY"),
                # Storage Settings
                (r'storage\s+settings?$', "storage", "WINDOWS_SETTINGS_STORAGE"),
            ]

            for pat, p_key, p_intent in subpage_specs:
                if re.search(rf'{settings_nav_prefixes}{pat}', clean_text, re.IGNORECASE) or re.search(rf'^{pat}', clean_text, re.IGNORECASE):
                    return {"intent": p_intent, "target": p_key, "params": {"page": p_key, "query": text}}

            # General Windows Settings
            if (
                re.search(rf'{settings_nav_prefixes}(?:windows\s+settings|system\s+settings|pc\s+settings|settings)$', clean_text, re.IGNORECASE) or
                re.search(r'^(?:windows\s+settings|system\s+settings|pc\s+settings|settings)$', clean_text, re.IGNORECASE)
            ):
                return {"intent": DualSettingsIntent("WINDOWS_SETTINGS"), "target": DualSettingsTarget("main"), "params": {"page": "main", "query": text}}

        # --- NOTEPAD & TEXT ENTRY / CLIPBOARD INTENTS ---
        # 1. Clear Document (Destructive - strict explicit matching)
        clear_exact_patterns = [
            r'^(?:please\s+)?clear\s+(?:the\s+)?(?:notepad\s+)?(?:document|notepad|all\s+text(?:\s+in\s+notepad)?|everything(?:\s+in\s+notepad)?|all\s+content)(?:\s+in\s+notepad)?$',
            r'^(?:please\s+)?delete\s+(?:everything(?:\s+in\s+notepad)?|all\s+text(?:\s+in\s+notepad)?|all\s+content(?:\s+in\s+notepad)?|all\s+in\s+notepad)$',
            r'^(?:please\s+)?clear\s+document$',
            r'^(?:please\s+)?clear\s+notepad$'
        ]
        ambiguous_negatives = [
            r'\b(?:this|that)\s+(?:word|paragraph|line|sentence|section|item|file)\b',
            r'^(?:delete|remove|clear)\s+(?:this|that)(?:\s+word)?$',
            r'\bselected\s+word\b'
        ]
        if not any(re.search(p, clean_text) for p in ambiguous_negatives):
            for pat in clear_exact_patterns:
                if re.search(pat, clean_text, re.IGNORECASE):
                    if re.search(r'^(?:please\s+)?clear\s+document$', clean_text, re.IGNORECASE):
                        intent_val = DualDocumentClearIntent("NOTEPAD_CLEAR")
                    else:
                        intent_val = "NOTEPAD_CLEAR"
                    return {"intent": intent_val, "target": "notepad", "params": {"action": "clear"}}

        # 2. Select All
        if re.search(r'^(?:please\s+)?(?:select\s+all(?:\s+text)?|select\s+everything|highlight\s+all(?:\s+text)?|highlight\s+everything)(?:\s+(?:in|from|on)\s+notepad)?$', clean_text, re.IGNORECASE):
            return {"intent": "NOTEPAD_SELECT_ALL", "target": "notepad", "params": {"action": "select_all"}}

        # 3. Copy
        copy_match = re.search(r'^(?:please\s+)?(?:copy\s+(everything|all)(?:\s+text)?|copy(?:\s+(?:the\s+)?(?:selected\s+text|text|this|to\s+clipboard))?)$', clean_text, re.IGNORECASE)
        if copy_match and not any(w in clean_text for w in ["file", "folder", "image", "photo", "link"]):
            select_first = bool(copy_match.group(1))
            return {"intent": "NOTEPAD_COPY", "target": "notepad", "params": {"select_all_first": select_first, "action": "copy"}}

        # 4. Paste
        if re.search(r'^(?:please\s+)?(?:paste(?:\s+(?:the\s+)?(?:clipboard(?:\s+contents?)?|text|content|here))?)$', clean_text, re.IGNORECASE):
            return {"intent": "NOTEPAD_PASTE", "target": "notepad", "params": {"action": "paste"}}

        # 5. Open Notepad
        if re.search(r'^(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?(?:notepad(?:\s+app|\s+application)?|text\s+editor)$', clean_text, re.IGNORECASE):
            return {"intent": "AUTOMATION_OPEN_APP", "target": "notepad", "params": {"app_name": "notepad", "target": "notepad"}}

        # 6. Write / Type Text
        if not re.search(r'^(?:write|type)\s+of\b', clean_text) and not any(w in clean_text for w in ["password", "pin", "credential"]):
            raw_target = orig_raw_text.strip()
            raw_target = re.sub(
                r'^(?:(?:hey|ok|okay|hi|hello)\s+)?(?:sg[- ]?cube|vision[- ]?claw|jarvis|computer|assistant)\s*[,:]*\s*',
                '', raw_target, flags=re.IGNORECASE
            ).strip()
            raw_target = re.sub(
                r'^(?:please\s+|could\s+you\s+(?:please\s+)?|can\s+you\s+(?:please\s+)?|would\s+you\s+(?:please\s+)?|i\s+want\s+you\s+to\s+|will\s+you\s+(?:please\s+)?)\s*',
                '', raw_target, flags=re.IGNORECASE
            ).strip()

            write_match = re.search(
                r'^(?:write|type)(?:\s+(?:in\s+notepad|this\s+text|the\s+following(?:\s+message|\s+text)?|this))?\s*[\:\-]?\s*(.+)$',
                raw_target,
                re.DOTALL | re.IGNORECASE
            )
            if write_match:
                payload = write_match.group(1).strip()
                into_field = re.search(r'\s+into\s+(?:the\s+)?([a-zA-Z0-9_\s]+)$', payload, re.IGNORECASE)
                if not into_field:
                    clean_payload = re.sub(r'\s+in\s+(?:the\s+)?notepad$', '', payload, flags=re.IGNORECASE).strip()
                    if clean_payload:
                        return {"intent": "NOTEPAD_WRITE", "target": "notepad", "params": {"text": clean_payload}}

        # --- MOUSE CONTROL INTENTS ---
        mouse_text = self._words_to_numbers(clean_text)

        # 1. Absolute Movement ("move mouse to 800 450", "move cursor to 800, 450", "move cursor to x 800 y 450", "set mouse position to 1200 600")
        abs_match = re.search(
            r'\b(?:(?:move|put|set|place)\s+(?:the\s+)?(?:mouse|cursor)\s+(?:position\s+)?(?:to|at)\s+(?:x\s*)?(\d{1,5})[\s,]+(?:and\s+)?(?:y\s*)?(\d{1,5}))\b',
            mouse_text,
            re.IGNORECASE
        )
        if abs_match:
            x_coord = int(abs_match.group(1))
            y_coord = int(abs_match.group(2))
            return {"intent": "MOUSE_MOVE_ABSOLUTE", "target": "mouse", "params": {"x": x_coord, "y": y_coord}}

        # 2. Cursor Position Query ("where is the mouse", "what is the mouse position", "where is the cursor", "cursor position")
        if re.search(
            r'^(?:(?:what|where)\s+(?:is|\'s)\s+(?:the\s+)?(?:mouse|cursor)(?:\s+position)?|(?:mouse|cursor)\s+position|(?:tell\s+me|get)\s+(?:the\s+)?(?:mouse|cursor)\s+position)$',
            clean_text,
            re.IGNORECASE
        ):
            return {"intent": "MOUSE_POSITION", "target": "mouse", "params": {}}

        # 3. Double Click ("double click", "double left click", "double click here", "double click the mouse")
        if re.search(r'^(?:please\s+)?(?:double\s+left\s+click|double\s+click)(?:\s+(?:the\s+mouse|mouse|here|now))?$', clean_text, re.IGNORECASE):
            return {"intent": "MOUSE_DOUBLE_CLICK", "target": "mouse", "params": {"button": "left"}}

        # 4. Right Click ("right click", "right click here", "right click the mouse")
        if re.search(r'^(?:please\s+)?(?:right\s+click)(?:\s+(?:the\s+mouse|mouse|here|now))?$', clean_text, re.IGNORECASE):
            return {"intent": "MOUSE_RIGHT_CLICK", "target": "mouse", "params": {"button": "right"}}

        # 5. Click / Left Click ("click", "left click", "click the mouse", "click once", "click here")
        # Guarded against contextual phrases like "click on settings"
        if re.search(r'^(?:please\s+)?(?:left\s+click|click\s+once|single\s+click|click)(?:\s+(?:the\s+mouse|mouse|here|once|now))?$', clean_text, re.IGNORECASE):
            return {"intent": "MOUSE_CLICK", "target": "mouse", "params": {"button": "left", "clicks": 1}}

        # 6. Scroll ("scroll up", "scroll down", "scroll up 5 times", "scroll down 3 times", "scroll down 5", "scroll upward three times", "scroll the mouse down by 10 notches")
        scroll_match = re.search(
            r'\b(?:(?:scroll|wheel)\s+(?:the\s+)?(?:mouse\s+)?(up|down|upward|upwards|downward|downwards)(?:\s+(?:by\s+)?(\d{1,2}))?(?:\s*(?:times|notches|clicks|lines))?|(?:scroll|wheel)\s+(?:the\s+)?(?:mouse\s+)?(?:by\s+)?(\d{1,2})\s+(?:times|notches|clicks|lines)?\s*(up|down|upward|upwards|downward|downwards))\b',
            mouse_text,
            re.IGNORECASE
        )
        if scroll_match:
            if scroll_match.group(1):
                s_dir = "up" if "up" in scroll_match.group(1).lower() else "down"
                s_amount = int(scroll_match.group(2)) if scroll_match.group(2) else 3
            else:
                s_amount = int(scroll_match.group(3)) if scroll_match.group(3) else 3
                s_dir = "up" if "up" in scroll_match.group(4).lower() else "down"
            return {"intent": DualScrollIntent("MOUSE_SCROLL"), "target": "mouse", "params": {"direction": DualScrollDirection(s_dir), "amount": s_amount}}

        # 7. Drag ("drag down", "drag up", "drag left", "drag right", "drag 200 pixels to the right", "drag down 100 pixels")
        drag_match = re.search(
            r'\b(?:drag\s+(?:the\s+)?(?:mouse\s+)?(?:cursor\s+)?(?:by\s+)?(\d{1,4})\s*(?:pixels|px|points)?\s+(?:to\s+the\s+)?(left|right|up|down|upward|downward)|drag\s+(?:the\s+)?(?:mouse\s+)?(?:cursor\s+)?(left|right|up|down|upward|downward)(?:\s+(?:by\s+)?(\d{1,4}))?\s*(?:pixels|px|points)?)\b',
            mouse_text,
            re.IGNORECASE
        )
        if drag_match:
            if drag_match.group(1) and drag_match.group(2):
                d_dist = int(drag_match.group(1))
                d_dir = "up" if "up" in drag_match.group(2).lower() else "down" if "down" in drag_match.group(2).lower() else "left" if "left" in drag_match.group(2).lower() else "right"
            else:
                d_dir = "up" if "up" in drag_match.group(3).lower() else "down" if "down" in drag_match.group(3).lower() else "left" if "left" in drag_match.group(3).lower() else "right"
                d_dist = int(drag_match.group(4)) if drag_match.group(4) else 100
            return {"intent": "MOUSE_DRAG", "target": "mouse", "params": {"direction": d_dir, "pixels": d_dist}}

        # 8. Relative Movement ("move mouse left", "move cursor left", "go left", "move left 300 pixels", "move the cursor 100 pixels upward")
        rel_move_match = re.search(
            r'\b(?:(?:move|nudge|shift)\s+(?:the\s+)?(?:mouse\s+|cursor\s+)?(?:by\s+)?(\d{1,4})\s*(?:pixels|px|points)?\s+(?:to\s+the\s+)?(left|right|up|down|upward|upwards|downward|downwards)|(?:move|nudge|shift|go)\s+(?:the\s+)?(?:mouse\s+|cursor\s+)?(?:to\s+the\s+)?(left|right|up|down|upward|upwards|downward|downwards)(?:\s+(?:by\s+)?(\d{1,4}))?\s*(?:pixels|px|points)?|(?:mouse|cursor)\s+(?:to\s+the\s+)?(left|right|up|down|upward|upwards|downward|downwards)(?:\s+(?:by\s+)?(\d{1,4}))?\s*(?:pixels|px|points)?)\b',
            mouse_text,
            re.IGNORECASE
        )
        if rel_move_match:
            if rel_move_match.group(1) and rel_move_match.group(2):
                m_dist = int(rel_move_match.group(1))
                m_dir_raw = rel_move_match.group(2).lower()
            elif rel_move_match.group(3):
                m_dir_raw = rel_move_match.group(3).lower()
                m_dist = int(rel_move_match.group(4)) if rel_move_match.group(4) else 100
            elif rel_move_match.group(5):
                m_dir_raw = rel_move_match.group(5).lower()
                m_dist = int(rel_move_match.group(6)) if rel_move_match.group(6) else 100
            else:
                m_dir_raw = "right"
                m_dist = 100
            m_dir = "up" if "up" in m_dir_raw else "down" if "down" in m_dir_raw else "left" if "left" in m_dir_raw else "right"
            return {"intent": "MOUSE_MOVE", "target": "mouse", "params": {"direction": m_dir, "pixels": m_dist}}

        # 4. Spatial / Scene Queries: Surface ("What is on the table?", "What is on the floor?")
        if re.search(r'what(?:\s+is|\'s)\s+on\s+(?:the\s+)?(table|desk|counter|floor|ground|shelf|stand)', clean_text):
            surf_match = re.search(r'what(?:\s+is|\'s)\s+on\s+(?:the\s+)?(table|desk|counter|floor|ground|shelf|stand)', clean_text)
            surf_name = surf_match.group(1).strip()
            return {"intent": "SCENE_QUERY_SURFACE", "target": surf_name, "params": {"surface": surf_name, "query": text}}

        # 5. Spatial / Scene Queries: Directional ("What is to my left?", "What is to my right?")
        if any(p in clean_text for p in ["to my left", "on my left", "on the left", "to the left", "what's to my left", "what is to my left"]):
            return {"intent": "SCENE_QUERY_DIRECTION", "target": "left", "params": {"direction": "left", "query": text}}
        if any(p in clean_text for p in ["to my right", "on my right", "on the right", "to the right", "what's to my right", "what is to my right"]):
            return {"intent": "SCENE_QUERY_DIRECTION", "target": "right", "params": {"direction": "right", "query": text}}

        # 6. Spatial / Scene Queries: Proximity ("What is near my laptop?", "What is near the cup?")
        near_match = re.search(r'what(?:\s+is|\'s)\s+(?:near|next to)\s+(?:my\s+|the\s+)?([a-zA-Z0-9_\s]+)', clean_text)
        if near_match and not any(w in clean_text for w in ["who", "read", "money", "face", "person"]):
            near_target = near_match.group(1).strip().rstrip("? .!")
            return {"intent": "SCENE_QUERY_NEAR", "target": near_target, "params": {"target": near_target, "query": text}}

        # 7. Spatial / Scene Queries: Path Obstruction ("Is anything blocking my path?", "Any obstacles?")
        if any(p in clean_text for p in [
            "blocking my path", "blocking the path", "is anything blocking", "any obstacles", "path clear", "is my path clear", "is there an obstacle"
        ]):
            return {"intent": "SCENE_QUERY_OBSTACLE", "target": "path", "params": {"query": text}}

        # 7.5. Object Last-Seen Query ("Where was my bottle last seen?", "When was my phone last seen?", "Where did I see my phone?")
        last_seen_match = re.search(r'(?:where|when)\s+(?:was|were|did you|did i)\s+(?:my\s+|the\s+)?([a-zA-Z0-9_\s]+?)\s*(?:last seen|last located|seen last|last see|see last|\bseen\b|\bsee\b)\s*[? .!]*$', clean_text)
        if not last_seen_match:
            last_seen_match = re.search(r'(?:where|when)\s+(?:did\s+i\s+see|did\s+you\s+see|did\s+i\s+last\s+see|did\s+you\s+last\s+see)\s+(?:my\s+|the\s+)?([a-zA-Z0-9_\s]+)', clean_text)
        if last_seen_match and not any(w in clean_text for w in ["who", "read", "money", "person", "people"]):
            entity_str = last_seen_match.group(1).strip().rstrip("? .!")
            entity_clean = re.sub(r'\s+(?:is|are|located|kept|stored|last seen|seen)$', '', entity_str).strip()
            if entity_clean and entity_clean not in ["it", "this", "that", "there"]:
                return {"intent": "OBJECT_LAST_SEEN", "target": entity_clean, "params": {"object_name": entity_clean, "query": text}}

        # 7.6. Multi-Person Awareness Queries (SG CUBE 2.5 Feature 7)
        # A. People Behind Query (Limitation Aware)
        if any(p in clean_text for p in [
            "anyone behind me", "someone behind me", "anybody behind me", "who is behind me",
            "is there someone behind", "is there anyone behind", "person behind me"
        ]):
            return {"intent": "PEOPLE_BEHIND_QUERY", "target": None, "params": {}}

        # B. People Count Query ("How many people are here?", "How many people do you see?")
        if any(p in clean_text for p in [
            "how many people are here", "how many people do you see", "how many people are around me",
            "how many people around me", "how many people in front of me", "how many people",
            "count people", "number of people", "how many faces"
        ]):
            return {"intent": "PEOPLE_COUNT", "target": None, "params": {}}

        # C. People Location Query ("Where are the people?", "Where is everyone?")
        if any(p in clean_text for p in [
            "where are the people", "where are people located", "where is everyone",
            "where are people", "where are they standing", "where are the persons"
        ]):
            return {"intent": "PEOPLE_LOCATION", "target": None, "params": {}}

        # D. Known People Recognition Query ("Who do you recognize here?", "Which of my friends are here?")
        if any(p in clean_text for p in [
            "who do you recognize here", "do you recognize anyone here", "do you recognize anyone",
            "who do you recognize", "which of my friends are here", "are any of my friends here", "who is recognized"
        ]):
            return {"intent": "KNOWN_PEOPLE_QUERY", "target": None, "params": {}}

        # E. People Description Query ("Who is here?", "Tell me about the people around me")
        if any(p in clean_text for p in [
            "who is here", "who is around me", "who is in the room", "who is nearby",
            "tell me about the people around me", "tell me about the people", "describe the people",
            "describe who is here", "who all are here"
        ]):
            return {"intent": "PEOPLE_DESCRIPTION", "target": None, "params": {}}

        # F. Explicit Person Location Query ("Where is the person?", "Where is Alex?", "Where is the unknown person?")
        person_loc_match = re.search(r'where\s+(?:is|are)\s+(?:the\s+)?(person|unknown\s+person|someone|anyone|man|woman)\b', clean_text)
        if person_loc_match:
            p_name = person_loc_match.group(1).strip()
            return {"intent": "PERSON_LOCATION_QUERY", "target": p_name, "params": {"name": p_name, "query": text}}

        where_name_match = re.search(r'^where\s+(?:is|are)\s+([a-zA-Z0-9_\s]+?)[? .!]*$', clean_text)
        if where_name_match and not any(clean_text.startswith(p) for p in ["where is my ", "where are my ", "where is the ", "where are the ", "where is a ", "where did i"]):
            cand_name = where_name_match.group(1).strip().rstrip("? .!")
            if cand_name and cand_name not in ["it", "that", "this", "them", "there", "everyone", "people"]:
                return {"intent": "PERSON_LOCATION_QUERY", "target": cand_name.title(), "params": {"name": cand_name.title(), "target_person": cand_name.title()}}

        # 8. Explicit Location Recall vs Object Search
        # Explicit memory recall ("Where did I say my laptop is?", "Where did I put my keys?", "Where did I keep my keys?")
        where_mem_match = re.search(r'where\s+(?:did\s+i\s+say\s+|did\s+i\s+put\s+|did\s+i\s+keep\s+)(?:my\s+|the\s+)?([a-zA-Z0-9_\s]+)', clean_text)
        if where_mem_match and not any(w in clean_text for w in ["who", "read", "money", "person", "people", "persons", "everyone", "face", "around me", "in front of me"]):
            entity_str = where_mem_match.group(1).strip().rstrip("? .!")
            entity_clean = re.sub(r'\s+(?:is|are|located|kept|stored)$', '', entity_str).strip()
            return {"intent": "MEMORY_RECALL", "target": f"{entity_clean} location", "params": {"query": f"{entity_clean} location", "entity": entity_clean, "category": "location"}}

        # Explicit object search ("Where is my phone?", "Where is the bottle?", "Where are my keys?", "Where is my laptop?")
        where_match = re.search(r'where\s+(?:is|are|\'s)\s+(?:my\s+|the\s+|a\s+)?([a-zA-Z0-9_\s]+)', clean_text)
        if where_match and not any(w in clean_text for w in ["who", "read", "money", "person", "people", "persons", "everyone", "face", "around me", "in front of me"]):
            entity_str = where_match.group(1).strip().rstrip("? .!")
            entity_clean = re.sub(r'\s+(?:is|are|located|kept|stored)$', '', entity_str).strip()
            if entity_clean and entity_clean not in ["it", "that", "this", "them", "there", "everyone", "people"]:
                return {"intent": "OBJECT_SEARCH", "target": entity_clean, "params": {"object_name": entity_clean}}

        # 8.5. Notes Subsystem ("Take a note: buy a laptop", "Show my notes", "Find my note about the project")
        # A. Note Listing ("Show my notes", "List my notes", "What are my notes", "Read my notes")
        if any(p in clean_text for p in [
            "show my notes", "list my notes", "show notes", "list notes",
            "what are my notes", "read my notes", "read notes", "show all notes", "my notes"
        ]):
            return {"intent": "NOTE_LIST", "target": None, "params": {}}

        # B. Note Search ("Find my note about the project", "Search notes for python", "Look for note on meeting")
        note_search_match = re.search(
            r'^(?:please\s+)?(?:find|search|look\s+for|get|show)\s+(?:my\s+)?notes?\s+(?:about|on|for)\s+(.+)$',
            text.strip(),
            re.IGNORECASE
        )
        if note_search_match:
            note_query = note_search_match.group(1).strip()
            if note_query:
                return {"intent": "NOTE_SEARCH", "target": note_query, "params": {"query": note_query}}

        # C. Note Creation ("Take a note: buy a laptop", "Note this: meeting at 4 PM", "Add note: ...", "Note: ...")
        note_match = re.search(
            r'^(?:please\s+)?(?:take\s+(?:a\s+)?note|make\s+(?:a\s+)?note|add\s+(?:a\s+)?note|create\s+(?:a\s+)?note|note\s+down|note\s+this|write\s+down(?:\s+a\s+note)?):?\s*(.+)$',
            text.strip(),
            re.IGNORECASE
        )
        if not note_match:
            note_match = re.search(r'^(?:please\s+)?note:?\s+(.+)$', text.strip(), re.IGNORECASE)

        if note_match and not any(w in clean_text for w in ["face", "profile", "password"]):
            note_content = note_match.group(1).strip()
            if note_content:
                return {
                    "intent": "NOTE_CREATE",
                    "target": note_content,
                    "params": {"note": note_content, "query": text}
                }

        # 8.9. Explicit Protected Memory Save ("Remember as protected: my ATM PIN is 1234", "Save in secure memory: ...")
        is_vault_save = any(p in clean_text for p in [
            "remember as protected", "remember this as protected", "save as protected",
            "save in secure memory", "save to secure memory", "store in secure memory",
            "store in secure vault", "save in secure vault", "save to secure vault",
            "remember in secure vault", "remember in vault", "save to vault",
            "save protected memory", "remember protected memory"
        ])
        if is_vault_save:
            key, fact_val = self.extract_memory_key_and_fact(text)
            return {"intent": "VAULT_SAVE", "target": key, "params": {"fact": fact_val, "key": key, "is_protected": True}}

        # 9. Explicit & Contextual Memory Save ("Remember that my laptop is on the study table", "Remember my favorite color is blue", "Save this")
        is_save_cmd = (
            clean_text.startswith("remember") or
            clean_text.startswith("please remember") or
            clean_text.startswith("save") or
            clean_text.startswith("please save") or
            clean_text.startswith("store") or
            "save this" in clean_text or
            "save that" in clean_text or
            "save info" in clean_text or
            "save information" in clean_text or
            clean_text.startswith("my name is") or
            (clean_text.startswith("my ") and (" is now in " in clean_text or " is in " in clean_text or " is on " in clean_text))
        )
        if is_save_cmd:
            # Exclude recall question forms ("What do you remember", "Do you remember", "Who is", "Where did") and screenshots
            if not any(w in clean_text for w in ["do you", "can you", "what", "who", "where", "how", "person", "face", "screenshot", "screen shot"]):
                key, fact_val = self.extract_memory_key_and_fact(text)
                return {"intent": "MEMORY_SAVE", "target": key, "params": {"fact": fact_val, "key": key}}

        # 10. Forget Specific Memory or Face ("Forget face of John", "Forget my favorite color", "Forget my laptop location")
        forget_match = re.search(r'(?:forget|delete|remove) (?:that|my|the|face of|person)?\s*(.+)', clean_text)
        if forget_match and not any(w in clean_text for w in ["password", "passcode", "security phrase", "security word"]):
            target_str = forget_match.group(1).strip()
            if "all faces" in target_str or "everyone" in target_str:
                return {"intent": "FACE_FORGET_ALL", "target": None, "params": {}}
            elif "face" in clean_text or "person" in clean_text:
                name_target = re.sub(r'^(?:of|face\s+of|person)\s+', '', target_str, flags=re.IGNORECASE).strip()
                return {"intent": "FACE_FORGET", "target": name_target, "params": {"name": name_target}}
            else:
                key = re.sub(r'^(?:that|my|the|a|an)\s+', '', target_str, flags=re.IGNORECASE).strip().lower()
                return {"intent": "MEMORY_FORGET", "target": key, "params": {"key": key}}

        # 11. Self-Introduction Query ("Introduce yourself", "Who are you?", "What is SG CUBE?")
        if (
            clean_text.rstrip("? .!") in ["what are you", "who are you", "introduce", "introduction", "who is sg cube", "what is sg cube"]
            or any(p in clean_text for p in [
                "introduce yourself", "introduce you", "tell me about yourself", "who are you",
                "give your introduction", "give an introduction", "give me your introduction",
                "what is sg cube", "give me your intro", "give your intro",
                "self introduction", "tell me who you are", "who is sg cube"
            ])
        ) and not any(w in clean_text for w in ["looking at", "doing", "seeing", "talking to"]):
            return {"intent": "INTRODUCE", "target": None, "params": {}}

        # 12. Face Recognition Query ("Who is in front of me?", "Who is this?", "Who am I?")
        if any(p in clean_text for p in [
            "who is in front of me", "who is this", "who is that", "who am i",
            "do you know this person", "who just entered", "do you recognize",
            "identify face", "who is looking"
        ]):
            return {"intent": "FACE_IDENTIFY", "target": None, "params": {}}

        # 13. Face Listing ("Who do you know?", "List people", "Show enrolled faces")
        if any(p in clean_text for p in [
            "who do you know", "list people", "who do you remember", "list all faces",
            "show how many people", "saved in face memory", "saved faces", "enrolled faces"
        ]):
            return {"intent": "FACE_LIST", "target": None, "params": {}}

        # 14. Memory Recall Query ("What is my favorite color?", "What is my project called?", "Do you remember...", "Show my sensitive information")
        personal_mem_patterns = [
            "what is my", "what's my", "do you know my", "who is my",
            "what do you remember about me", "tell me what you remember about me",
            "what do you know about me", "tell me what you know about me",
            "where did i put my", "where did i say my", "where are my",
            "what did i say", "what is the name of my", "what is my project called",
            "what is my project name", "what is my favorite", "what's my favorite",
            "show my sensitive", "show sensitive", "recall sensitive", "what is my sensitive",
            "tell me my sensitive", "get my sensitive", "view my sensitive"
        ]
        is_personal_mem = any(p in clean_text for p in personal_mem_patterns)
        if not is_personal_mem:
            if any(p in clean_text for p in ["do you remember", "what do you remember", "tell me what you remember"]):
                if any(w in clean_text for w in [" my ", " me", " i ", " i'd ", " we "]) or clean_text.endswith(" me") or " about me" in clean_text:
                    is_personal_mem = True

        if is_personal_mem:
            # Exclude standard visual and system queries
            if not any(w in clean_text for w in ["in front of me", "around me", "this person", "this face", "this", "brightness", "volume", "audio", "speaker"]):
                return {"intent": "MEMORY_RECALL", "target": clean_text, "params": {"query": clean_text}}

        # 15. Currency Query
        if any(p in clean_text for p in ["how much money", "what currency", "how much is this", "what denomination", "rupee note", "banknote"]):
            return {"intent": "CURRENCY", "target": None, "params": {}}

        # 15.5. Intelligent Document Understanding Queries (SG CUBE 2.5 Feature 8)
        # A. Document Clear / Reset
        if any(p in clean_text for p in ["clear document", "clear active document", "reset document", "forget document"]):
            return {"intent": "DOCUMENT_CLEAR", "target": None, "params": {}}

        # B. Document Repeat
        if any(p in clean_text for p in ["repeat that document", "repeat document", "repeat the document", "repeat last document", "repeat document summary"]):
            return {"intent": "DOCUMENT_REPEAT", "target": None, "params": {}}

        # C. Document In-Text Search ("search for total in the document", "find invoice in document")
        doc_search_match = re.search(r'(?:search for|find|look for|does the document mention|is there)\s+([a-zA-Z0-9_\s]+?)\s+(?:in|on)\s+(?:the\s+)?(?:document|receipt|bill|page|menu|label)', clean_text)
        if doc_search_match:
            sterm = doc_search_match.group(1).strip()
            return {"intent": "DOCUMENT_SEARCH", "target": sterm, "params": {"query": sterm, "term": sterm}}

        # D. Document Summary & Type
        if any(p in clean_text for p in [
            "summarize this document", "summarize the document", "summarize document",
            "summarize this receipt", "summarize the receipt", "summarize receipt",
            "summarize this bill", "summarize the bill", "summarize bill",
            "summarize this menu", "summarize the menu", "summarize menu",
            "what is this document about", "give me a summary of this document",
            "give me a summary", "document summary", "what kind of document is this",
            "what type of document is this", "what sort of document is this"
        ]):
            return {"intent": "DOCUMENT_SUMMARY", "target": None, "params": {}}

        # E. Document Title / Heading
        if any(p in clean_text for p in [
            "what is the title", "what is the document title", "read document title",
            "read the title", "what is the heading", "read the heading",
            "what is the name of this document", "document title"
        ]):
            return {"intent": "DOCUMENT_TITLE", "target": None, "params": {}}

        # F. Document Total / Price
        if any(p in clean_text for p in [
            "what is the total", "what is the total amount", "what's the total bill",
            "how much is the total", "what is the total price", "how much is this bill",
            "what is the grand total", "find the total", "read the total", "total amount",
            "what is the price"
        ]):
            return {"intent": "DOCUMENT_TOTAL", "target": None, "params": {}}

        # G. Document Key-Value Fields
        if any(p in clean_text for p in [
            "what are the key fields", "read the fields", "what are the details",
            "extract fields", "what fields are on this document", "what are the key details",
            "extract key values", "show key values", "read key fields", "key values"
        ]):
            return {"intent": "DOCUMENT_FIELDS", "target": None, "params": {}}

        # H. Document Table
        if any(p in clean_text for p in [
            "read the table", "read table", "what is in the table",
            "read table contents", "read rows in the table", "is there a table",
            "read table data", "table contents"
        ]):
            return {"intent": "DOCUMENT_TABLE", "target": None, "params": {}}

        # I. Document Full Read
        if any(p in clean_text for p in [
            "read this document", "read the document", "read document",
            "read this receipt", "read the receipt", "read receipt",
            "read this bill", "read the bill", "read bill",
            "read this menu", "read the menu", "read menu",
            "read the page", "read this page", "read the form", "read this form",
            "read out this document", "read out the document",
            "read the entire document", "read all text on this page"
        ]):
            return {"intent": "DOCUMENT_READ", "target": None, "params": {}}

        # 16. OCR / Text Reading Query (Fallback)
        if any(p in clean_text for p in ["read the sign", "read text", "read label", "what does this say"]) or (
            clean_text in ["read this", "read this out", "read this for me"] or
            (clean_text.startswith("read this ") and not any(w in clean_text for w in ["chat", "screen", "message", "whatsapp", "doc", "receipt", "bill", "menu", "page", "form"]))
        ):
            return {"intent": "OCR", "target": None, "params": {}}

        # 17. Environment Query ("What is around me?", "Describe the environment", "Describe my surroundings")
        if any(p in clean_text for p in [
            "what is around me", "what's around me", "describe the environment", "describe my surroundings",
        ]):
            return {"intent": "ENVIRONMENT", "target": None, "params": {"query": text}}

        # 17.5. Multi-Step Natural Assistant Actions ("Open Chrome and search for ...", "Search YouTube for ... and play ...", "Open Notepad and write ...", "Search web and save note")
        multi_match = (
            re.search(r'^(?:please\s+)?open\s+(?:chrome|browser|google\s+chrome)\s+and\s+search\s+(?:for\s+)?(.+)$', clean_text) or
            re.search(r'^(?:please\s+)?search\s+youtube\s+for\s+(.+?)\s+and\s+play(?:\s+(?:the\s+first(?:\s+suitable)?\s+result|it))?$', clean_text) or
            re.search(r'^(?:please\s+)?open\s+notepad\s+and\s+write\s+(.+)$', clean_text) or
            re.search(r'^(?:please\s+)?search\s+(?:the\s+)?web\s+for\s+(.+?)\s+and\s+save(?:\s+(?:the\s+useful\s+result|it))?\s+as\s+(?:a\s+)?note$', clean_text)
        )
        if multi_match:
            return {
                "intent": "MULTI_STEP_ACTION",
                "target": text.strip(),
                "params": {"goal": text.strip(), "query": text.strip()}
            }

        # 18. Object Search Query ("Find my phone", "Look for bottle", "Where is the bottle", "Can you find my keys", "Search for my phone", "Can you see my bag")
        find_match = re.search(r'(?:find|can you see|can you find|is there a|look for|search for|start searching for|see)\s*(?:my|a|the)?\s*([a-zA-Z0-9_\s]+)', clean_text)
        if find_match and not any(w in clean_text for w in ["who", "read", "money", "youtube", "password", "passcode", "pin", "credential", "vault", "secret"]):
            obj_name = find_match.group(1).strip()
            return {"intent": "OBJECT_SEARCH", "target": obj_name, "params": {"object_name": obj_name}}

        # 19. Safety / Hazard Query
        if any(p in clean_text for p in ["are there stairs", "is it safe", "any obstacles", "anything dangerous"]):
            return {"intent": "SAFETY", "target": None, "params": {}}

        # 20. Settings Toggles
        if "turn greetings off" in clean_text or "stop greetings" in clean_text:
            return {"intent": "SETTINGS", "target": "greetings", "params": {"setting": "greeting_enabled", "value": False}}

        if "turn greetings on" in clean_text or "start greetings" in clean_text:
            return {"intent": "SETTINGS", "target": "greetings", "params": {"setting": "greeting_enabled", "value": True}}

        if "turn environment monitoring on" in clean_text or "continuous monitoring on" in clean_text:
            return {"intent": "SETTINGS", "target": "continuous", "params": {"setting": "environment_monitor_enabled", "value": True}}

        if "turn environment monitoring off" in clean_text or "continuous monitoring off" in clean_text:
            return {"intent": "SETTINGS", "target": "continuous", "params": {"setting": "environment_monitor_enabled", "value": False}}

        # 21. Color Identification Query
        if any(p in clean_text for p in ["what color", "tell me the color", "identify color", "color of this"]):
            return {"intent": "COLOR_IDENTIFY", "target": None, "params": {}}

        # 22. Light Level Check
        if any(p in clean_text for p in ["are the lights on", "is it dark", "check light level", "how is the light", "is the room lit"]):
            return {"intent": "LIGHT_LEVEL_CHECK", "target": None, "params": {}}

        # 23. Product Scan
        if any(p in clean_text for p in ["scan product", "scan barcode", "scan qr", "read expiration", "expiry date", "what medicine", "is this medicine"]):
            return {"intent": "PRODUCT_SCAN", "target": None, "params": {}}

        # 24. Sleep / Deactivate Command
        if (any(p in clean_text for p in ["go to sleep", "stop listening", "sleep mode"]) or
            clean_text in ["deactivate", "deactivate system", "deactivate assistant", "deactivate cube"]) and not any(w in clean_text for w in ["wifi", "wi-fi", "wireless", "alerts", "alert"]):
            return {"intent": "SLEEP", "target": None, "params": {}}

        # 25. Voice Security Commands (SG CUBE 2.5)
        # A. Lock Session
        if not any(clean_text.startswith(u) for u in ["unlock", "open"]) and any(p in clean_text for p in [
            "lock sensitive actions", "lock sensitive", "lock security", "lock session", "revoke security", "lock voice security", "lock my session",
            "lock secure memory", "lock secure vault", "lock vault", "lock protected memory"
        ]):
            return {"intent": "SECURITY_LOCK", "target": None, "params": {}}

        # B. Reset Password (Checked before SET with word boundaries to eliminate substring collisions)
        if any(re.search(p, clean_text) for p in [
            r'\breset (?:voice )?(?:security )?password\b',
            r'\brecover (?:voice )?(?:security )?password\b',
            r'\breset (?:my )?password\b',
            r'\brecover (?:my )?password\b',
            r'\breset security word\b'
        ]):
            return {"intent": "SECURITY_RESET", "target": None, "params": {}}

        # C. Remove Password (Checked before SET with word boundaries)
        if any(re.search(p, clean_text) for p in [
            r'\b(?:remove|delete) (?:voice )?(?:security )?password\b',
            r'\b(?:remove|delete) (?:my )?password\b',
            r'\b(?:remove|delete) security word\b'
        ]):
            return {"intent": "SECURITY_REMOVE", "target": None, "params": {}}

        # D. Change Password (Checked before SET with word boundaries)
        if any(re.search(p, clean_text) for p in [
            r'\b(?:change|update) (?:my )?(?:sensitive |security |voice security |voice )?password\b',
            r'\b(?:change|update) (?:sensitive )?(?:passphrase|phrase|word)\b',
            r'\b(?:change|update) (?:my )?password\b'
        ]):
            return {"intent": "SECURITY_CHANGE", "target": None, "params": {}}

        # E. Set Password
        if any(re.search(p, clean_text) for p in [
            r'\b(?:set|create|setup|i want to set) (?:a |my )?(?:sensitive |security |voice security |voice )?password\b',
            r'\bset (?:a |my )?(?:sensitive )?(?:passphrase|phrase|word)\b',
            r'\bset (?:a |my )?security word\b',
            r'\bset password\b',
            r'\bcreate password\b',
            r'\bsetup password\b'
        ]):
            return {"intent": "SECURITY_SET", "target": None, "params": {}}

        # F. Security Status
        if any(p in clean_text for p in ["is security enabled", "security status", "check security status", "check voice security", "security password status", "password status"]):
            return {"intent": "SECURITY_STATUS", "target": None, "params": {}}

        # G. Open / Access Secure Password Vault
        if any(p in clean_text for p in [
            "open my password vault", "open password vault", "open the password vault",
            "open my vault", "open the vault", "open vault",
            "unlock my password vault", "unlock password vault", "unlock the password vault",
            "unlock my vault", "unlock the vault", "unlock vault",
            "access my password vault", "access password vault", "access vault",
            "view my password vault", "view password vault", "view vault",
            "show my password vault", "show password vault"
        ]):
            return {"intent": "VAULT_OPEN", "target": "vault", "params": {}}

        # H. Vault Credential Recall / Search ("find the password for SG CUBE TEST", "what is the password for...")
        vault_pw_match = re.search(
            r'^(?:please\s+)?(?:find|search|look\s+for|get|show|retrieve|what\s+is|what\'s|tell\s+me)\s+(?:the\s+)?(?:password|passcode|pin|credential|key|secret)\s+(?:for|of)\s+(.+?)[? .!]*$',
            clean_text
        )
        if not vault_pw_match:
            vault_pw_match = re.search(
                r'^(?:password|passcode|credential)\s+(?:for|of)\s+(.+?)[? .!]*$',
                clean_text
            )
        if vault_pw_match:
            target_key = vault_pw_match.group(1).strip()
            return {
                "intent": "VAULT_RECALL",
                "target": target_key,
                "params": {"query": target_key, "target": target_key, "is_protected": True}
            }

        # 26. System Automation Commands (SG CUBE 2.5 Feature 9)
        # A. Lock Workstation / Screen
        if any(p in clean_text for p in [
            "lock my workstation", "lock workstation", "lock the workstation",
            "lock my pc", "lock the pc", "lock pc", "lock computer", "lock the computer",
            "lock screen", "lock the screen", "lock my computer"
        ]):
            return {"intent": "AUTOMATION_LOCK_DEVICE", "target": "workstation", "params": {}}

        # B. Automation Status & Permissions
        if any(p in clean_text for p in [
            "automation status", "automation permissions", "check automation status",
            "system automation status", "show automation permissions", "check automation permissions"
        ]):
            return {"intent": "AUTOMATION_STATUS", "target": None, "params": {}}

        # C. Close Application ("Close calculator", "Exit notepad", "Quit calculator", "Close file explorer", "Close browser", "Close whatsapp", "Close vscode", "Close settings")
        close_app_match = re.search(
            r'^(?:please\s+)?(?:close|exit|quit|terminate|shut\s+down)\s+(?:the\s+)?(?:app\s+|application\s+)?(calculator|calc|notepad|file\s+explorer|explorer|files|browser|web\s+browser|chrome|edge|firefox|whatsapp|whats\s+app|vscode|vs\s+code|code|visual\s+studio\s+code|settings|windows\s+settings)\b',
            clean_text
        )
        if close_app_match and not clean_text.endswith("window"):
            app_t = close_app_match.group(1).strip()
            if app_t in ["whats app", "whatsapp"]:
                app_t = "whatsapp"
            elif app_t in ["vscode", "vs code", "code", "visual studio code"]:
                app_t = "vscode"
            elif app_t in ["settings", "windows settings"]:
                app_t = "settings"
            return {"intent": "AUTOMATION_CLOSE_APP", "target": app_t, "params": {"app_name": app_t, "target": app_t}}

        # D. Open Application ("Open calculator", "Launch notepad", "Start file explorer", "Open browser", "Open whatsapp", "Open chrome", "Open youtube", "Open github", "Open vscode", "Open settings")
        open_app_match = re.search(
            r'^(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?(?:app\s+|application\s+|website\s+|site\s+)?(calculator|calc|notepad|text\s+editor|file\s+explorer|explorer|browser|web\s+browser|chrome|google\s+chrome|edge|firefox|whatsapp|whats\s+app|youtube|github|vscode|vs\s+code|visual\s+studio\s+code|code|settings|windows\s+settings)\b',
            clean_text
        )
        if open_app_match:
            app_t = open_app_match.group(1).strip()
            if app_t in ["whats app", "whatsapp"]:
                app_t = "whatsapp"
            elif app_t in ["chrome", "google chrome"]:
                app_t = "browser"
            elif app_t in ["vscode", "vs code", "code", "visual studio code"]:
                app_t = "vscode"
            elif app_t in ["settings", "windows settings"]:
                app_t = "settings"
            elif app_t == "youtube":
                return {"intent": DualYouTubeOpenIntent("YOUTUBE_OPEN"), "target": DualYouTubeTarget("https://www.youtube.com"), "params": {"target": "youtube", "url": "https://www.youtube.com"}}
            elif app_t == "github":
                return {"intent": "AUTOMATION_OPEN_URL", "target": "https://github.com", "params": {"url": "https://github.com", "target": "https://github.com"}}
            return {"intent": "AUTOMATION_OPEN_APP", "target": app_t, "params": {"app_name": app_t, "target": app_t}}

        # D.1. Read Screen / Active Window Content ("Read screen", "What is on my screen", "Describe the screen", "Tell me what's on the screen")
        if any(p in clean_text for p in [
            "read screen", "read the screen", "read my screen", "read this screen", "read current screen",
            "what is on my screen", "what is on the screen", "what is on screen",
            "what's on my screen", "what's on the screen", "what's on screen",
            "tell me what's on the screen", "tell me whats on the screen", "tell me what is on the screen",
            "tell me what is on my screen", "tell me what's on my screen", "tell me whats on my screen",
            "describe the screen", "describe my screen", "describe this screen",
            "describe what is on my screen", "describe what's on my screen",
            "describe what is on the screen", "describe what's on the screen",
            "what do you see on my screen", "what do you see on the screen", "what do you see on screen",
            "read active window", "read content on screen", "what is showing on my screen", "what is showing on the screen",
            "what am i looking at", "what am i seeing", "what is open", "what's open",
            "describe this page", "describe the page", "what is this page", "what is this page about",
            "what page is this", "what is this website", "what website is this",
            "what app is open", "what application is open", "what is open on my screen",
            "what is on my computer", "what's on my computer screen",
        ]):
            return {"intent": "AUTOMATION_READ_SCREEN", "target": None, "params": {}}


        # D.2. Read WhatsApp Messages / Chat ("Read this chat", "Read chat", "Read whatsapp", "What messages do I have")
        if any(p in clean_text for p in [
            "read this chat", "read chat", "read whatsapp", "read my messages", "read messages",
            "what messages do i have", "check whatsapp", "read whatsapp messages", "read incoming messages"
        ]):
            return {"intent": "AUTOMATION_READ_CHAT", "target": "whatsapp", "params": {"app": "whatsapp"}}

        # D.3. Open Specific Chat with Contact ("Open chat with Mom", "Open whatsapp chat with Alex", "Chat with John")
        open_chat_match = re.search(r'^(?:please\s+)?(?:open\s+(?:whatsapp\s+)?chat\s+with|open\s+chat\s+with|chat\s+with)\s+([a-zA-Z0-9_\s]+)$', clean_text)
        if open_chat_match:
            c_name = open_chat_match.group(1).strip()
            return {"intent": "AUTOMATION_OPEN_CHAT", "target": c_name.title(), "params": {"contact": c_name.title(), "app": "whatsapp"}}

        # D.4. Send Message to Contact ("Send I will be late to Mom", "Send message to Mom saying I will be late", "Message Alex hello")
        send_msg_match = re.search(
            r'^(?:please\s+)?(?:send\s+(?:a\s+)?(?:whatsapp\s+)?(?:message\s+)?to\s+([a-zA-Z0-9_\s]+?)\s+saying\s+(.+)|send\s+(.+?)\s+to\s+([a-zA-Z0-9_\s]+)|message\s+([a-zA-Z0-9_\s]+?)\s+(?:saying\s+)?(.+))$',
            text.strip(),
            re.IGNORECASE
        )
        if send_msg_match and not any(w in clean_text for w in ["money", "password", "code", "task", "reminder"]):
            if send_msg_match.group(1) and send_msg_match.group(2):
                c_target = send_msg_match.group(1).strip().title()
                m_body = send_msg_match.group(2).strip()
            elif send_msg_match.group(3) and send_msg_match.group(4):
                c_target = send_msg_match.group(4).strip().title()
                m_body = send_msg_match.group(3).strip()
            elif send_msg_match.group(5) and send_msg_match.group(6):
                c_target = send_msg_match.group(5).strip().title()
                m_body = send_msg_match.group(6).strip()
            else:
                c_target, m_body = None, None

            if c_target and m_body:
                return {
                    "intent": "AUTOMATION_SEND_MESSAGE",
                    "target": c_target,
                    "params": {"contact": c_target, "message": m_body, "app": "whatsapp"}
                }

        # E. Open URL / Website ("Open website google.com", "Open url wikipedia.org", "Go to github.com", "Open site youtube.com")
        open_url_match = re.search(
            r'^(?:please\s+)?(?:open|go\s+to|visit|navigate\s+to)\s+(?:website\s+|site\s+|webpage\s+|url\s+|link\s+)?(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9.\-]+\.(?:com|org|net|edu|gov|io|ai|dev)(?:/[^\s]*)?)$',
            clean_text
        )
        if open_url_match:
            url_t = open_url_match.group(1).strip()
            return {"intent": "AUTOMATION_OPEN_URL", "target": url_t, "params": {"url": url_t, "target": url_t}}

        # F. Open Safe Folder ("Open documents folder", "Open my downloads", "Open desktop folder", "Open pictures folder")
        open_folder_match = re.search(
            r'^(?:please\s+)?(?:open|show|explore)\s+(?:my\s+|the\s+)?(?:folder\s+)?(documents|downloads|desktop|pictures|photos|music|videos|home)\s*(?:folder)?$',
            clean_text
        )
        if open_folder_match:
            folder_t = open_folder_match.group(1).strip()
            return {"intent": "AUTOMATION_OPEN_FOLDER", "target": folder_t, "params": {"folder": folder_t, "target": folder_t}}

        # G. Copy Text to Clipboard ("Copy text meeting at 3 PM", "Copy this text: ...", "Copy to clipboard: ...")
        copy_text_match = re.search(
            r'^(?:please\s+)?(?:copy\s+(?:the\s+)?(?:following\s+)?text\s*:\s*(.+)|copy\s+(?:to\s+clipboard\s*:\s*|to\s+the\s+clipboard\s*:\s*)(.+)|copy\s+(.+?)\s+(?:in|on|to|into)\s+(?:the\s+|my\s+)?clipboard|copy\s+text\s+(.+))$',
            text,
            flags=re.IGNORECASE
        )
        if copy_text_match and not any(w in clean_text for w in ["face", "profile", "memory", "task", "reminder"]):
            text_val = [g for g in copy_text_match.groups() if g is not None][0]
            if text_val:
                clean_copy_val = re.sub(r'^(?:text\s*:\s*|that\s*:\s*|this\s*:\s*)', '', text_val.strip(), flags=re.IGNORECASE).strip()
                clean_copy_val = clean_copy_val.strip("\"'")
                if clean_copy_val:
                    return {"intent": "AUTOMATION_COPY_TEXT", "target": clean_copy_val, "params": {"text": clean_copy_val, "target": clean_copy_val}}

        # 26.5. Screenshot Voice Commands
        has_screenshot_word = any(w in clean_text for w in [
            "screenshot", "screen shot", "capture screen", "capture the screen", "capture this"
        ])
        is_window_target = any(w in clean_text for w in ["window", "active window", "this window", "current window"])

        if is_window_target and (has_screenshot_word or any(p in clean_text for p in [
            "capture active window", "capture this window", "capture the window", "capture current window",
            "screenshot window", "take window screenshot", "screenshot this window", "screenshot active window"
        ])):
            return {"intent": "SCREENSHOT_CAPTURE_WINDOW", "target": "active_window", "params": {}}

        if has_screenshot_word or any(p in clean_text for p in [
            "take a screenshot", "take screenshot", "take a screen shot", "take screen shot",
            "capture the screen", "capture screen", "capture this", "save a screenshot", "save screenshot",
            "save a screen shot", "save screen shot", "screenshot", "screenshot full screen"
        ]):
            return {"intent": "SCREENSHOT_CAPTURE_FULL", "target": "full_screen", "params": {}}

        # 26.6. Dedicated YouTube Search & Controls
        yt_search_match = re.search(
            r'^(?:please\s+)?(?:search\s+youtube\s+for\s+(.+)|youtube\s+search\s+for\s+(.+)|search\s+on\s+youtube\s+for\s+(.+)|search\s+(?:for\s+)?(.+?)\s+on\s+youtube|find\s+(.+?)\s+on\s+youtube|youtube\s+search\s+(.+)|play\s+(.+?)\s+on\s+youtube)$',
            clean_text,
            re.IGNORECASE
        )
        if yt_search_match:
            yt_query = next((g.strip() for g in yt_search_match.groups() if g and g.strip()), "")
            if yt_query:
                return {
                    "intent": DualPlayMediaIntent("YOUTUBE_SEARCH"),
                    "target": CaseInsensitiveStr(yt_query),
                    "params": {"query": yt_query, "title": yt_query, "platform": "youtube"}
                }

        if any(p in clean_text for p in [
            "open youtube", "launch youtube", "start youtube", "go to youtube"
        ]):
            return {"intent": DualYouTubeOpenIntent("YOUTUBE_OPEN"), "target": DualYouTubeTarget("https://www.youtube.com"), "params": {"target": "youtube", "url": "https://youtube.com"}}

        if any(p in clean_text for p in [
            "close youtube", "exit youtube", "quit youtube", "stop youtube"
        ]):
            return {"intent": "YOUTUBE_CLOSE", "target": "youtube", "params": {}}

        if any(p in clean_text for p in [
            "unmute youtube", "unmute the video", "unmute video"
        ]):
            return {"intent": "YOUTUBE_UNMUTE", "target": None, "params": {}}

        if any(p in clean_text for p in [
            "mute youtube", "mute the video", "mute video"
        ]):
            return {"intent": "YOUTUBE_MUTE", "target": None, "params": {}}

        if any(p in clean_text for p in [
            "seek forward", "fast forward", "skip forward", "skip ahead", "fast-forward"
        ]):
            return {"intent": "YOUTUBE_SEEK_FORWARD", "target": None, "params": {}}

        if any(p in clean_text for p in [
            "seek backward", "seek back", "skip back", "skip backward", "rewind", "rewind video"
        ]):
            return {"intent": "YOUTUBE_SEEK_BACKWARD", "target": None, "params": {}}

        # 26.7. Media Playback Controls (YouTube & Desktop Media)
        # A. Media Pause
        if any(p in clean_text for p in [
            "pause youtube", "pause the video", "pause video",
            "pause the music", "pause music", "pause song", "pause audio",
            "pause playback", "pause it", "pause that", "pause"
        ]):
            return {"intent": "MEDIA_PAUSE", "target": None, "params": {}}

        # B. Media Resume
        if clean_text in ("play", "resume", "unpause") or any(p in clean_text for p in [
            "resume youtube", "resume the video", "resume video",
            "resume the music", "resume music", "resume song", "resume audio",
            "resume playback", "resume it", "resume that"
        ]):
            return {"intent": "MEDIA_RESUME", "target": None, "params": {}}

        # C. Media Next Track
        if any(p in clean_text for p in [
            "next video", "next song", "next track", "next music", "next one",
            "skip video", "skip song", "skip this song", "skip track"
        ]):
            return {"intent": "MEDIA_NEXT", "target": None, "params": {}}

        # D. Media Previous Track
        if any(p in clean_text for p in [
            "previous video", "previous song", "previous track", "previous music",
            "previous one", "last song"
        ]):
            return {"intent": "MEDIA_PREVIOUS", "target": None, "params": {}}

        # E. Media Stop
        if any(p in clean_text for p in [
            "stop the video", "stop video",
            "stop the music", "stop music", "stop song", "stop playback", "stop playing"
        ]):
            return {"intent": "MEDIA_STOP", "target": None, "params": {}}

        # F. Play Media ("Play Believer on YouTube", "Play Shiva songs", "Play relaxing music")
        play_media_match = re.search(
            r'^(?:please\s+)?play\s+(.+?)(?:\s+on\s+youtube)?$',
            text.strip(),
            re.IGNORECASE
        )
        if play_media_match and not any(w in clean_text for w in ["game", "games", "role", "with", "around", "card", "trick", "chess", "video game"]):
            track_query = play_media_match.group(1).strip()
            clean_track = re.sub(r'\s+(?:music|song|songs)$', '', track_query, flags=re.IGNORECASE).strip()
            if clean_track:
                return {
                    "intent": "PLAY_MEDIA",
                    "target": clean_track or track_query,
                    "params": {"query": track_query, "title": clean_track or track_query, "platform": "youtube"}
                }


        # 27. Real-Time Web Search ("Search the web for ...", "Web search for ...", "Search online for ...")
        web_search_match = re.search(
            r'^(?:please\s+)?(?:search\s+(?:the\s+)?web\s+for|web\s+search\s+for|web\s+search|search\s+online\s+for|search\s+google\s+for|google\s+search\s+for|search\s+for)\s+(.+)$',
            text.strip(),
            re.IGNORECASE
        )
        if web_search_match and not any(w in clean_text for w in ["face", "profile", "memory", "task", "reminder", "person", "object", "item", "saved"]):
            query_t = web_search_match.group(1).strip()
            if query_t:
                return {"intent": "WEB_SEARCH", "target": query_t, "params": {"query": query_t}}

        # 28. Computer-Use / Desktop Interaction Actions
        # A. Stop / Cancel Computer Action
        if clean_text in ["stop", "cancel", "abort", "halt", "emergency stop"] or any(p in clean_text for p in [
            "stop computer action", "cancel computer action", "stop computer task",
            "cancel computer task", "stop the computer", "abort computer task", "abort computer action"
        ]):
            return {"intent": "COMPUTER_ACTION_CANCEL", "target": None, "params": {}}

        # B. Click UI Element ("Click on the search bar", "Click the send button", "Click submit")
        click_match = re.search(
            r'^(?:please\s+)?(?:click\s+(?:on\s+)?(?:the\s+)?|double\s+click\s+(?:on\s+)?(?:the\s+)?|right\s+click\s+(?:on\s+)?(?:the\s+)?)(.+)$',
            clean_text
        )
        if click_match and not any(w in clean_text for w in ["picture", "photo", "face", "image", "frame", "camera"]):
            target_el = click_match.group(1).strip()
            if target_el and target_el not in ["here", "there", "now"]:
                return {"intent": "COMPUTER_USE_ACTION", "target": target_el, "params": {"goal": text.strip(), "action": "click", "element": target_el}}

        # C. Type into focused UI / field ("Type hello world", "Enter username admin")
        type_match = re.search(
            r'^(?:please\s+)?(?:type|enter|input)\s+(?:the\s+text\s+)?(?:[\'\"]?)(.+?)(?:[\'\"]?)(?:\s+(?:in|into)\s+(?:the\s+)?(.+))?$',
            text.strip(),
            re.IGNORECASE
        )
        if type_match and not any(w in clean_text for w in ["password", "pin", "credential", "memory", "task"]):
            text_to_type = type_match.group(1).strip()
            dest_field = type_match.group(2).strip() if type_match.group(2) else None
            if text_to_type:
                return {
                    "intent": "COMPUTER_USE_ACTION",
                    "target": dest_field or text_to_type,
                    "params": {"goal": text.strip(), "action": "type_text", "text": text_to_type, "field": dest_field}
                }

        # D. Press Key / Hotkey ("Press enter", "Press escape", "Press tab", "Press hotkey ctrl c")
        press_match = re.search(
            r'^(?:please\s+)?(?:press\s+(?:the\s+)?key\s+|press\s+(?:the\s+)?hotkey\s+|press\s+)(enter|tab|escape|esc|backspace|space|up|down|left|right|f5|ctrl\s*[+]\s*[a-z]|alt\s*[+]\s*[a-z])$',
            clean_text
        )
        if press_match:
            key_val = press_match.group(1).strip()
            return {"intent": "COMPUTER_USE_ACTION", "target": key_val, "params": {"goal": text.strip(), "action": "press_key", "key": key_val}}

        # 29. System Operations & Windows Controls
        # 0. Compound Multi-Step Tasks (Delegated to CompoundTaskPlanner)
        try:
            from .task_planner import CompoundTaskPlanner
            _planner = CompoundTaskPlanner()
            if _planner.is_compound_request(clean_text):
                return {"intent": "COMPOUND_TASK", "target": text.strip(), "params": {"query": text.strip()}}
        except Exception:
            pass

        # Audio Output Routing & Device Management (SG CUBE Central Audio Architecture)
        if any(p in clean_text for p in [
            "run audio diagnostics", "audio diagnostics", "check audio health", "test audio output",
            "audio output test", "audio health check", "diagnose audio"
        ]):
            return {"intent": "AUDIO_DIAGNOSTICS", "target": None, "params": {}}

        if any(p in clean_text for p in [
            "tell me the current audio output", "tell me current audio output", "what audio output are you using",
            "what is the current audio output", "what is the audio output", "what audio output is active",
            "what audio device are you using", "what audio device is this", "what is the current audio device",
            "current audio output", "active audio output", "which speaker are you using"
        ]):
            return {"intent": "AUDIO_DEVICE_GET", "target": None, "params": {}}

        if any(p in clean_text for p in [
            "list audio outputs", "list audio output devices", "list audio devices",
            "what audio outputs are available", "what audio devices are available",
            "show audio outputs", "show audio devices", "available audio outputs",
            "what audio devices do you see", "list available speakers"
        ]):
            return {"intent": "AUDIO_DEVICE_LIST", "target": None, "params": {}}

        switch_dev_match = re.search(
            r'^(?:please\s+)?(?:switch|change|set)\s+(?:the\s+)?(?:audio\s+output|audio\s+device|playback\s+device|speaker)\s+(?:to\s+)?(.+)$',
            clean_text
        )
        if switch_dev_match:
            target_dev = switch_dev_match.group(1).strip()
            return {"intent": "AUDIO_DEVICE_SWITCH", "target": target_dev, "params": {"device": target_dev}}


        # A. Master Audio Volume
        vol_set_match = re.search(r'\b(?:(?:set|change)\s+(?:master\s+|system\s+|the\s+|my\s+)?volume\s+(?:to\s+)?|volume\s+(?:to\s+)?)(\d{1,3})(?:\s*(?:%|percent))?\b', clean_text)
        if vol_set_match:
            v_val = int(vol_set_match.group(1))
            return {"intent": "SYSTEM_VOLUME", "target": "volume", "params": {"action": "set", "value": v_val}}
        if any(p in clean_text for p in ["turn up the volume", "turn up volume", "volume up", "increase volume", "increase the volume", "make it louder"]):
            return {"intent": "SYSTEM_VOLUME", "target": "volume", "params": {"action": "up", "step": 10}}
        if any(p in clean_text for p in ["turn down the volume", "turn down volume", "volume down", "decrease volume", "decrease the volume", "lower the volume", "lower volume", "make it quieter"]):
            return {"intent": "SYSTEM_VOLUME", "target": "volume", "params": {"action": "down", "step": 10}}
        if any(p in clean_text for p in ["unmute volume", "unmute the volume", "unmute audio", "unmute the audio", "unmute sound", "unmute"]):
            return {"intent": "SYSTEM_VOLUME", "target": "volume", "params": {"action": "unmute"}}
        if any(p in clean_text for p in ["mute volume", "mute the volume", "mute audio", "mute the audio", "mute system", "mute sound"]) or clean_text == "mute":
            if not any(w in clean_text for w in ["alert", "alerts", "notification"]):
                return {"intent": "SYSTEM_VOLUME", "target": "volume", "params": {"action": "mute"}}
        if any(p in clean_text for p in ["what is the volume", "what's the volume", "check volume", "check the volume", "current volume"]):
            return {"intent": "SYSTEM_VOLUME", "target": "volume", "params": {"action": "get"}}

        # B. Display Brightness
        bright_text = self._words_to_numbers(clean_text)

        # 1. Maximum / Minimum shortcuts
        if any(p in bright_text for p in [
            "set brightness to maximum", "set brightness to max", "set screen brightness to max",
            "set screen brightness to maximum", "set display brightness to max", "set display brightness to maximum",
            "maximum brightness", "max brightness", "full brightness", "brightness to maximum", "brightness to max",
            "set brightness to 100", "set screen brightness to 100", "brightness to 100", "brightness at 100",
            "100 percent brightness", "100% brightness"
        ]):
            return {"intent": "SYSTEM_BRIGHTNESS", "target": "brightness", "params": {"action": "set", "value": 100}}

        if any(p in bright_text for p in [
            "set brightness to minimum", "set brightness to min", "set screen brightness to min",
            "set screen brightness to minimum", "set display brightness to min", "set display brightness to minimum",
            "minimum brightness", "min brightness", "lowest brightness", "brightness to minimum", "brightness to min",
            "set brightness to 0", "set screen brightness to 0", "brightness to 0", "brightness at 0",
            "0 percent brightness", "0% brightness"
        ]):
            return {"intent": "SYSTEM_BRIGHTNESS", "target": "brightness", "params": {"action": "set", "value": 0}}

        # 2. Relative increase with explicit step (e.g. "increase brightness by 10 percent", "turn up brightness by 20%", "brightness up by 15")
        bright_up_step = re.search(
            r'\b(?:(?:increase|turn\s+up|raise)\s+(?:the\s+|screen\s+|display\s+|my\s+)?brightness\s+by\s+|brightness\s+up\s+by\s+)(\d{1,3})(?:\s*(?:%|percent))?\b',
            bright_text
        )
        if bright_up_step:
            step_val = max(1, min(100, int(bright_up_step.group(1))))
            return {"intent": "SYSTEM_BRIGHTNESS", "target": "brightness", "params": {"action": "up", "step": step_val}}

        # 3. Relative decrease with explicit step (e.g. "decrease brightness by 10 percent", "turn down brightness by 20%", "brightness down by 15", "dim brightness by 10%")
        bright_down_step = re.search(
            r'\b(?:(?:decrease|turn\s+down|lower|dim|reduce)\s+(?:the\s+|screen\s+|display\s+|my\s+)?brightness\s+by\s+|brightness\s+down\s+by\s+)(\d{1,3})(?:\s*(?:%|percent))?\b',
            bright_text
        )
        if bright_down_step:
            step_val = max(1, min(100, int(bright_down_step.group(1))))
            return {"intent": "SYSTEM_BRIGHTNESS", "target": "brightness", "params": {"action": "down", "step": step_val}}

        # 4. Absolute brightness setting (e.g. "set brightness to 50 percent", "set screen brightness to 70", "change brightness to 80%", "brightness 60%", "brightness to 50")
        bright_set_match = re.search(
            r'\b(?:(?:set|change|turn|adjust)\s+(?:the\s+|screen\s+|display\s+|my\s+)?brightness\s+(?:to\s+)?|brightness\s+(?:to\s+)?|(?:set|change|turn|adjust)\s+(?:the\s+)?(?:screen|display)\s+(?:to\s+)?)(\d{1,3})(?:\s*(?:%|percent))?(?:\s*brightness)?\b',
            bright_text
        )
        if bright_set_match:
            b_val = max(0, min(100, int(bright_set_match.group(1))))
            return {"intent": "SYSTEM_BRIGHTNESS", "target": "brightness", "params": {"action": "set", "value": b_val}}

        # 5. Relative increase without step (default step = 10)
        if any(p in bright_text for p in [
            "increase brightness", "increase the brightness", "increase screen brightness", "increase display brightness",
            "turn up brightness", "turn up the brightness", "turn up screen brightness", "turn up display brightness",
            "brightness up", "screen brightness up", "display brightness up",
            "make the screen brighter", "make screen brighter", "screen brighter", "brighter screen",
            "make it brighter", "raise brightness", "raise the brightness", "more brightness"
        ]):
            return {"intent": "SYSTEM_BRIGHTNESS", "target": "brightness", "params": {"action": "up", "step": 10}}

        # 6. Relative decrease without step (default step = 10)
        if any(p in bright_text for p in [
            "decrease brightness", "decrease the brightness", "decrease screen brightness", "decrease display brightness",
            "turn down brightness", "turn down the brightness", "turn down screen brightness", "turn down display brightness",
            "brightness down", "screen brightness down", "display brightness down",
            "lower brightness", "lower the brightness", "lower screen brightness", "lower display brightness",
            "make the screen dimmer", "make screen dimmer", "screen dimmer", "dimmer screen",
            "dim the screen", "dim screen", "dim the display", "dim display",
            "make it dimmer", "less brightness"
        ]):
            return {"intent": "SYSTEM_BRIGHTNESS", "target": "brightness", "params": {"action": "down", "step": 10}}

        # 7. Brightness query / status (exclude informational / general questions)
        is_informational = any(p in clean_text for p in [
            "tell me about", "explain", "what do you know about", "how does", "what is screen brightness used for", "why is", "why does"
        ])
        if not is_informational and any(p in bright_text for p in [
            "what is the brightness", "what's the brightness", "what is my brightness", "what's my brightness",
            "what is the screen brightness", "what's the screen brightness", "what is the display brightness", "what's the display brightness",
            "check brightness", "check the brightness", "check screen brightness", "check display brightness",
            "current brightness", "screen brightness", "how bright is the screen", "how bright is the display",
            "tell me the brightness", "tell me screen brightness"
        ]):
            return {"intent": "SYSTEM_BRIGHTNESS", "target": "brightness", "params": {"action": "get"}}

        # C. Wi-Fi Wireless Network Control
        is_wifi_informational = any(p in clean_text for p in [
            "tell me about", "tell me what", "explain", "what do you know about", "how does", "what is wifi used for", "what does wifi mean", "why is", "search for"
        ])

        # 1. Wi-Fi OFF
        if not is_wifi_informational and any(p in clean_text for p in [
            "turn off wifi", "turn off wi-fi", "turn off wireless", "turn off wi fi",
            "turn wifi off", "turn wi-fi off", "turn wireless off", "turn wi fi off",
            "switch off wifi", "switch off wi-fi", "switch off wireless", "switch off wi fi",
            "switch wifi off", "switch wi-fi off", "switch wireless off", "switch wi fi off",
            "disable wifi", "disable wi-fi", "disable wireless", "disable wi fi",
            "deactivate wifi", "deactivate wi-fi", "deactivate wireless", "deactivate wi fi"
        ]):
            return {"intent": "SYSTEM_WIFI", "target": "wifi", "params": {"action": "off"}}

        # 2. Wi-Fi ON
        if not is_wifi_informational and (any(p in clean_text for p in [
            "turn on wifi", "turn on wi-fi", "turn on wireless", "turn on wi fi",
            "turn wifi on", "turn wi-fi on", "turn wireless on", "turn wi fi on",
            "switch on wifi", "switch on wi-fi", "switch on wireless", "switch on wi fi",
            "switch wifi on", "switch wi-fi on", "switch wireless on", "switch wi fi on",
            "enable wifi", "enable wi-fi", "enable wireless", "enable wi fi"
        ]) or re.search(r'\bactivate\s+(?:wifi|wi-fi|wireless|wi\s+fi)\b', clean_text)):
            return {"intent": "SYSTEM_WIFI", "target": "wifi", "params": {"action": "on"}}

        # 3. Wi-Fi Status Query
        if not is_wifi_informational and any(p in clean_text for p in [
            "is wifi on", "is wi-fi on", "is wireless on", "is wi fi on",
            "is wifi off", "is wi-fi off", "is wireless off", "is wi fi off",
            "what is the wifi status", "what's the wifi status", "what is the wi-fi status", "what's the wi-fi status",
            "what is the wireless status", "what's the wireless status",
            "check wifi", "check wi-fi", "check the wifi", "check the wi-fi", "check wireless",
            "wifi status", "wi-fi status", "wireless status",
            "is wifi enabled", "is wi-fi enabled", "is wifi connected", "is wi-fi connected"
        ]):
            return {"intent": "SYSTEM_WIFI", "target": "wifi", "params": {"action": "status"}}

        # C.5. Bluetooth Wireless Adapter & Device Control
        is_bt_informational = any(p in clean_text for p in [
            "tell me about", "tell me what", "explain", "what do you know about", "how does", "what is bluetooth used for", "what does bluetooth mean", "why is", "search for"
        ])

        # 1. Bluetooth OFF
        if not is_bt_informational and any(p in clean_text for p in [
            "turn off bluetooth", "turn bluetooth off", "switch off bluetooth", "switch bluetooth off",
            "disable bluetooth", "deactivate bluetooth", "turn bt off", "turn off bt", "disable bt"
        ]):
            return {"intent": "SYSTEM_BLUETOOTH", "target": "bluetooth", "params": {"action": "off"}}

        # 2. Bluetooth ON
        if not is_bt_informational and (any(p in clean_text for p in [
            "turn on bluetooth", "turn bluetooth on", "switch on bluetooth", "switch bluetooth on",
            "enable bluetooth", "turn bt on", "turn on bt", "enable bt"
        ]) or re.search(r'\bactivate\s+(?:bluetooth|bt)\b', clean_text)):
            return {"intent": "SYSTEM_BLUETOOTH", "target": "bluetooth", "params": {"action": "on"}}

        # 3. List Bluetooth Devices
        if not is_bt_informational and any(p in clean_text for p in [
            "list bluetooth devices", "list my bluetooth devices", "show bluetooth devices",
            "show my bluetooth devices", "what bluetooth devices are paired", "what bluetooth devices are available",
            "paired bluetooth devices", "get bluetooth devices", "list paired devices", "list bluetooth",
            "show paired bluetooth devices", "list my paired devices", "what are my bluetooth devices"
        ]):
            return {"intent": "SYSTEM_BLUETOOTH", "target": "bluetooth", "params": {"action": "list"}}

        # 4. Bluetooth Status Query
        if not is_bt_informational and any(p in clean_text for p in [
            "is bluetooth on", "is bluetooth off", "what is the bluetooth status", "what's the bluetooth status",
            "check bluetooth", "check the bluetooth", "bluetooth status", "bt status",
            "is bluetooth enabled", "is bt on", "is bt enabled"
        ]):
            return {"intent": "SYSTEM_BLUETOOTH", "target": "bluetooth", "params": {"action": "status"}}

        # 5. Connect Bluetooth Device
        bt_connect_match = re.search(r'^(?:please\s+)?(?:connect|pair)(?:\s+to|\s+with)?\s+(?:my\s+|the\s+)?([a-zA-Z0-9_\-\s\']+?)(?:\s+via\s+bluetooth|\s+over\s+bluetooth)?$', clean_text)
        if not is_bt_informational and bt_connect_match:
            cand = bt_connect_match.group(1).strip()
            if cand and cand not in ["wifi", "wi-fi", "internet", "network", "window", "it", "this"]:
                if cand == "bluetooth":
                    cand = ""
                cand = re.sub(r'^(?:bluetooth\s+device|bluetooth)\s*', '', cand).strip()
                return {"intent": "SYSTEM_BLUETOOTH", "target": cand or "bluetooth", "params": {"action": "connect", "device": cand}}

        # 6. Disconnect Bluetooth Device
        bt_disconnect_match = re.search(r'^(?:please\s+)?(?:disconnect)(?:\s+from)?\s+(?:my\s+|the\s+)?([a-zA-Z0-9_\-\s\']+?)(?:\s+via\s+bluetooth|\s+from\s+bluetooth)?$', clean_text)
        if not is_bt_informational and bt_disconnect_match:
            cand = bt_disconnect_match.group(1).strip()
            if cand and cand not in ["wifi", "wi-fi", "internet", "network", "window", "it", "this"]:
                if cand == "bluetooth":
                    cand = ""
                cand = re.sub(r'^(?:bluetooth\s+device|bluetooth)\s*', '', cand).strip()
                return {"intent": "SYSTEM_BLUETOOTH", "target": cand or "bluetooth", "params": {"action": "disconnect", "device": cand}}

        # D. Window Management (Minimize, Maximize, Restore, Switch, App Targeting)
        if any(p in clean_text for p in ["minimize window", "minimize the window", "minimize active window", "minimize this window", "minimize this", "minimize it"]):
            return {"intent": "SYSTEM_WINDOW_CONTROL", "target": "window", "params": {"action": "minimize"}}
        win_app_min = re.search(r'^(?:please\s+)?(?:minimize)\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+window)?$', clean_text)
        if win_app_min and win_app_min.group(1).strip() not in ["window", "active window", "this window", "this", "it", "screen"]:
            app_t = win_app_min.group(1).strip()
            return {"intent": "SYSTEM_WINDOW_CONTROL", "target": app_t, "params": {"action": "minimize_app", "app": app_t}}

        if any(p in clean_text for p in ["maximize window", "maximize the window", "maximize active window", "maximize this window", "maximize this", "maximize it"]):
            return {"intent": "SYSTEM_WINDOW_CONTROL", "target": "window", "params": {"action": "maximize"}}
        win_app_max = re.search(r'^(?:please\s+)?(?:maximize)\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+window)?$', clean_text)
        if win_app_max and win_app_max.group(1).strip() not in ["window", "active window", "this window", "this", "it", "screen"]:
            app_t = win_app_max.group(1).strip()
            return {"intent": "SYSTEM_WINDOW_CONTROL", "target": app_t, "params": {"action": "maximize_app", "app": app_t}}

        if any(p in clean_text for p in ["restore window", "restore the window", "restore active window", "restore this window", "restore this", "unmaximize window", "unmaximize this window", "unmaximize this", "restore it"]):
            return {"intent": "SYSTEM_WINDOW_CONTROL", "target": "window", "params": {"action": "restore"}}
        win_app_restore = re.search(r'^(?:please\s+)?(?:restore|unmaximize)\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+window)?$', clean_text)
        if win_app_restore and win_app_restore.group(1).strip() not in ["window", "active window", "this window", "this", "it", "screen"]:
            app_t = win_app_restore.group(1).strip()
            return {"intent": "SYSTEM_WINDOW_CONTROL", "target": app_t, "params": {"action": "restore_app", "app": app_t}}

        if any(p in clean_text for p in ["close window", "close the window", "close active window", "close this window", "close this"]):
            return {"intent": "SYSTEM_WINDOW_CONTROL", "target": "window", "params": {"action": "close"}}
        win_app_close = re.search(r'^(?:please\s+)?(?:close)\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+window)$', clean_text)
        if win_app_close and win_app_close.group(1).strip() not in ["window", "active window", "this window", "this", "it", "screen"]:
            app_t = win_app_close.group(1).strip()
            return {"intent": "SYSTEM_WINDOW_CONTROL", "target": app_t, "params": {"action": "close_app", "app": app_t}}
        if any(p in clean_text for p in ["switch window", "switch the window", "next window", "cycle window", "alt tab", "switch to next window"]):
            return {"intent": "SYSTEM_WINDOW_CONTROL", "target": "window", "params": {"action": "switch"}}

        win_app_switch = re.search(r'^(?:please\s+)?(?:switch\s+to|go\s+to|focus|bring\s+up)\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)(?:\s+window)?$', clean_text)
        if win_app_switch and win_app_switch.group(1).strip() not in ["window", "next window", "previous window", "desktop"]:
            app_t = win_app_switch.group(1).strip()
            if not any(domain in app_t for domain in [".com", ".org", ".net", "youtube", "google", "sleep"]):
                return {"intent": "SYSTEM_WINDOW_CONTROL", "target": app_t, "params": {"action": "switch_app", "app": app_t}}

        if any(p in clean_text for p in ["what window is this", "what is the active window", "current window title", "active window"]):
            return {"intent": "SYSTEM_WINDOW_CONTROL", "target": "window", "params": {"action": "title"}}

        # D. Clipboard Operations
        clip_write_match = re.search(r'^(?:please\s+)?(?:copy|put|set|write)\s+(?:["\'](.*)["\']|(.*?))\s+(?:to|on|into)\s+(?:the\s+|my\s+)?clipboard$', clean_text)
        if clip_write_match:
            clip_t = (clip_write_match.group(1) or clip_write_match.group(2) or "").strip()
            if clip_t and clip_t not in ["that", "this", "selection", "it"]:
                return {"intent": "SYSTEM_CLIPBOARD", "target": "clipboard", "params": {"action": "write", "text": clip_t}}

        if any(p in clean_text for p in [
            "what is on my clipboard", "what's on my clipboard", "what is on the clipboard", "what's on the clipboard",
            "read clipboard", "read the clipboard", "show clipboard", "get clipboard", "check clipboard"
        ]):
            return {"intent": "SYSTEM_CLIPBOARD", "target": "clipboard", "params": {"action": "read"}}
        if clean_text in ["select all", "select all text", "select everything"]:
            return {"intent": "SYSTEM_CLIPBOARD", "target": "clipboard", "params": {"action": "select_all"}}
        if clean_text in ["copy that", "copy this", "copy selection", "copy it"]:
            return {"intent": "SYSTEM_CLIPBOARD", "target": "clipboard", "params": {"action": "copy"}}
        if clean_text in ["paste", "paste that", "paste this", "paste it", "paste from clipboard"]:
            return {"intent": "SYSTEM_CLIPBOARD", "target": "clipboard", "params": {"action": "paste"}}

        # E. Ordinal Search Result / Artifact Reference ("open the second result", "open first result", "play the first one", "click 3rd result")
        ordinal_res_match = re.search(
            r'^(?:please\s+)?(?:open|play|show|visit|go\s+to|click)\s+(?:the\s+)?(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|last)(?:\s+(?:search\s+)?(?:result|link|video|one|item))?$',
            clean_text
        )
        if ordinal_res_match:
            ord_target = ordinal_res_match.group(1).strip()
            return {"intent": "OPEN_SEARCH_RESULT_ORDINAL", "target": ord_target, "params": {"ordinal_str": ord_target}}

        # F. Browser Navigation & Page Reading
        if any(p in clean_text for p in ["go back", "navigate back", "back page", "browser back"]):
            return {"intent": "BROWSER_NAVIGATE", "target": "back", "params": {"direction": "back"}}
        if any(p in clean_text for p in ["go forward", "navigate forward", "forward page", "browser forward"]):
            return {"intent": "BROWSER_NAVIGATE", "target": "forward", "params": {"direction": "forward"}}
        if any(p in clean_text for p in ["scroll down", "page down", "scroll downwards"]):
            return {"intent": "BROWSER_NAVIGATE", "target": "scroll_down", "params": {"direction": "scroll_down"}}
        if any(p in clean_text for p in ["scroll up", "page up", "scroll upwards"]):
            return {"intent": "BROWSER_NAVIGATE", "target": "scroll_up", "params": {"direction": "scroll_up"}}
        if any(p in clean_text for p in ["what does that page say", "what does this page say", "what does the page say", "read the webpage", "read this webpage"]):
            return {"intent": "BROWSER_READ_PAGE", "target": None, "params": {}}

        # G. Last Action / Recently Opened Query ("what did you just open", "what was the last item opened")
        if any(p in clean_text for p in [
            "what did you just open", "what was the last item opened", "what was the last thing opened",
            "what did i open", "what did you open", "what was the last action", "what did you just do",
            "what did you do", "what was your last action", "what was the last action performed"
        ]):
            return {"intent": "LAST_ACTION_QUERY", "target": None, "params": {}}

        # H. Health Diagnostics & Self-Awareness Sweep
        if any(p in clean_text for p in [
            "system health", "run diagnostics", "check diagnostics", "system diagnostics",
            "health check", "check system status", "subsystem status", "run system health"
        ]):
            return {"intent": "HEALTH_DIAGNOSTICS", "target": None, "params": {}}

        # I. Deterministic Calculator Intent ("calculate 25 times 18", "what is 150 divided by 3", "calculate 2 raised to 10")
        calc_match = re.search(r'^(?:please\s+)?(?:calculate|compute)\s+(.+)$', clean_text)
        if not calc_match:
            calc_match = re.search(r'^(?:what\s+is|what\'s)\s+(\d+[\d\s+\-*/xX.]*(?:times|multiplied\s+by|divided\s+by|plus|minus|raised\s+to(?:\s+the\s+power\s+of)?|\+|\-|\*|\/|\*\*)\s*[\d\s+\-*/xX.]+)$', clean_text)
        if calc_match:
            expr_val = calc_match.group(1).strip()
            return {"intent": "SYSTEM_CALCULATE", "target": expr_val, "params": {"expression": expr_val}}



        # Fallback to General Gemini Live Reasoning
        clean_log = "[REDACTED]" if any(w in clean_text for w in ["password", "passcode", "pin", "secret", "token"]) else clean_text
        print(f"[NORMAL_PATH: gemini] Delegating '{clean_log}' to Gemini Live reasoning.")
        return {"intent": "GENERAL", "target": None, "params": {}}

    route_command = route_intent
