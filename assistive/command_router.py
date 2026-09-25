import re
from typing import Dict, Optional, Tuple

OFFICIAL_INTRODUCTION = """Hi! I’m SG CUBE — your AI vision companion. 👋

I can see, listen, remember, and help you understand the world around you.

I can recognize faces, read text, find objects, detect currency, remember useful information, and talk with you naturally.

Basically, I’m like a helpful friend… except I never ask, ‘Where did I keep my phone?’ while holding it in my hand. 😂

See. Understand. Remember. Assist. That’s SG CUBE."""

class CommandRouter:
    """
    Intelligent Intent Parser & Command Router for Voice Queries.
    Maps natural language spoken commands to specialized perception, memory, and security routines.
    """

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
        clean = text.strip()
        # Strip any combination of leading command prefixes
        body = re.sub(
            r'^(?:please\s+)?(?:remember|save|store)\s+(?:(?:that|this|info|information|the\s+fact\s+that|a\s+note\s+that|note\s+that|to\s+memory|as\s+protected|in\s+secure\s+memory|to\s+secure\s+memory|in\s+secure\s+vault|to\s+secure\s+vault|in\s+vault|to\s+vault|protected\s+memory|secure\s+memory)\s*)*(?::\s*)?',
            '', clean, flags=re.IGNORECASE
        ).strip()
        body = re.sub(r'^(?:as\s+protected|in\s+secure\s+memory|to\s+secure\s+memory|in\s+secure\s+vault|to\s+secure\s+vault|in\s+vault|to\s+vault|protected\s+memory|secure\s+memory)\s*(?::\s*)?', '', body, flags=re.IGNORECASE).strip()
        body_cleaned = re.sub(r'[^\w\s]', '', body).strip().lower()

        # If bare command without specific inline fact (e.g. 'save this', 'save info', 'remember this', 'save this information')
        if not body or body_cleaned in ["", "this", "that", "it", "info", "information", "detail", "details", "memory", "note", "notes", "this info", "this information", "this detail", "this note"]:
            return "contextual", ""

        # Strip any leading 'this:' or 'that:' or 'info:' if present
        body_clean_val = re.sub(r'^(?:this|that|info|information)\s*:\s*', '', body, flags=re.IGNORECASE).strip()
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

        clean_text = text.strip().lower()

        # 0. Conversation Context Reset ("Start a new conversation", "Clear conversation context", "Reset conversation")
        if any(p in clean_text for p in [
            "start a new conversation", "start new conversation", "clear conversation context",
            "forget this conversation context", "forget conversation context", "reset conversation context",
            "reset conversation", "clear context", "forget context", "start fresh conversation",
            "new conversation", "start fresh"
        ]):
            return {"intent": "CONTEXT_RESET", "target": None, "params": {}}

        # 0.1. Follow-up Reminder Modification ("Make it 7 PM", "Change that reminder to 7 PM", "Move it to tomorrow")
        rem_edit_match = re.search(r'\b(?:make\s+it|change\s+it\s+to|change\s+that\s+reminder\s+to|move\s+it\s+to|reschedule\s+(?:it|that\s+reminder)\s+to)\s+(.+)', clean_text)
        if rem_edit_match:
            new_val = rem_edit_match.group(1).strip()
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

        # 1. Face Memory Enrollment ("Remember my face as Sharath", "Save this face as Sahana", "Enroll face as Alex")
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
            if not any(w in clean_text for w in ["all", "memories", "face", "faces", "everyone"]):
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

        # F. Explicit Person Location Query ("Where is the person?", "Where is Sharath?", "Where is the unknown person?")
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
            # Exclude recall question forms ("What do you remember", "Do you remember", "Who is", "Where did")
            if not any(w in clean_text for w in ["do you", "can you", "what", "who", "where", "how", "person", "face"]):
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
            # Exclude standard visual queries
            if not any(w in clean_text for w in ["in front of me", "around me", "this person", "this face", "this"]):
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
            "what is around me", "what's around me", "describe the environment", "describe my surroundings"
        ]):
            return {"intent": "ENVIRONMENT", "target": None, "params": {"query": text}}

        # Generic visual questions ("what do you see", "what is in front of me", "describe the scene") fall through to Gemini Live Multimodal Vision.

        # 18. Object Search Query ("Find my phone", "Look for bottle", "Where is the bottle", "Can you find my keys", "Search for my phone")
        find_match = re.search(r'(?:find|can you see|can you find|is there a|look for|search for|start searching for)\s*(?:my|a|the)?\s*([a-zA-Z0-9_\s]+)', clean_text)
        if find_match and not any(w in clean_text for w in ["who", "read", "money"]):
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
        if any(p in clean_text for p in ["go to sleep", "stop listening", "sleep mode", "deactivate"]):
            return {"intent": "SLEEP", "target": None, "params": {}}

        # 25. Voice Security Commands (SG CUBE 2.5)
        # A. Lock Session
        if any(p in clean_text for p in [
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

        # C. Close Application ("Close calculator", "Exit notepad", "Quit calculator", "Close file explorer", "Close browser", "Close whatsapp")
        close_app_match = re.search(
            r'^(?:please\s+)?(?:close|exit|quit|terminate|shut\s+down)\s+(?:the\s+)?(?:app\s+|application\s+)?(calculator|calc|notepad|file\s+explorer|explorer|files|browser|web\s+browser|chrome|edge|firefox|whatsapp|whats\s+app)\b',
            clean_text
        )
        if close_app_match:
            app_t = close_app_match.group(1).strip()
            if app_t in ["whats app", "whatsapp"]:
                app_t = "whatsapp"
            return {"intent": "AUTOMATION_CLOSE_APP", "target": app_t, "params": {"app_name": app_t, "target": app_t}}

        # D. Open Application ("Open calculator", "Launch notepad", "Start file explorer", "Open browser", "Open whatsapp")
        open_app_match = re.search(
            r'^(?:please\s+)?(?:open|launch|start)\s+(?:the\s+)?(?:app\s+|application\s+)?(calculator|calc|notepad|text\s+editor|file\s+explorer|explorer|browser|web\s+browser|chrome|edge|firefox|whatsapp|whats\s+app)\b',
            clean_text
        )
        if open_app_match:
            app_t = open_app_match.group(1).strip()
            if app_t in ["whats app", "whatsapp"]:
                app_t = "whatsapp"
            return {"intent": "AUTOMATION_OPEN_APP", "target": app_t, "params": {"app_name": app_t, "target": app_t}}

        # D.1. Read Screen / Active Window Content ("Read screen", "What is on my screen", "What do you see on my screen")
        if any(p in clean_text for p in [
            "read screen", "read the screen", "what is on my screen", "what is on the screen",
            "what's on my screen", "what's on the screen", "read my screen", "what do you see on my screen",
            "what is on screen", "read active window", "read content on screen", "what is showing on my screen"
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
            r'^(?:please\s+)?(?:copy\s+(?:the\s+)?(?:following\s+)?(?:text\s+)?(?:to\s+clipboard\s*)?:?\s*(.+)|copy\s+(.+)\s+to\s+clipboard)$',
            clean_text
        )
        if copy_text_match and not any(w in clean_text for w in ["face", "profile", "memory", "task", "reminder"]):
            text_val = copy_text_match.group(1) or copy_text_match.group(2)
            if text_val:
                clean_copy_val = re.sub(r'^(?:text\s*:\s*|that\s*:\s*|this\s*:\s*)', '', text_val.strip(), flags=re.IGNORECASE).strip()
                if clean_copy_val:
                    return {"intent": "AUTOMATION_COPY_TEXT", "target": clean_copy_val, "params": {"text": clean_copy_val, "target": clean_copy_val}}

        # Fallback to General Gemini Live Reasoning
        return {"intent": "GENERAL", "target": None, "params": {}}

    route_command = route_intent
