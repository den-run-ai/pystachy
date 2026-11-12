"""Run-scoped state, rewrite pressure and the single step recorder.

Mirrors ``state.py``. This leaf module depends only on action records and
JSON helpers; it never loads configuration or imports policy, transport or
CLI code. The attempt- and step-scoped records that ``loop.py`` defines live
here too, so the policies can name their types without importing the loop.
"""

from __future__ import annotations

from typing import Callable

from native_actions import ActionEnvelope, ActionTransport, SkippedStep, StepReceipt
from native_host import path_name
from native_json import JSONValue, copy_dict, get_str, str_items

REWRITE_PRESSURE_WRITES = 2
REWRITE_SKIP_WRITES = 3
WRITE_PRESSURE_OBSERVATIONS = 3


class PendingWrite:
    """A newly recorded zero-byte write obligation."""

    def __init__(
        self, name: str, append_allowed: bool, append_targets: list[str], recovery_arg: str | None
    ) -> None:
        self.name = name
        self.append_allowed = append_allowed
        self.append_targets = append_targets
        self.recovery_arg = recovery_arg

    def describe(self) -> dict[str, JSONValue]:
        """Result/model projection, detached from the typed record."""
        record: dict[str, JSONValue] = {
            "name": self.name,
            "append_allowed": self.append_allowed,
            "append_targets": str_items(self.append_targets),
            "recovery_arg": self.recovery_arg,
        }
        return record


def _stored_list(data: dict[str, JSONValue], key: str) -> list[JSONValue]:
    value = data[key]
    if isinstance(value, list):
        return value
    raise TypeError("run state field '" + key + "' is not a list")


def _stored_int(data: dict[str, JSONValue], key: str) -> int:
    value = data[key]
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise TypeError("run state field '" + key + "' is not an integer")


class RunProgress:
    """Typed access and mutation ownership over one live state dict.

    This is not a second state store. Fields resolve at use time, so replacing
    ``errors``/``last_steps`` stays visible; constructing a view never
    populates a sparse mapping. A strict accessor raises ``KeyError`` for a
    field the run has not created yet, as indexing the dictionary would.
    """

    def __init__(self, data: dict[str, JSONValue]) -> None:
        self.data = data

    def errors(self) -> list[JSONValue]:
        return _stored_list(self.data, "errors")

    def add_error(self, message: str) -> None:
        _stored_list(self.data, "errors").append(message)

    def completed_tasks(self) -> list[JSONValue]:
        return _stored_list(self.data, "completed_tasks")

    def completed_step_groups(self) -> list[JSONValue]:
        return _stored_list(self.data, "completed_step_groups")

    def all_steps(self) -> list[JSONValue]:
        return _stored_list(self.data, "all_steps")

    def last_steps(self) -> list[JSONValue]:
        return _stored_list(self.data, "last_steps")

    def selected_steps(self) -> int:
        return _stored_int(self.data, "selected_steps")

    def executed_steps(self) -> int:
        return _stored_int(self.data, "executed_steps")

    def skipped_steps(self) -> int:
        return _stored_int(self.data, "skipped_steps")

    def pending_empty_writes(self) -> dict[str, JSONValue]:
        value = self.data["pending_empty_writes"]
        if isinstance(value, dict):
            return value
        raise TypeError("run state field 'pending_empty_writes' is not an object")

    def optional_last_steps(self) -> list[JSONValue]:
        value = self.data.get("last_steps")
        if isinstance(value, list):
            return value
        empty: list[JSONValue] = []
        return empty

    def optional_all_steps(self) -> list[JSONValue]:
        value = self.data.get("all_steps")
        if isinstance(value, list):
            return value
        empty: list[JSONValue] = []
        return empty

    def optional_completed_tasks(self) -> list[JSONValue]:
        value = self.data.get("completed_tasks")
        if isinstance(value, list):
            return value
        empty: list[JSONValue] = []
        return empty

    def optional_pending_empty_writes(self) -> dict[str, JSONValue]:
        value = self.data.get("pending_empty_writes")
        if isinstance(value, dict):
            return value
        empty: dict[str, JSONValue] = {}
        return empty

    def set_pending_write(self, target: str, record: PendingWrite) -> None:
        self.pending_empty_writes()[target] = record.describe()


class StepRecorder:
    """The single record-and-count path for controller steps.

    Counter semantics: ``selected`` counts every decoded model action,
    including ``done``/``fail``; ``executed`` counts model actions dispatched
    to handlers (deterministic repair/retry receipts are recorded but never
    counted as executed); ``skipped`` counts selected actions a controller
    guard suppressed before dispatch. Per attempt, selected == executed +
    skipped + accepted control actions.
    """

    def __init__(
        self,
        state: dict[str, JSONValue],
        history: list[JSONValue],
        event_sink: Callable[[dict[str, JSONValue]], None],
    ) -> None:
        self.state = state
        self.history = history
        self._event_sink: Callable[[dict[str, JSONValue]], None] = event_sink

    def _event(self, event: dict[str, JSONValue]) -> None:
        self._event_sink(event)

    def progress(self) -> RunProgress:
        return RunProgress(self.state)

    def selected(self) -> None:
        self.state["selected_steps"] = _stored_int(self.state, "selected_steps") + 1

    def executed(self) -> None:
        self.state["executed_steps"] = _stored_int(self.state, "executed_steps") + 1

    def control(self, task_index: int, step: int, act: str) -> None:
        """Record an accepted model control action, never execution evidence.

        Refused ``done`` claims use ``skip`` instead. Keeping this out of
        last_steps/all_steps preserves duplicate context and validation
        evidence while making accepted done/fail selections observable.
        """
        event: dict[str, JSONValue] = {
            "event": "step_control",
            "task_index": task_index,
            "step": step,
            "action": act,
        }
        self.history.append(copy_dict(event))
        self._event(event)

    def skip(
        self, task_index: int, step: int, act: str, action: ActionEnvelope, reason: str
    ) -> None:
        """Record a selected-but-not-dispatched action in run metrics + log."""
        self.state["skipped_steps"] = _stored_int(self.state, "skipped_steps") + 1
        record = SkippedStep(task_index, step, act, action.text("arg"), reason)
        self._event(record.jsonl_event())

    def note(self, entry: dict[str, JSONValue]) -> None:
        """Model-visible corrective observation: enters the sliding window
        only, never the run-wide structured record or the JSONL log."""
        self.progress().last_steps().append(entry)

    def record(
        self, receipt: StepReceipt, task_index: int, step: int, wall_s: float | None = None
    ) -> dict[str, JSONValue]:
        """Append a receipt to every projection; returns the live entry."""
        entry = receipt.entry
        progress = self.progress()
        progress.last_steps().append(entry)
        progress.all_steps().append(copy_dict(entry))
        self.history.append(receipt.history_event(task_index, step))
        self._event(receipt.jsonl_event(task_index, step, wall_s))
        return entry

    def append_recovery_hint(self, hint: str) -> None:
        """Suffix the newest recorded step's output with a recovery hint."""
        progress = self.progress()
        for steps in (progress.last_steps(), progress.all_steps()):
            newest = steps[-1]
            if isinstance(newest, dict):
                newest["output"] = get_str(newest, "output")[:100] + f" → {hint}"


class RunState:
    """Typed owner of run-scoped controller data.

    ``data`` is the structured state dict the run result carries and the
    planner/executor summaries are curated from; the single
    :class:`StepRecorder` projects receipts into it and ``history``. The
    rewrite-damping fields live here because they are run-scoped, not
    attempt-scoped: a task-local retry or full replan must not let the
    executor restart a same-target full-write streak; only the documented
    successful shell/edit and truncation paths disarm it.
    """

    def __init__(
        self,
        reasoning_policy: str,
        goal_context_chars: int,
        clock: Callable[[], float],
        event_sink: Callable[[dict[str, JSONValue]], None],
        rewrite_pressure_writes: int = REWRITE_PRESSURE_WRITES,
        rewrite_skip_writes: int = REWRITE_SKIP_WRITES,
    ) -> None:
        self.clock: Callable[[], float] = clock
        self.rewrite_pressure_writes = rewrite_pressure_writes
        self.rewrite_skip_writes = rewrite_skip_writes
        no_pending: dict[str, JSONValue] = {}
        self.data: dict[str, JSONValue] = {
            "completed_tasks": json_list(),
            "errors": json_list(),
            "validated_once": False,
            "validation_attempts": 0,
            "validation_recheck_needed": False,
            "validated_step_count": 0,
            "completed_step_groups": json_list(),
            "all_steps": json_list(),
            # Empty sentinel truncations dispatch no mutation, but a following
            # `done` must not treat the failed write attempt as completion.
            "pending_empty_writes": no_pending,
            "task_start_step_count": 0,
            "reasoning_policy": reasoning_policy,
            "goal_context_chars": goal_context_chars,
            # Selected vs executed accounting: the gap between actions the
            # model selected and actions that reached the dispatcher must be
            # first-class in run metrics, not reconstructed from logs.
            "selected_steps": 0,
            "executed_steps": 0,
            "skipped_steps": 0,
        }
        self.history: list[JSONValue] = []
        self.recorder: StepRecorder = StepRecorder(self.data, self.history, event_sink)
        self.started: float = self.clock()
        self.last_write_target: str | None = None
        self.consecutive_target_writes = 0

    def progress(self) -> RunProgress:
        return RunProgress(self.data)

    def elapsed(self) -> float:
        """Wall seconds since the run started."""
        return self.clock() - self.started

    def disarm_rewrite_damping(self) -> None:
        """Forget the streak entirely (documented truncation-recovery paths)."""
        self.last_write_target = None
        self.consecutive_target_writes = 0

    def break_rewrite_streak(self) -> None:
        """A successful shell/edit ends the streak; observations never do."""
        self.consecutive_target_writes = 0

    def note_successful_full_write(self, target: str | None) -> None:
        """Advance or restart the same-target full-write streak."""
        if target == self.last_write_target:
            self.consecutive_target_writes += 1
        else:
            self.last_write_target = target
            self.consecutive_target_writes = 1

    def rewrite_skip_armed(self, target: str | None) -> bool:
        """True when further full rewrites of ``target`` must be skipped."""
        return (
            self.last_write_target is not None
            and self.consecutive_target_writes >= self.rewrite_skip_writes
            and target == self.last_write_target
        )

    def validate_pressure_target(self) -> str | None:
        """Basename the executor must verify once rewrites repeat, or None."""
        target = self.last_write_target
        if target is not None and self.consecutive_target_writes >= self.rewrite_pressure_writes:
            return path_name(target)
        return None


def json_list() -> list[JSONValue]:
    """A fresh empty JSON array."""
    items: list[JSONValue] = []
    return items


class TaskAttemptState:
    """Executor-facing state scoped to one attempt of one task.

    A task-local replan constructs a fresh attempt; nothing here survives
    into the next attempt except what the run-scoped record already holds.
    """

    def __init__(
        self,
        task: str,
        wants_write: bool,
        write_pressure_observations: int = WRITE_PRESSURE_OBSERVATIONS,
    ) -> None:
        self.task = task
        self.wants_write = wants_write
        self.done = False
        self.steps: list[JSONValue] = []
        self.use_think = False
        self.reasoning_trigger = "executor"
        self.dup_skip_count = 0
        self.observe_executed = 0
        self.commit_executed = 0
        self.observe_blocked = 0
        self.write_pressure_observations = write_pressure_observations

    def write_pressure(self) -> bool:
        """True once observation spending must yield to a first commit."""
        return (
            self.wants_write
            and self.commit_executed == 0
            and self.observe_executed >= self.write_pressure_observations
        )


class StepContext:
    """Working data for one selected executor action within an attempt."""

    def __init__(
        self,
        task_index: int,
        step: int,
        started: float,
        action: ActionEnvelope,
        act: str,
        transport: ActionTransport,
    ) -> None:
        self.task_index = task_index
        self.step = step
        self.started = started
        self.action = action
        self.act = act
        self.transport = transport
        self.truncated_write = False
        self.logical_write_target: str | None = None
        self.operation_write_target: str | None = None
