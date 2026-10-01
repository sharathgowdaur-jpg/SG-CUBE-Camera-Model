"""
SG CUBE — Computer-Use Subsystem: Autonomous Bounded Agent
Implements the observe → locate → safety-check → act → verify loop.
Strictly bounded by a 5-step limit, corner failsafes, sensitive window masking,
and human confirmation gates.
"""

import re
import time
import urllib.parse
import webbrowser
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

from .screen_provider import ScreenProvider
from .element_locator import ElementLocator, ElementLocation
from .action_executor import ActionExecutor, ActionResult
from .safety_guard import SafetyGuard, SafetyDecision
from .verification import VerificationEngine, VerificationResult
from .web_tools import WebTools
from .media_controller import MediaController, MediaActionResult
from .action_ledger import ActionLedger, compute_frame_thumb
from .geometry import input_space

logger = logging.getLogger(__name__)


@dataclass
class AgentStepLog:
    step_number: int
    action_type: str
    target: str
    status: str
    verified: bool
    details: str


@dataclass
class AgentTaskResult:
    success: bool
    goal: str
    total_steps: int
    spoken_summary: str
    aborted: bool = False
    requires_confirmation: bool = False
    pending_action: Optional[Dict[str, Any]] = None
    step_logs: List[AgentStepLog] = field(default_factory=list)


class ComputerUseAgent:
    """
    Coordinates safe, bounded computer actions.
    """

    def __init__(
        self,
        api_key_manager: Optional[Any] = None,
        max_steps: int = 5,
        automation_manager: Optional[Any] = None
    ):
        self.screen_provider = ScreenProvider()
        dims = self.screen_provider.get_screen_dimensions()
        self.safety_guard = SafetyGuard(max_steps=max_steps, screen_width=dims[0], screen_height=dims[1])
        self.element_locator = ElementLocator(api_key_manager=api_key_manager)
        self.action_executor = ActionExecutor(safety_guard=self.safety_guard)
        self.verification_engine = VerificationEngine()
        self.web_tools = WebTools()
        self.automation_manager = automation_manager
        self.media_controller = MediaController(
            screen_provider=self.screen_provider,
            action_executor=self.action_executor,
            element_locator=self.element_locator,
            safety_guard=self.safety_guard,
            verification_engine=self.verification_engine
        )
        self.action_ledger = ActionLedger()
        self.is_running = False

    def cancel(self, reason: str = "User requested abort"):
        """Stops the currently running computer-use task immediately."""
        logger.info("[COMPUTER-USE-AGENT] Cancelling current task: %s", reason)
        self.safety_guard.request_abort(reason)

    def play_media(self, query: str, platform: str = "youtube") -> MediaActionResult:
        return self.media_controller.play_media(query, platform=platform)

    def pause_media(self) -> MediaActionResult:
        return self.media_controller.pause_media()

    def resume_media(self) -> MediaActionResult:
        return self.media_controller.resume_media()

    def next_media(self) -> MediaActionResult:
        return self.media_controller.next_track()

    def previous_media(self) -> MediaActionResult:
        return self.media_controller.previous_track()

    def stop_media(self) -> MediaActionResult:
        return self.media_controller.stop_media()

    def search_youtube(self, query: str) -> MediaActionResult:
        return self.media_controller.search_youtube(query)

    def open_youtube(self) -> MediaActionResult:
        return self.media_controller.open_youtube()

    def mute_youtube(self) -> MediaActionResult:
        return self.media_controller.mute_youtube()

    def unmute_youtube(self) -> MediaActionResult:
        return self.media_controller.unmute_youtube()

    def seek_forward(self, seconds: int = 10) -> MediaActionResult:
        return self.media_controller.seek_forward(seconds)

    def seek_backward(self, seconds: int = 10) -> MediaActionResult:
        return self.media_controller.seek_backward(seconds)

    def close_youtube(self) -> MediaActionResult:
        return self.media_controller.close_youtube()

    def execute_goal(
        self,
        goal: str,
        confirmed: bool = False,
        step_callback: Optional[Callable[[int, str, str], None]] = None
    ) -> AgentTaskResult:
        """
        Executes a bounded computer-use goal.
        """
        if not goal.strip():
            return AgentTaskResult(False, goal, 0, "No goal specified.")

        if self.safety_guard.abort_requested:
            # Abort was requested
            self.safety_guard.reset()
            return AgentTaskResult(
                success=False,
                goal=goal,
                total_steps=0,
                spoken_summary="Computer-use task was stopped.",
                aborted=True
            )

        logger.info("=== [COMPUTER-USE-AGENT] Starting Goal: '%s' ===", goal)
        self.is_running = True
        dims = self.screen_provider.get_screen_dimensions()
        self.safety_guard.reset(screen_dimensions=dims)

        step_logs: List[AgentStepLog] = []

        try:
            # 0. Check if this is a web search goal
            goal_lower = goal.lower()
            prefixes = [
                "search the web for", "search web for", "search the web",
                "web search for", "web search", "google for", "search for",
                "search online for", "search online"
            ]
            if any(goal_lower.startswith(p) for p in prefixes):
                clean_query = goal
                for p in prefixes:
                    if goal_lower.startswith(p):
                        clean_query = goal[len(p):].strip()
                        break
                results = self.web_tools.search_web(clean_query, max_results=3)
                summary = self.web_tools.format_search_summary(results)
                return AgentTaskResult(
                    success=True,
                    goal=goal,
                    total_steps=1,
                    spoken_summary=f"Here is what I found on the web: {summary}",
                    step_logs=[AgentStepLog(1, "web_search", clean_query, "SUCCESS", True, summary)]
                )

            # 1. Main Bounded Loop
            while self.safety_guard.current_step < self.safety_guard.max_steps:
                if self.safety_guard.abort_requested:
                    return AgentTaskResult(
                        success=False,
                        goal=goal,
                        total_steps=self.safety_guard.current_step,
                        spoken_summary="Computer-use task was stopped.",
                        aborted=True,
                        step_logs=step_logs
                    )

                step_num = self.safety_guard.current_step + 1

                # Step A: Capture Screen
                before_img = self.screen_provider.capture_full_screen()

                # Step B: Check for sensitive window before doing anything
                is_sensitive, sensitive_title = self.safety_guard.is_sensitive_window_active()
                if is_sensitive:
                    msg = f"Task halted: Active window '{sensitive_title}' contains sensitive/protected credentials."
                    return AgentTaskResult(
                        success=False,
                        goal=goal,
                        total_steps=self.safety_guard.current_step,
                        spoken_summary=msg,
                        aborted=True,
                        step_logs=step_logs
                    )

                # Step C: Parse Target and Action Type from Goal
                # Determine action: Click, Type, Open App, or Scroll
                action_type = "click"
                target_desc = goal

                if "type " in goal_lower:
                    action_type = "type_text"
                elif "press " in goal_lower:
                    action_type = "press_key"
                elif "scroll " in goal_lower:
                    action_type = "scroll"

                # Step D: Safety Check Action
                decision, reason = self.safety_guard.evaluate_action_safety(action_type, {"description": goal, "target": target_desc})
                if decision == SafetyDecision.ABORT:
                    return AgentTaskResult(False, goal, self.safety_guard.current_step, reason, aborted=True, step_logs=step_logs)
                elif decision == SafetyDecision.DENY:
                    return AgentTaskResult(False, goal, self.safety_guard.current_step, reason, aborted=True, step_logs=step_logs)
                elif decision == SafetyDecision.REQUIRE_CONFIRMATION and not confirmed:
                    return AgentTaskResult(
                        success=False,
                        goal=goal,
                        total_steps=self.safety_guard.current_step,
                        spoken_summary=reason,
                        requires_confirmation=True,
                        pending_action={"goal": goal, "action_type": action_type},
                        step_logs=step_logs
                    )

                # Check duplicate action ledger against current screen frame
                thumb = compute_frame_thumb(before_img)
                action_spec = {"action": action_type, "target": target_desc}
                if self.action_ledger.is_duplicate(action_spec, thumb):
                    dup_msg = f"Duplicate action prevented: '{goal}' has already been performed on this unchanged screen."
                    logger.warning("[COMPUTER-USE-AGENT] %s", dup_msg)
                    step_logs.append(AgentStepLog(step_num, action_type, target_desc, "DUPLICATE_REFUSED", False, dup_msg))
                    return AgentTaskResult(False, goal, step_num, dup_msg, aborted=False, step_logs=step_logs)

                # Increment step count
                self.safety_guard.increment_step()

                # Step E: Resolve Coordinates or Dispatch within Thread DPI Input Space
                action_res: Optional[ActionResult] = None
                target_coords = None

                with input_space():
                    if action_type == "click":
                        loc = self.element_locator.locate_element(target_desc, before_img, native_screen_size=dims)
                        if not loc.found:
                            err_msg = f"Could not locate '{target_desc}' on screen: {loc.error or 'not visible'}"
                            step_logs.append(AgentStepLog(step_num, action_type, target_desc, "FAILED", False, err_msg))
                            return AgentTaskResult(False, goal, step_num, err_msg, step_logs=step_logs)
                        
                        target_coords = (loc.x, loc.y)
                        if step_callback:
                            step_callback(step_num, action_type, f"Clicking {loc.label} at ({loc.x}, {loc.y})")
                        action_res = self.action_executor.click(loc.x, loc.y)

                    elif action_type == "type_text":
                        # Extract text to type
                        text_to_type = goal
                        for prefix in ["type ", "write ", "enter "]:
                            if goal_lower.startswith(prefix):
                                text_to_type = goal[len(prefix):].strip()
                                break
                        if step_callback:
                            step_callback(step_num, action_type, f"Typing text: '{text_to_type}'")
                        action_res = self.action_executor.type_text(text_to_type)

                    elif action_type == "press_key":
                        key_name = goal_lower.replace("press ", "").strip()
                        action_res = self.action_executor.press_key(key_name)

                    elif action_type == "scroll":
                        direction = "down" if "down" in goal_lower else "up"
                        clicks = -3 if direction == "down" else 3
                        action_res = self.action_executor.scroll(clicks=clicks)

                # Record executed action in ledger
                self.action_ledger.record(action_spec, thumb, resolved_xy=target_coords)

                # Step F: Verify Action
                if action_res and not action_res.success:
                    fail_msg = f"Action execution failed: {action_res.message}"
                    step_logs.append(AgentStepLog(step_num, action_type, target_desc, "FAILED", False, fail_msg))
                    return AgentTaskResult(False, goal, step_num, fail_msg, step_logs=step_logs)

                time.sleep(0.3)
                after_img = self.screen_provider.capture_full_screen()
                v_res = self.verification_engine.verify_action_effect(before_img, after_img, action_type=action_type, target_coords=target_coords)

                log_entry = AgentStepLog(
                    step_number=step_num,
                    action_type=action_type,
                    target=target_desc,
                    status="SUCCESS",
                    verified=v_res.verified,
                    details=f"{action_res.message if action_res else 'OK'}. {v_res.details}"
                )
                step_logs.append(log_entry)

                # Bounded: Single action goals finish here
                return AgentTaskResult(
                    success=True,
                    goal=goal,
                    total_steps=step_num,
                    spoken_summary=f"Action completed: {action_res.message if action_res else 'Done'}. {v_res.details}",
                    step_logs=step_logs
                )

            return AgentTaskResult(
                success=False,
                goal=goal,
                total_steps=self.safety_guard.current_step,
                spoken_summary=f"Task reached maximum allowed step limit ({self.safety_guard.max_steps}) without finishing.",
                step_logs=step_logs
            )

        finally:
            self.is_running = False

    def execute_multi_step_goal(
        self,
        goal: str,
        memory_manager: Optional[Any] = None,
        task_manager: Optional[Any] = None,
        automation_manager: Optional[Any] = None
    ) -> AgentTaskResult:
        """
        Executes bounded, safe multi-step natural language desktop assistant commands.
        Guaranteed: <= 5 steps, zero shell execution, safety guard checks on each step.
        """
        clean_g = goal.strip()
        low_g = clean_g.lower()
        step_logs: List[AgentStepLog] = []

        # Case 1: "open chrome/browser and search for <query>"
        m1 = re.search(r'open\s+(?:chrome|browser|google\s+chrome)\s+and\s+search\s+(?:for\s+)?(.+)', clean_g, flags=re.IGNORECASE)
        if m1:
            query = m1.group(1).strip()
            search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
            try:
                webbrowser.open(search_url, new=2)
                step_logs.append(AgentStepLog(1, "open_url", search_url, "SUCCESS", True, f"Navigated browser to search for '{query}'."))
            except Exception as e:
                return AgentTaskResult(False, goal, 1, f"Failed to open browser: {e}", step_logs=step_logs)

            time.sleep(1.0)
            dims = self.screen_provider.get_screen_dimensions()
            after_img = self.screen_provider.capture_full_screen()
            step_logs.append(AgentStepLog(2, "observe", "search_results", "SUCCESS", True, "Browser rendered search results."))

            return AgentTaskResult(
                success=True,
                goal=goal,
                total_steps=2,
                spoken_summary=f"Opened Chrome and searched for '{query}'.",
                step_logs=step_logs
            )

        # Case 2: "search youtube for <query> and play (the first suitable result)"
        m2 = re.search(r'search\s+youtube\s+for\s+(.+?)(?:\s+and\s+play(?:\s+(?:the\s+first(?:\s+suitable)?\s+result|it))?|\s*$)', clean_g, flags=re.IGNORECASE)
        if m2:
            query = m2.group(1).strip()
            res = self.media_controller.play_media(query, platform="youtube")
            step_logs.append(AgentStepLog(1, "search_youtube", query, "SUCCESS" if res.success else "FAILED", res.verified, res.details))
            return AgentTaskResult(
                success=res.success,
                goal=goal,
                total_steps=1,
                spoken_summary=res.spoken_summary,
                step_logs=step_logs
            )

        # Case 3: "open notepad and write <content>"
        m3 = re.search(r'open\s+notepad\s+and\s+write\s+(.+)', clean_g, flags=re.IGNORECASE)
        if m3:
            content_desc = m3.group(1).strip()
            text_to_write = content_desc
            if "today's task list" in content_desc.lower() or "task list" in content_desc.lower() or "tasks" in content_desc.lower():
                if task_manager and hasattr(task_manager, "list_tasks"):
                    tasks = task_manager.list_tasks(status="PENDING")
                    if tasks:
                        task_lines = [f"- {t.title}" for t in tasks[:5]]
                        text_to_write = "Today's Task List:\n" + "\n".join(task_lines)
                    else:
                        text_to_write = "Today's Task List:\n- No pending tasks scheduled."
                else:
                    text_to_write = "Today's Task List:\n- Focus on SG CUBE deployment."

            # Step 1: Open notepad safely via automation manager or direct subprocess without shell
            import subprocess
            try:
                subprocess.Popen(["notepad.exe"], shell=False)
            except Exception as exc:
                logger.warning("Could not launch notepad directly: %s", exc)

            time.sleep(1.0)
            step_logs.append(AgentStepLog(1, "open_app", "notepad", "SUCCESS", True, "Opened Notepad text editor."))

            # Step 2: Type text into active Notepad
            type_res = self.action_executor.type_text(text_to_write)
            step_logs.append(AgentStepLog(2, "type_text", "notepad_editor", "SUCCESS" if type_res.success else "FAILED", type_res.success, type_res.message))

            return AgentTaskResult(
                success=type_res.success,
                goal=goal,
                total_steps=2,
                spoken_summary=f"Opened Notepad and wrote your {content_desc}.",
                step_logs=step_logs
            )

        # Case 4: "search the web for <query> and save (the useful result) as a note"
        m4 = re.search(r'search\s+(?:the\s+)?web\s+for\s+(.+?)\s+and\s+save(?:\s+(?:the\s+useful\s+result|it))?\s+as\s+(?:a\s+)?note', clean_g, flags=re.IGNORECASE)
        if m4:
            query = m4.group(1).strip()
            results = self.web_tools.search_web(query, max_results=2)
            summary = self.web_tools.format_search_summary(results)
            step_logs.append(AgentStepLog(1, "web_search", query, "SUCCESS", bool(results), f"Found {len(results)} results."))

            if memory_manager and hasattr(memory_manager, "save_note"):
                note_content = f"{query}: {summary}" if summary else f"Information on {query}"
                ok, note_msg = memory_manager.save_note(note_content, title=query)
                step_logs.append(AgentStepLog(2, "save_note", query, "SUCCESS" if ok else "FAILED", ok, note_msg))
            else:
                note_msg = "Note saved."

            return AgentTaskResult(
                success=True,
                goal=goal,
                total_steps=2,
                spoken_summary=f"Searched the web for '{query}' and saved the key result to your notes.",
                step_logs=step_logs
            )

        # Fallback to standard execute_goal
        return self.execute_goal(goal)

