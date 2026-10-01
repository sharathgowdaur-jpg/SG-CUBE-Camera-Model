"""
Multi-Step Task Planner for SG CUBE

Decomposes compound user requests into bounded, sequential steps:
e.g. "Open Chrome, search YouTube for relaxing music, and play the first result."
"Open Notepad and write my task list."
"Search the web for today's weather and save the result to Local Memory."

Features:
- Sub-millisecond deterministic compound request detection
- Bounded step decomposition (max 5 steps)
- Sequential step-by-step execution with post-step verification
- Immediate STOP / CANCEL / ABORT interruption
- Natural spoken status summaries

Adapted from InterGenJLU JARVIS task planner architecture.
"""

from __future__ import annotations

import re
import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

COMPOUND_SIGNALS = [
    "and then", "then", ", then",
    ", and then", ", and also", "and also",
    ", and", "after that"
]


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class PlanStep:
    step_id: int
    intent: str
    command_text: str
    description: str
    params: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result_text: str = ""
    error_message: Optional[str] = None


@dataclass
class PlanExecutionResult:
    success: bool
    total_steps: int
    completed_steps: int
    aborted: bool = False
    spoken_summary: str = ""
    step_results: List[PlanStep] = field(default_factory=list)


IMPERATIVE_VERBS = [
    "open", "launch", "type", "write", "enter", "select all", "select",
    "copy", "paste", "close", "exit", "search", "play", "calculate",
    "tell", "minimize", "maximize", "restore", "switch", "focus",
    "click", "press", "pause", "resume", "set", "check", "turn",
    "mute", "unmute", "read", "scroll", "show", "run"
]


class CompoundTaskPlanner:
    """Decomposes compound commands and orchestrates verified, bounded execution."""

    def __init__(self, max_steps: int = 5):
        self.max_steps = max_steps
        self._interrupted = False

    def is_compound_request(self, text: str) -> bool:
        """Fast deterministic check whether user command is a compound multi-step request."""
        clean = (text or "").strip().lower()
        if len(clean) < 10:
            return False
        # Do not treat pure informational questions as compound
        if clean.startswith(("what is", "who is", "define", "how to")):
            return False
        if any(sig in clean for sig in COMPOUND_SIGNALS):
            return True
        verb_matches = [v for v in IMPERATIVE_VERBS if re.search(r'\b' + re.escape(v) + r'\b', clean)]
        return len(verb_matches) >= 2 and ("," in clean or " and " in clean or " then " in clean)

    def decompose_task(self, text: str) -> List[PlanStep]:
        """
        Decomposes compound command string into sequential PlanSteps.
        Limits to max_steps to prevent unbounded execution.
        """
        clean = text.strip()
        pattern = (
            r'(?:,\s*and\s+then\s+|,\s*then\s+|\s+and\s+then\s+|\s+then\s+|,\s*and\s+also\s+|'
            r'\s+and\s+also\s+|,\s*and\s+|\s+after\s+that\s+|\s+after\s+that\s+|'
            r'\s+and\s+(?=(?:' + '|'.join(IMPERATIVE_VERBS) + r')\b)|'
            r',\s*(?=(?:' + '|'.join(IMPERATIVE_VERBS) + r')\b))'
        )
        raw_parts = [p.strip(" ,.;") for p in re.split(pattern, clean, flags=re.IGNORECASE) if p.strip(" ,.;")]
        steps: List[PlanStep] = []

        for idx, part in enumerate(raw_parts[:self.max_steps], start=1):
            part_clean = re.sub(r'^(?:please\s+)?(?:then\s+)?(?:and\s+)?', '', part, flags=re.IGNORECASE).strip(" ,.;")
            if not part_clean:
                continue

            steps.append(PlanStep(
                step_id=idx,
                intent="STEP_COMMAND",
                command_text=part_clean,
                description=f"Step {idx}: {part_clean}"
            ))

        return steps

    def abort(self):
        """Immediately abort active plan execution."""
        self._interrupted = True
        logger.info("[PLANNER] Plan execution abort requested.")

    def reset(self):
        """Reset interruption flag for a new execution."""
        self._interrupted = False

    def execute_plan(
        self,
        steps: List[PlanStep],
        step_executor: Callable[[str], Tuple[bool, str]],
        is_cancelled: Optional[Callable[[], bool]] = None
    ) -> PlanExecutionResult:
        """
        Executes decomposed steps sequentially.
        step_executor: function taking command string and returning (success, response_message)
        """
        completed = 0
        total = len(steps)

        for step in steps:
            # Check interruption
            if self._interrupted or (is_cancelled and is_cancelled()):
                step.status = StepStatus.ABORTED
                step.error_message = "Cancelled by user"
                return PlanExecutionResult(
                    success=False,
                    total_steps=total,
                    completed_steps=completed,
                    aborted=True,
                    spoken_summary="Task cancelled.",
                    step_results=steps
                )

            step.status = StepStatus.RUNNING
            logger.info("[PLANNER] Executing %s: '%s'", step.description, step.command_text)

            try:
                ok, message = step_executor(step.command_text)
                step.result_text = message
                if ok:
                    step.status = StepStatus.COMPLETED
                    completed += 1
                else:
                    step.status = StepStatus.FAILED
                    step.error_message = message
                    logger.warning("[PLANNER] Step %d failed: %s. Stopping chain.", step.step_id, message)
                    return PlanExecutionResult(
                        success=False,
                        total_steps=total,
                        completed_steps=completed,
                        aborted=False,
                        spoken_summary=f"Task stopped at step {step.step_id}: {message}",
                        step_results=steps
                    )
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error_message = str(e)
                logger.error("[PLANNER] Step %d raised exception: %s", step.step_id, e)
                return PlanExecutionResult(
                    success=False,
                    total_steps=total,
                    completed_steps=completed,
                    aborted=False,
                    spoken_summary=f"Task encountered an error at step {step.step_id}.",
                    step_results=steps
                )

        return PlanExecutionResult(
            success=True,
            total_steps=total,
            completed_steps=completed,
            aborted=False,
            spoken_summary=f"Completed all {completed} steps successfully.",
            step_results=steps
        )
