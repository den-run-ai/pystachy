"""Step, write-obligation and completion policies (mirrors ``policies.py``).

Policy algorithms own their decisions and consume the run state and a few
explicit services. Model calls stay injected; importing this module does not
load configuration, credentials, the CLI or the provider client. Completion
claims, validation verdicts and terminal records remain separate evidence.
"""

from __future__ import annotations

import re
from typing import Callable

from native_actions import (
    OBSERVE_ACTIONS,
    SHELL_TIMEOUT_LONG,
    SHELL_TIMEOUT_MAX,
    ActionEnvelope,
    ActionResult,
    _get_shell_timeout,
    _mutation_target_key,
    _read_key,
    _target_recovery_arg,
)
from native_host import path_name
from native_json import (
    JSONValue,
    as_dict,
    get_flag,
    get_int,
    get_str,
    str_items,
    truthy,
)
from native_state import PendingWrite, RunProgress, RunState, StepContext, TaskAttemptState

_VALIDATE_KEYWORDS = re.compile(
    r"\b(compile|build|test|run|execute|fix|debug|repair|verify|install|server|api|script|program)\b",
    re.I,
)

# Control-flow outcome of a step decision inside one task attempt.
FLOW_DISPATCH = 0  # no decision: continue to the next guard, then dispatch
FLOW_NEXT_STEP = 1  # handled; select the next executor action
FLOW_END_ATTEMPT = 2  # attempt over: done, fail, stuck, or error


class RunOutcome:
    """Typed terminal record for one run.

    The controller builds exactly one of these at its terminal site; the
    JSONL ``run_end`` event and the structured result's ``status`` and
    ``outcome`` fields are projections of it, so the terminal claim cannot
    diverge between the log and the returned record. ``validation`` is the
    final-validation disposition — ``passed``, ``deterministic``,
    ``unavailable``, ``failed``, or ``skipped`` — kept separate from
    ``status`` because completion and verification are distinct claims.
    """

    def __init__(
        self,
        status: str,
        validation: str,
        replans: int,
        wall_s: float,
        completed_tasks: int,
        selected_steps: int,
        executed_steps: int,
        skipped_steps: int,
        errors: list[JSONValue],
    ) -> None:
        self.status = status  # "complete" | "complete_unverified" | "exhausted"
        self.validation = validation
        self.replans = replans
        self.wall_s = wall_s
        self.completed_tasks = completed_tasks
        self.selected_steps = selected_steps
        self.executed_steps = executed_steps
        self.skipped_steps = skipped_steps
        self.errors = errors

    def _steps(self) -> dict[str, JSONValue]:
        steps: dict[str, JSONValue] = {
            "selected": self.selected_steps,
            "executed": self.executed_steps,
            "skipped": self.skipped_steps,
        }
        return steps

    def run_end_event(self) -> dict[str, JSONValue]:
        """The ``run_end`` JSONL event shape for this outcome."""
        event: dict[str, JSONValue] = {
            "event": "run_end",
            "status": self.status,
            "replans": self.replans,
            "wall_s": self.wall_s,
        }
        if self.status == "exhausted":
            errors: list[JSONValue] = []
            for error in self.errors:
                errors.append(error)
            event["errors"] = errors
        else:
            event["completed_tasks"] = self.completed_tasks
        event["steps"] = self._steps()
        return event

    def describe(self) -> dict[str, JSONValue]:
        """JSON-ready terminal record for the structured run result."""
        record: dict[str, JSONValue] = {
            "status": self.status,
            "validation": self.validation,
            "replans": self.replans,
            "wall_s": self.wall_s,
            "completed_tasks": self.completed_tasks,
            "steps": self._steps(),
        }
        return record


class IncompleteWrite:
    """One unresolved truncated write: its position and recorded step."""

    def __init__(self, index: int, step: dict[str, JSONValue]) -> None:
        self.index = index
        self.step = step


def _unresolved_incomplete_writes(
    steps: list[JSONValue], working_dir: str | None = None
) -> dict[str, IncompleteWrite]:
    """Latest unresolved truncated writes, keyed by normalized target.

    Only a later complete write/append to the same target resolves truncation;
    an edit cannot reconstruct the suffix that never arrived.
    """
    unresolved: dict[str, IncompleteWrite] = {}
    idx = 0
    for item in steps:
        step = as_dict(item)
        if step.get("action") == "write" and get_flag(step, "ok"):
            target = _mutation_target_key(step, working_dir)
            if target is not None:
                if get_flag(step, "_truncated_write"):
                    unresolved[target] = IncompleteWrite(idx, step)
                elif target in unresolved:
                    unresolved.pop(target)
        idx += 1
    return unresolved


def _latest_incomplete(unresolved: dict[str, IncompleteWrite]) -> tuple[str, IncompleteWrite]:
    """The newest unresolved write (``max`` by step position)."""
    best_target = ""
    best: IncompleteWrite | None = None
    for target, record in unresolved.items():
        if best is None or record.index > best.index:
            best_target = target
            best = record
    if best is None:
        raise ValueError("no unresolved write")
    return best_target, best


def _incomplete_step_hint(target: str, step: dict[str, JSONValue]) -> tuple[str, str]:
    """Return the display name and actionable target for a partial write."""
    arg = get_str(step, "arg")
    name = path_name(arg) if arg else "file"
    recovery = step.get("_recovery_arg")
    if isinstance(recovery, str) and recovery.strip():
        return name, recovery
    if target.strip():
        return name, target
    return name, arg if arg.strip() else name


class Blocker:
    """An open incomplete-write obligation: name, target and recovery mode."""

    def __init__(self, name: str, recovery_arg: str, append_allowed: bool) -> None:
        self.name = name
        self.recovery_arg = recovery_arg
        self.append_allowed = append_allowed


def _pending_empty_hint(target: str, info: JSONValue) -> Blocker:
    """Return the display name, actionable target, and recovery mode."""
    raw_name = ""
    append_allowed = False
    recovery_arg: JSONValue = None
    if isinstance(info, dict):
        raw_name = get_str(info, "name")
        append_allowed = get_flag(info, "append_allowed")
        recovery_arg = info.get("recovery_arg")
    elif isinstance(info, str):
        raw_name = info
    name = path_name(raw_name) if raw_name else "file"
    if isinstance(recovery_arg, str) and recovery_arg.strip():
        return Blocker(name, recovery_arg, append_allowed)
    if target.strip():
        return Blocker(name, target, append_allowed)
    return Blocker(name, raw_name if raw_name.strip() else name, append_allowed)


def _append_allowed(info: JSONValue) -> bool:
    return isinstance(info, dict) and get_flag(info, "append_allowed")


def _restrictive_pending_empty(pending: dict[str, JSONValue]) -> str | None:
    """Return the first pending obligation that forbids append recovery."""
    for target, info in pending.items():
        if not _append_allowed(info):
            return target
    return None


def _next_pending_empty(pending: dict[str, JSONValue]) -> str:
    """Choose an actionable obligation, with restrictive overwrites first."""
    restrictive = _restrictive_pending_empty(pending)
    if restrictive is not None:
        return restrictive
    for target in pending:
        return target
    raise ValueError("no pending obligation")


def _incomplete_write_visibility(
    all_steps: list[JSONValue], pending: dict[str, JSONValue]
) -> dict[str, JSONValue] | None:
    """Run-scoped incomplete artifact state for either replanner."""
    restrictive = _restrictive_pending_empty(pending)
    if restrictive is not None:
        hint = _pending_empty_hint(restrictive, pending[restrictive])
        blocked: dict[str, JSONValue] = {
            "incomplete_write": hint.name,
            "incomplete_write_target": hint.recovery_arg,
            "incomplete_write_append_allowed": False,
        }
        return blocked

    unresolved = _unresolved_incomplete_writes(all_steps)
    if unresolved:
        target, latest = _latest_incomplete(unresolved)
        name, recovery_arg = _incomplete_step_hint(target, latest.step)
        partial: dict[str, JSONValue] = {
            "incomplete_write": name,
            "incomplete_write_target": recovery_arg,
            "incomplete_write_append_allowed": True,
        }
        return partial

    if pending:
        # A restrictive overwrite can block recovery of an older permissive
        # append obligation. Surface it first so following the hint always
        # makes progress; all completion paths use this same selection.
        chosen = _next_pending_empty(pending)
        hint = _pending_empty_hint(chosen, pending[chosen])
        waiting: dict[str, JSONValue] = {
            "incomplete_write": hint.name,
            "incomplete_write_target": hint.recovery_arg,
            "incomplete_write_append_allowed": hint.append_allowed,
        }
        return waiting
    return None


def _progress_completion_blocker(progress: RunProgress, working_dir: str) -> Blocker | None:
    """Single finish-eligibility gate for incomplete-write obligations.

    Both completion sites — the executor's ``done`` claim and post-task
    acceptance — must refuse while any truncated or zero-byte write obligation
    is unresolved, and must steer recovery at the same target the replanner
    visibility reports. Selection order matches
    ``_incomplete_write_visibility``: a restrictive pending overwrite first,
    then the newest unresolved truncated write, then any remaining pending
    obligation.
    """
    unresolved = _unresolved_incomplete_writes(progress.optional_all_steps(), working_dir)
    pending = progress.optional_pending_empty_writes()
    if not unresolved and not pending:
        return None
    restrictive = _restrictive_pending_empty(pending)
    if restrictive is not None:
        return _pending_empty_hint(restrictive, pending[restrictive])
    if unresolved:
        target, latest = _latest_incomplete(unresolved)
        name, recovery_arg = _incomplete_step_hint(target, latest.step)
        return Blocker(name, recovery_arg, True)
    chosen = _next_pending_empty(pending)
    return _pending_empty_hint(chosen, pending[chosen])


def _pending_append_targets(info: JSONValue) -> list[str]:
    """Normalized referent guards from current and legacy pending records."""
    targets: list[str] = []
    if not isinstance(info, dict):
        return targets
    plural = info.get("append_targets")
    if isinstance(plural, list):
        for target in plural:
            if isinstance(target, str) and target.strip() and target not in targets:
                targets.append(target)
    legacy = info.get("append_target")
    if isinstance(legacy, str) and legacy.strip() and legacy not in targets:
        targets.append(legacy)
    return targets


def _append_blocked_by_pending(
    pending: dict[str, JSONValue], logical_target: str | None, operation_target: str | None
) -> bool:
    """True when an append must wait for a pending zero-byte overwrite.

    A pending overwrite is tied to the logical pathname and also blocks
    physical aliases. A permissive append obligation follows only the referent
    observed when it was created, so retargeting cannot satisfy it. Multiple
    aliases can carry different obligations for one referent; a pending
    overwrite always wins over a permissive append.
    """
    matched = False
    all_allowed = True
    for key, info in pending.items():
        allowed = _append_allowed(info)
        same_operation = operation_target is not None and operation_target in (
            _pending_append_targets(info)
        )
        if same_operation or (not allowed and key == logical_target):
            matched = True
            if not allowed:
                all_allowed = False
    return matched and not all_allowed


def _clear_pending_empty_writes(
    pending: dict[str, JSONValue],
    logical_target: str | None,
    operation_target: str | None,
    is_append: bool,
) -> None:
    """Clear zero-byte obligations satisfied by a successful write."""
    keys: list[str] = []
    if not is_append and logical_target is not None:
        keys.append(logical_target)
    if operation_target is not None:
        for key, info in pending.items():
            if _append_allowed(info) and operation_target in _pending_append_targets(info):
                if key not in keys:
                    keys.append(key)
    for key in keys:
        if key in pending:
            pending.pop(key)


def _write_visibility_flag(task_steps: list[JSONValue]) -> dict[str, JSONValue] | None:
    """Replanner visibility for a failed write-shaped task.

    Returns {"no_write_executed": True} when the task never landed a write,
    {"incomplete_write": <basename>} while any target has an unresolved
    truncated partial write, and {"unvalidated_write": <basename>} when it
    wrote but never verified after the last successful write, or None.
    """
    last_mutation = -1
    idx = 0
    for item in task_steps:
        step = as_dict(item)
        if get_str(step, "action") in ("write", "edit") and get_flag(step, "ok"):
            last_mutation = idx
        idx += 1
    if last_mutation < 0:
        none_written: dict[str, JSONValue] = {"no_write_executed": True}
        return none_written
    unresolved = _unresolved_incomplete_writes(task_steps)
    if unresolved:
        # Incomplete state wins over unrelated later mutations and shells.
        _target, latest = _latest_incomplete(unresolved)
        arg = get_str(latest.step, "arg")
        incomplete: dict[str, JSONValue] = {"incomplete_write": path_name(arg) if arg else True}
        return incomplete
    arg = get_str(as_dict(task_steps[last_mutation]), "arg")
    for item in task_steps[last_mutation + 1 :]:
        step = as_dict(item)
        if step.get("action") == "shell" and get_flag(step, "ok"):
            return None
    unvalidated: dict[str, JSONValue] = {"unvalidated_write": path_name(arg) if arg else True}
    return unvalidated


def _read_continuation_hint(continuation: JSONValue) -> str:
    """Render an action-ready continuation for the executor prompt."""
    if isinstance(continuation, dict):
        return (
            f"cursor={get_int(continuation, 'cursor')}, "
            f"limit={get_int(continuation, 'limit')}, "
            f"sha256={get_str(continuation, 'sha256')}"
        )
    return f"offset={continuation}"


def _progress_should_validate(
    replan: int,
    history: list[JSONValue],
    progress: RunProgress,
    user_prompt: str,
    final_validate: str,
) -> bool:
    """Decide whether to run final validation.

    ``final_validate`` is the run's resolved mode: "0" never validates,
    "always" always does, and auto triggers on complexity/risk signals."""
    mode = final_validate
    if mode == "0":
        return False
    if mode == "always":
        return True
    if replan > 0:
        return True
    total_steps = 0
    for item in history:
        event = as_dict(item)
        if event.get("event") == "step":
            total_steps += 1
            result = event.get("result")
            # Any failed step in history
            if isinstance(result, dict) and "ok" in result and not truthy(result["ok"]):
                return True
    if len(progress.optional_completed_tasks()) >= 3:
        return True
    if total_steps >= 5:
        return True
    if _VALIDATE_KEYWORDS.search(user_prompt):
        return True
    return False


def _has_new_validation_evidence(state: dict[str, JSONValue]) -> bool:
    start = get_int(state, "validated_step_count", 0)
    steps = state.get("all_steps")
    if not isinstance(steps, list):
        return False
    for item in steps[start:]:
        step = as_dict(item)
        if get_str(step, "action") in ("write", "edit", "shell") and get_flag(step, "ok"):
            return True
    return False


def _optional_text(value: str | None) -> str:
    """How an f-string renders an optional string."""
    return "None" if value is None else value


class PolicyServices:
    """Live run state and recording access shared by the policies."""

    def __init__(
        self,
        run_state: RunState,
        working_dir: str,
        emit: Callable[[str], None],
        max_steps: int,
        observe_tail_reserve: int,
    ) -> None:
        self.run_state = run_state
        self.working_dir = working_dir
        self.emit = emit
        self.max_steps = max_steps
        self.observe_tail_reserve = observe_tail_reserve

    def progress(self) -> RunProgress:
        return self.run_state.progress()


class StepPolicy:
    """Pluggable step/completion-pressure policy for one run.

    The policy owns how the controller pressures the model toward progress
    and when it may accept ``done`` beyond the shared invariants: observation
    discipline, rewrite/verification discipline, and the executor prompt
    pressure signals. Everything else stays controller-owned and identical
    across arms — duplicate/stuck loop protection, incomplete-write
    obligations and the completion blocker, recording and counters, typed
    errors, and validation. Policies are constructed once per run and may
    keep run-scoped state.
    """

    name = "base"

    def __init__(self, services: PolicyServices) -> None:
        self.services = services
        self.needs_verification = False
        self.unverified_target: str | None = None

    def write_pressure(self, attempt: TaskAttemptState) -> bool:
        """True when the executor prompt must demand a committing action."""
        return False

    def validate_pressure(self, attempt: TaskAttemptState) -> str | None:
        """Basename the executor prompt must steer to verifying, or None."""
        return None

    def guard_done(self, ctx: StepContext, attempt: TaskAttemptState) -> int:
        """Extra policy conditions on ``done`` after the shared blocker."""
        return FLOW_DISPATCH

    def allows_deterministic_completion(self) -> bool:
        """May a deterministic-repair receipt auto-complete a matching task?

        Automatic completion paths must pass the same policy discipline as a
        model ``done``; arms with an open verification obligation refuse."""
        return True

    def guard_action(self, ctx: StepContext, attempt: TaskAttemptState) -> int:
        """Pre-dispatch discipline for a non-control action."""
        return FLOW_DISPATCH

    def guard_duplicate(self, ctx: StepContext, attempt: TaskAttemptState) -> int:
        """Shared per-action-type loop protection: duplicates and stuck repeats
        are suppressed or reported, never converted into completion. One
        implementation serves every arm."""
        services = self.services
        progress = services.progress()
        recorder = services.run_state.recorder
        action = ctx.action
        act = ctx.act
        last_steps = progress.last_steps()
        if not last_steps:
            return FLOW_DISPATCH
        prev = as_dict(last_steps[-1])
        if prev["action"] != act:
            return FLOW_DISPATCH
        arg = action.text("arg")
        same_mutation_target = False
        if act in ("write", "edit"):
            current_target_step: dict[str, JSONValue] = {"arg": arg}
            if act == "write" and action.flag("append"):
                current_target_step["append"] = True
            current_target = _mutation_target_key(current_target_step, services.working_dir)
            same_mutation_target = (
                current_target is not None
                and _mutation_target_key(prev, services.working_dir) == current_target
            )
        if act in ("write", "edit") and same_mutation_target:
            # write: same content = duplicate; edit: same find+replace = duplicate
            is_dup = False
            content = action.fields.get("content", "")
            if act == "write" and action.flag("append"):
                # Chunked append is never a no-op — an identical consecutive
                # chunk is a stuck loop, not a duplicate.
                if get_flag(prev, "_append") and prev.get("_content", "") == content:
                    services.emit(
                        f"  [{ctx.step + 1}] auto-fail (same chunk appended twice to {arg[:40]})"
                    )
                    progress.add_error(f"[stuck_loop] write {arg[:60]}: same chunk appended twice")
                    recorder.skip(ctx.task_index, ctx.step, act, action, "stuck_append")
                    return FLOW_END_ATTEMPT
            elif (
                act == "write"
                and not ctx.truncated_write
                and get_flag(prev, "ok")
                and not get_flag(prev, "_truncated_write")
                and not get_flag(prev, "_append")
                and prev.get("_content", "") == content
            ):
                is_dup = True
            elif (
                act == "edit"
                and get_flag(prev, "ok")
                and prev.get("_find", "") == action.text("find")
                and prev.get("_replace", "") == action.text("replace")
            ):
                is_dup = True
            # Consecutive identical failed edit → stuck; bail to replan
            elif (
                act == "edit"
                and not get_flag(prev, "ok")
                and prev.get("_find", "") == action.text("find")
            ):
                services.emit(
                    f"  [{ctx.step + 1}] auto-fail (same edit failed twice on {arg[:40]})"
                )
                progress.add_error(f"[stuck_loop] edit {arg[:60]}: same find string failed twice")
                recorder.skip(ctx.task_index, ctx.step, act, action, "stuck_edit")
                return FLOW_END_ATTEMPT
            if is_dup:
                attempt.dup_skip_count += 1
                services.emit(f"  [{ctx.step + 1}] skip (duplicate {act}, same content)")
                recorder.skip(ctx.task_index, ctx.step, act, action, f"duplicate_{act}")
                if get_flag(prev, "_truncated_write"):
                    dup_msg = (
                        "File is incomplete — the earlier write was truncated. "
                        "Continue with append:true for the rest."
                    )
                else:
                    dup_msg = "Already done — file unchanged. Move to next action or emit done."
                entry: dict[str, JSONValue] = {
                    "action": act,
                    "arg": arg,
                    "ok": True,
                    "output": dup_msg,
                }
                # Preserve match metadata so guard still detects duplicates on subsequent turns
                if act == "write":
                    entry["_content"] = content
                    if get_flag(prev, "_truncated_write"):
                        entry["_truncated_write"] = True
                elif act == "edit":
                    entry["_find"] = action.text("find")
                    entry["_replace"] = action.text("replace")
                recorder.note(entry)
                # Defer thinking escalation: first duplicate skip gets a
                # corrective observation only; escalate on 2+ consecutive skips.
                if attempt.dup_skip_count >= 2:
                    attempt.use_think = True
                    attempt.reasoning_trigger = "duplicate_action"
                return FLOW_NEXT_STEP
        elif act == "shell" and prev.get("arg", "") == arg:
            # The sliding window carries prior-task context, not proof that
            # this attempt executed its check. Give each new task/attempt a
            # fresh execution after either success or failure; retain
            # same-attempt guards and timeout bumps, including deterministic
            # retries.
            ran_here = False
            for item in attempt.steps:
                step = as_dict(item)
                if step.get("action") == "shell" and step.get("arg", "") == arg:
                    ran_here = True
            if not ran_here:
                return FLOW_DISPATCH
            if get_flag(prev, "ok"):
                # Repetition is never completion evidence: the duplicate is
                # suppressed as a no-op once, and repeating it again is a
                # stuck loop for the replanner — task acceptance still
                # requires an explicit done.
                attempt.dup_skip_count += 1
                if attempt.dup_skip_count >= 2:
                    services.emit(
                        f"  [{ctx.step + 1}] auto-fail (same successful shell repeated on {arg[:40]})"
                    )
                    progress.add_error(
                        f"[stuck_loop] shell {arg[:60]}: same successful command repeated"
                    )
                    recorder.skip(ctx.task_index, ctx.step, act, action, "stuck_shell_repeat")
                    return FLOW_END_ATTEMPT
                services.emit(f"  [{ctx.step + 1}] skip (duplicate successful shell)")
                recorder.skip(ctx.task_index, ctx.step, act, action, "duplicate_shell")
                repeated: dict[str, JSONValue] = {
                    "action": act,
                    "arg": arg,
                    "ok": True,
                    "output": (
                        "Already ran successfully — use the earlier output. "
                        "Take the next action, or emit done/fail."
                    ),
                }
                recorder.note(repeated)
                return FLOW_NEXT_STEP
            elif prev.get("error_type") == "timeout":
                # Bump timeout for retry: read actual timeout from previous step,
                # not from fresh action (which won't have prior bumps)
                prev_timeout = get_int(prev, "_timeout", _get_shell_timeout(arg))
                bumped = max(SHELL_TIMEOUT_LONG, prev_timeout * 2)
                new_timeout = min(bumped, SHELL_TIMEOUT_MAX)
                ctx.action = action.with_update("timeout", new_timeout)
                services.emit(f"  [{ctx.step + 1}] retrying after timeout ({new_timeout}s)")
            else:
                services.emit(f"  [{ctx.step + 1}] auto-fail (same shell failed twice)")
                progress.add_error(f"Stuck: {act} {arg[:60]} failed twice")
                recorder.skip(ctx.task_index, ctx.step, act, action, "stuck_shell")
                return FLOW_END_ATTEMPT
        elif act == "read" and prev.get("arg", "") == arg:
            # Range-aware: new line windows and exact cursor continuations
            # are legitimate navigation.
            stored_key = prev.get("_read_key")
            prev_key: JSONValue = stored_key if truthy(stored_key) else _read_key(prev)
            cur_key: JSONValue = _read_key(action.fields)
            if prev_key != cur_key:
                pass  # different range — execute normally
            elif get_flag(prev, "ok"):
                attempt.dup_skip_count += 1
                if attempt.dup_skip_count >= 2:
                    services.emit(
                        f"  [{ctx.step + 1}] auto-fail (same read repeated on {arg[:40]})"
                    )
                    progress.add_error(f"[stuck_loop] read {arg[:60]}: same file read repeatedly")
                    recorder.skip(ctx.task_index, ctx.step, act, action, "stuck_read")
                    return FLOW_END_ATTEMPT
                services.emit(f"  [{ctx.step + 1}] skip (duplicate read)")
                recorder.skip(ctx.task_index, ctx.step, act, action, "duplicate_read")
                cont = prev.get("_continuation")
                if truthy(cont):
                    obs = (
                        "Already read this range. Continue with "
                        f"{_read_continuation_hint(cont)}; "
                        "or search, edit, done, or fail."
                    )
                else:
                    obs = "Already read. Use previous content; edit, write, shell, done, or fail."
                reread: dict[str, JSONValue] = {
                    "action": "read",
                    "arg": arg,
                    "ok": True,
                    "output": obs,
                    "_read_key": cur_key,
                }
                if truthy(cont):
                    reread["_continuation"] = cont
                recorder.note(reread)
                return FLOW_NEXT_STEP
            else:
                services.emit(f"  [{ctx.step + 1}] auto-fail (same read failed twice)")
                progress.add_error(f"[stuck_loop] read {arg[:60]} failed twice")
                recorder.skip(ctx.task_index, ctx.step, act, action, "stuck_read_failed")
                return FLOW_END_ATTEMPT
        return FLOW_DISPATCH

    def note_result(
        self, ctx: StepContext, attempt: TaskAttemptState, result: ActionResult
    ) -> None:
        """Observe one dispatched action's result for policy state."""

    def note_deterministic_repair(self, target: str | None) -> None:
        """Observe a dispatched compile-repair mutation."""

    def note_deterministic_retry(self, result: ActionResult) -> None:
        """Observe the scaffold shell retry after a repair."""


class HeuristicStepPolicy(StepPolicy):
    """The guard/counter baseline.

    Keyword write-shaping plus counters: write pressure after observation
    spending, an observation tail reserve, and same-target rewrite damping
    with validate pressure.
    """

    name = "heuristic"

    def write_pressure(self, attempt: TaskAttemptState) -> bool:
        return attempt.write_pressure()

    def validate_pressure(self, attempt: TaskAttemptState) -> str | None:
        return self.services.run_state.validate_pressure_target()

    def guard_action(self, ctx: StepContext, attempt: TaskAttemptState) -> int:
        flow = self._observe_tail_guard(ctx, attempt)
        if flow == FLOW_DISPATCH:
            flow = self._rewrite_loop_guard(ctx, attempt)
        return flow

    def _observe_tail_guard(self, ctx: StepContext, attempt: TaskAttemptState) -> int:
        """Reserve the final steps of a write-shaped task for commitment."""
        services = self.services
        # Write-forcing tail reserve: on a write-shaped task the final steps
        # are reserved for committing actions.
        if not (
            ctx.act in OBSERVE_ACTIONS
            and attempt.wants_write
            and attempt.commit_executed == 0
            and services.max_steps - ctx.step <= services.observe_tail_reserve
        ):
            return FLOW_DISPATCH
        recorder = services.run_state.recorder
        arg = ctx.action.text("arg")
        attempt.observe_blocked += 1
        if attempt.observe_blocked >= 2:
            services.emit(
                f"  [{ctx.step + 1}] auto-fail (observation steps exhausted without a write)"
            )
            services.progress().add_error(
                f"[stuck_loop] {ctx.act} {arg[:60]}: observation steps exhausted without a write"
            )
            recorder.skip(ctx.task_index, ctx.step, ctx.act, ctx.action, "observe_tail_exhausted")
            return FLOW_END_ATTEMPT
        services.emit(
            f"  [{ctx.step + 1}] skip ({ctx.act} blocked: remaining steps reserved for write)"
        )
        recorder.skip(ctx.task_index, ctx.step, ctx.act, ctx.action, "observe_tail_reserved")
        note: dict[str, JSONValue] = {
            "action": ctx.act,
            "arg": arg,
            "ok": True,
            "output": "Observation budget exhausted. Next action MUST be write, edit, or shell — or fail with reason.",
        }
        recorder.note(note)
        return FLOW_NEXT_STEP

    def _rewrite_loop_guard(self, ctx: StepContext, attempt: TaskAttemptState) -> int:
        """Skip a same-target full rewrite once the streak is armed."""
        services = self.services
        run_state = services.run_state
        # Rewrite damping: after rewrite_skip_writes successful full writes of
        # the same target with no intervening successful shell/edit, further
        # full rewrites are skipped — verify, edit, or finish instead.
        if not (
            ctx.act == "write"
            and not ctx.action.flag("append")
            and not ctx.truncated_write
            and run_state.rewrite_skip_armed(ctx.logical_write_target)
        ):
            return FLOW_DISPATCH
        arg = ctx.action.text("arg")
        attempt.dup_skip_count += 1
        services.emit(
            f"  [{ctx.step + 1}] skip (rewrite loop: "
            f"{arg[:40]} already written "
            f"{run_state.consecutive_target_writes}x)"
        )
        run_state.recorder.skip(ctx.task_index, ctx.step, ctx.act, ctx.action, "rewrite_loop")
        note: dict[str, JSONValue] = {
            "action": ctx.act,
            "arg": arg,
            "ok": True,
            "output": (
                f"Already written {run_state.consecutive_target_writes} times. "
                "Do NOT write it again — verify with shell, make a "
                "targeted edit, or emit done."
            ),
        }
        run_state.recorder.note(note)
        return FLOW_NEXT_STEP

    def note_result(
        self, ctx: StepContext, attempt: TaskAttemptState, result: ActionResult
    ) -> None:
        run_state = self.services.run_state
        if ctx.act == "write" and result.ok:
            if ctx.truncated_write:
                # A partial (truncated) write is not a completed rewrite: the
                # file is incomplete, and the recovery path may legitimately
                # append to it or restart the write. Reset for truncated
                # append chunks too; otherwise an armed streak can block the
                # clean restart.
                run_state.disarm_rewrite_damping()
            elif not ctx.action.flag("append"):
                run_state.note_successful_full_write(ctx.logical_write_target)
        elif ctx.act in ("shell", "edit") and result.ok:
            # Verification or a targeted fix breaks the rewrite streak;
            # observations do not.
            run_state.break_rewrite_streak()

    def note_deterministic_repair(self, target: str | None) -> None:
        # The deterministic source fix is a successful targeted repair, so
        # it breaks an armed rewrite streak just like a model-selected edit.
        self.services.run_state.break_rewrite_streak()


class LifecycleStepPolicy(StepPolicy):
    """Explicit inspect → modify → verify → finish arm.

    Replaces the tail reserve and the rewrite counters with two phase
    invariants, run-scoped so a task-local replan cannot silently move the
    lifecycle backward:

    - a successful mutation marks its target ``needs_verification``; only a
      later successful shell check clears it (a failed check does not);
    - while a target needs verification, a same-target full rewrite is
      steered to verification, and ``done`` is refused with a corrective
      note — repetition or observation never moves the lifecycle forward.

    Any successful shell counts as verification evidence, so a mutating shell
    is not itself tracked as a mutation; the final validator remains the
    independent check. This arm is an alternative to measure, not an assumed
    improvement.
    """

    name = "lifecycle"

    def write_pressure(self, attempt: TaskAttemptState) -> bool:
        return attempt.write_pressure()

    def _target_has_open_obligation(self, target: str | None) -> bool:
        """True while incomplete-write recovery legitimately rewrites it."""
        if target is None:
            return False
        progress = self.services.progress()
        if target in progress.optional_pending_empty_writes():
            return True
        return target in _unresolved_incomplete_writes(
            progress.optional_all_steps(), self.services.working_dir
        )

    def _unverified_name(self) -> str:
        target = self.unverified_target
        return path_name(target if target else "file")

    def guard_done(self, ctx: StepContext, attempt: TaskAttemptState) -> int:
        if not self.needs_verification:
            return FLOW_DISPATCH
        services = self.services
        name = self._unverified_name()
        services.emit(f"  [{ctx.step + 1}] skip (done before verifying {name})")
        recorder = services.run_state.recorder
        recorder.skip(ctx.task_index, ctx.step, ctx.act, ctx.action, "lifecycle_unverified_done")
        note: dict[str, JSONValue] = {
            "action": "done",
            "arg": "",
            "ok": True,
            "output": (
                f"Cannot finish: {name} was modified but never verified. "
                "Run a shell command that checks it, or fail with a reason."
            ),
        }
        recorder.note(note)
        return FLOW_NEXT_STEP

    def guard_action(self, ctx: StepContext, attempt: TaskAttemptState) -> int:
        if not (
            ctx.act == "write"
            and not ctx.action.flag("append")
            and not ctx.truncated_write
            and self.needs_verification
            and ctx.logical_write_target == self.unverified_target
            and not self._target_has_open_obligation(ctx.logical_write_target)
        ):
            return FLOW_DISPATCH
        services = self.services
        name = self._unverified_name()
        attempt.dup_skip_count += 1
        services.emit(f"  [{ctx.step + 1}] skip (rewrite of unverified {name})")
        recorder = services.run_state.recorder
        recorder.skip(
            ctx.task_index, ctx.step, ctx.act, ctx.action, "lifecycle_verify_before_rewrite"
        )
        note: dict[str, JSONValue] = {
            "action": ctx.act,
            "arg": ctx.action.text("arg"),
            "ok": True,
            "output": (
                f"{name} is already written but unverified. Do NOT rewrite "
                "it — verify it with a shell check or make a targeted edit."
            ),
        }
        recorder.note(note)
        return FLOW_NEXT_STEP

    def note_result(
        self, ctx: StepContext, attempt: TaskAttemptState, result: ActionResult
    ) -> None:
        if not result.ok:
            # Failures never move the lifecycle: a failed check does not
            # verify, and a failed mutation creates nothing to verify.
            return
        if ctx.act in ("write", "edit"):
            self.needs_verification = True
            if ctx.act == "write":
                self.unverified_target = ctx.logical_write_target
            else:
                edited: dict[str, JSONValue] = {"arg": ctx.action.text("arg")}
                self.unverified_target = _mutation_target_key(edited, self.services.working_dir)
        elif ctx.act == "shell":
            self.needs_verification = False
            self.unverified_target = None

    def note_deterministic_repair(self, target: str | None) -> None:
        self.needs_verification = True
        self.unverified_target = target

    def note_deterministic_retry(self, result: ActionResult) -> None:
        if result.ok:
            self.needs_verification = False
            self.unverified_target = None

    def allows_deterministic_completion(self) -> bool:
        # A repaired-but-unverified target gates the auto-done exactly like
        # a model done: verify first.
        return not self.needs_verification


STEP_POLICY_NAMES = ("heuristic", "lifecycle")


def make_step_policy(name: str, services: PolicyServices) -> StepPolicy:
    if name == "lifecycle":
        return LifecycleStepPolicy(services)
    return HeuristicStepPolicy(services)


class WriteObligations:
    """Typed owner of incomplete-write obligations for one run.

    Truncation classification, zero-byte obligation records, append-safety
    and recovery-order decisions, the completion refusal, resume anchors,
    and obligation clearing all live here — a shared invariant every policy
    arm runs under. The ``pending_empty_writes`` dictionary stays projected
    into run state because the structured result and replanner visibility
    read it there.
    """

    def __init__(self, services: PolicyServices) -> None:
        self.services = services

    def completion_blocker(self) -> Blocker | None:
        """The most actionable open obligation, or None."""
        return _progress_completion_blocker(self.services.progress(), self.services.working_dir)

    def refuse_done(self, ctx: StepContext) -> int:
        """Skip a ``done`` claim while any obligation is unresolved."""
        services = self.services
        blocker = self.completion_blocker()
        if blocker is None:
            return FLOW_DISPATCH
        if blocker.append_allowed:
            recovery = (
                "Retry that exact target with append:true if it "
                "still identifies the intended file, or restart "
                "it with a complete append:false write."
            )
        else:
            recovery = (
                "Resend a shorter write to that exact target with "
                "append:false before using append:true."
            )
        services.emit(f"  [{ctx.step + 1}] skip (done with incomplete write: {blocker.name})")
        recorder = services.run_state.recorder
        recorder.skip(ctx.task_index, ctx.step, ctx.act, ctx.action, "incomplete_write_done")
        note: dict[str, JSONValue] = {
            "action": "done",
            "arg": "",
            "ok": True,
            "output": (
                f"Cannot finish: {blocker.name} is incomplete at {blocker.recovery_arg}. {recovery}"
            ),
        }
        recorder.note(note)
        return FLOW_NEXT_STEP

    def prepare(self, ctx: StepContext) -> int:
        """Classify write truncation and enforce zero-byte recovery order."""
        services = self.services
        action = ctx.action
        act = ctx.act
        arg = action.text("arg")
        is_append = action.flag("append")
        recorder = services.run_state.recorder
        # Transport truncation: keep the complete lines that arrived and steer
        # the model to finish the file with chunked append instead of failing
        # the step.
        ctx.truncated_write = act == "write" and ctx.transport.content_truncated
        ctx.logical_write_target = None
        ctx.operation_write_target = None
        if act == "write":
            logical: dict[str, JSONValue] = {"arg": arg}
            ctx.logical_write_target = _mutation_target_key(logical, services.working_dir)
            operation: dict[str, JSONValue] = {"arg": arg, "append": is_append}
            ctx.operation_write_target = _mutation_target_key(operation, services.working_dir)
        pending = services.progress().pending_empty_writes()
        if (
            act == "write"
            and is_append
            and _append_blocked_by_pending(
                pending, ctx.logical_write_target, ctx.operation_write_target
            )
        ):
            services.emit(f"  [{ctx.step + 1}] skip (append before first replacement chunk landed)")
            recorder.skip(ctx.task_index, ctx.step, act, action, "append_after_empty_overwrite")
            blocked: dict[str, JSONValue] = {
                "action": act,
                "arg": arg,
                "ok": True,
                "output": (
                    "The replacement's first chunk wrote no bytes. "
                    "Resend a shorter write with append:false before "
                    "using append:true."
                ),
            }
            recorder.note(blocked)
            return FLOW_NEXT_STEP
        if ctx.truncated_write:
            kept = action.text("content")
            kept = kept[: kept.rfind("\n") + 1]
            if not kept:
                services.emit(f"  [{ctx.step + 1}] skip (write truncated before a complete line)")
                recorder.skip(ctx.task_index, ctx.step, act, action, "truncated_write_empty")
                # The recovery instruction asks for a clean resend; disarm
                # rewrite damping before that resend even though this empty
                # partial attempt wrote no bytes.
                services.run_state.disarm_rewrite_damping()
                # Empty append attempts are obligations on the referent
                # observed at dispatch time. Key them by that operation
                # target so retargeting a leaf symlink cannot overwrite an
                # older obligation.
                pending_target = (
                    ctx.operation_write_target if is_append else ctx.logical_write_target
                )
                recovery_arg = arg if arg else "file"
                if pending_target is not None:
                    existing = pending.get(pending_target)
                    append_allowed = is_append
                    if isinstance(existing, dict):
                        append_allowed = get_flag(existing, "append_allowed") and append_allowed
                    append_step: dict[str, JSONValue] = {"arg": arg, "append": True}
                    append_target = _mutation_target_key(append_step, services.working_dir)
                    append_targets = _pending_append_targets(existing)
                    if append_target is not None and append_target not in append_targets:
                        append_targets.append(append_target)
                    recovery_target = _target_recovery_arg(pending_target, services.working_dir)
                    recovery_arg = _optional_text(recovery_target)
                    services.progress().set_pending_write(
                        pending_target,
                        PendingWrite(
                            path_name(arg if arg else "file"),
                            append_allowed,
                            append_targets,
                            recovery_target,
                        ),
                    )
                # Nothing was written: the first dispatched chunk must stay a
                # non-append write (append would land on a stale existing
                # file), only later chunks may append.
                if is_append:
                    obs = (
                        "Append truncated before a complete line. "
                        "Resend a smaller append:true chunk at the "
                        f"exact target {recovery_arg}."
                    )
                else:
                    obs = (
                        "Write truncated before a complete line. Resend the "
                        f"write (no append) to the exact target {recovery_arg} "
                        "with a shorter first chunk, then continue with "
                        "append:true chunks."
                    )
                empty: dict[str, JSONValue] = {
                    "action": act,
                    "arg": arg,
                    "ok": True,
                    "output": obs,
                }
                recorder.note(empty)
                return FLOW_NEXT_STEP
            ctx.action = action.with_update("content", kept)
        return FLOW_DISPATCH

    def note_successful_write(self, ctx: StepContext, action: ActionEnvelope) -> None:
        """A complete write clears the obligations it satisfies."""
        _clear_pending_empty_writes(
            self.services.progress().pending_empty_writes(),
            ctx.logical_write_target,
            ctx.operation_write_target,
            action.flag("append"),
        )

    def append_resume_anchor(
        self, ctx: StepContext, action: ActionEnvelope, result: ActionResult
    ) -> None:
        """Suffix a truncated write's output with its exact resume point.

        The executor is stateless per step: without a resume anchor the
        model cannot know where the write stopped. The kept content is
        exactly what :meth:`prepare` trimmed to the last complete line."""
        kept = action.text("content")
        anchor = kept.splitlines()[-1][-80:]
        recovery_arg = _optional_text(
            _target_recovery_arg(ctx.operation_write_target, self.services.working_dir)
        )
        result.output += (
            f" (truncated after {kept.count(chr(10))} lines; "
            f"last written line: {anchor!r}; continue with "
            f"append:true at {recovery_arg} starting after "
            "that line)"
        )


class ValidationState:
    """Typed owner of run-scoped validation state.

    Projects through the structured state keys the result schema carries
    (``validated_once``, ``validation_attempts``,
    ``validation_recheck_needed``, ``validated_step_count``).
    """

    def __init__(self, data: dict[str, JSONValue]) -> None:
        self.data = data

    def attempts(self) -> int:
        return get_int(self.data, "validation_attempts", 0)

    def recheck_needed(self) -> bool:
        return get_flag(self.data, "validation_recheck_needed")

    def note_attempt(self) -> None:
        self.data["validated_once"] = True
        self.data["validation_attempts"] = self.attempts() + 1

    def mark_failed(self) -> None:
        """An explicit rejection blocks completion until new evidence."""
        self.data["validation_recheck_needed"] = True
        steps = self.data.get("all_steps")
        self.data["validated_step_count"] = len(steps) if isinstance(steps, list) else 0

    def clear_failure(self) -> None:
        self.data["validation_recheck_needed"] = False

    def has_new_evidence(self) -> bool:
        """New successful mutation or shell evidence since the failure."""
        return _has_new_validation_evidence(self.data)


class CompletionVerdict:
    """A final-validation verdict; ``deterministic`` marks the built-in check."""

    def __init__(self, valid: bool, reason: str, missing: list[str], deterministic: bool) -> None:
        self.valid = valid
        self.reason = reason
        self.missing = missing
        self.deterministic = deterministic


class CompletionContext:
    """Narrow terminal-policy services, separate from transport and setup.

    ``validate`` owns request configuration and returns a verdict or no
    verdict; the policy owns when to call it and how that result affects
    completion.
    """

    def __init__(
        self,
        run_state: RunState,
        user_prompt: str,
        working_dir: str,
        final_validate: str,
        max_replans: int,
        validate: Callable[[], CompletionVerdict | None],
        emit: Callable[[str], None],
        event: Callable[[dict[str, JSONValue]], None],
    ) -> None:
        self.run_state = run_state
        self.user_prompt = user_prompt
        self.working_dir = working_dir
        self.final_validate = final_validate
        self.max_replans = max_replans
        self.validate = validate
        self.emit = emit
        self.event = event


class CompletionPolicy:
    """Terminal policy for one run: validation gating, verdict handling, the
    evidence-gated recheck, and the typed terminal outcome for both completion
    and exhaustion. The controller sequences planning and attempts; this class
    decides how a run may end. No verdict is never a pass, an explicit
    rejection cannot be erased without new evidence, and exhaustion never
    reconciles to success."""

    def __init__(self, context: CompletionContext) -> None:
        self._context = context
        self.validation = ValidationState(context.run_state.data)

    def try_finish(self, replan: int) -> RunOutcome | None:
        """Validate an all-done pass; a :class:`RunOutcome` ends the run."""
        context = self._context
        run_state = context.run_state
        progress = run_state.progress()
        status = "complete"
        validation = "skipped"
        wants_validation = _progress_should_validate(
            replan, run_state.history, progress, context.user_prompt, context.final_validate
        )
        first_validation = self.validation.attempts() == 0
        recheck_validation = (
            self.validation.recheck_needed()
            and self.validation.attempts() < 2
            and self.validation.has_new_evidence()
        )
        if wants_validation and (first_validation or recheck_validation):
            self.validation.note_attempt()
            vresult = context.validate()
            if vresult is not None and not vresult.valid:
                reason = vresult.reason if vresult.reason else "validation failed"
                error_msg = f"[validation_failed] {reason}"
                if vresult.missing:
                    error_msg += f" missing: {', '.join(vresult.missing)}"
                progress.add_error(error_msg)
                self.validation.mark_failed()
                context.emit(f"  Validation failed: {reason}")
                failed: dict[str, JSONValue] = {
                    "event": "validation",
                    "valid": False,
                    "reason": reason,
                    "missing": str_items(vresult.missing),
                    "deterministic": vresult.deterministic,
                }
                context.event(failed)
                return None  # replan
            elif vresult is None and recheck_validation:
                # Once validation explicitly failed, an unavailable second
                # verdict cannot erase that known failure.
                context.emit("  Validation recheck produced no verdict; failure remains pending.")
                pending: dict[str, JSONValue] = {
                    "event": "validation",
                    "valid": None,
                    "reason": "recheck produced no verdict",
                    "deterministic": False,
                }
                context.event(pending)
            elif vresult is None:
                # An unavailable or malformed first verdict is not a pass: the
                # completed tasks stand, but the run is typed
                # ``complete_unverified`` instead of claiming "Validation
                # passed" from missing evidence.
                status = "complete_unverified"
                validation = "unavailable"
                context.emit("  Validation produced no verdict; completing unverified.")
                unavailable: dict[str, JSONValue] = {
                    "event": "validation",
                    "valid": None,
                    "reason": "validator unavailable",
                    "deterministic": False,
                }
                context.event(unavailable)
            else:
                validation = "deterministic" if vresult.deterministic else "passed"
                self.validation.clear_failure()
                context.emit("  Validation passed.")
                passed: dict[str, JSONValue] = {
                    "event": "validation",
                    "valid": True,
                    "deterministic": vresult.deterministic,
                }
                context.event(passed)
        if self.validation.recheck_needed():
            if self.validation.attempts() >= 2:
                reason = "validation remains failed after the maximum checks"
            else:
                reason = (
                    "completion after failed validation requires new write, edit, or shell evidence"
                )
            progress.add_error(f"[validation_failed] {reason}")
            context.emit(f"  Completion refused: {reason}")
            refused: dict[str, JSONValue] = {"event": "validation_pending", "reason": reason}
            context.event(refused)
            return None
        outcome = self._build_outcome(status, validation, replan)
        context.emit(f"All tasks complete. ({outcome.wall_s:.1f}s total)")
        context.emit(f"Output in: {context.working_dir}")
        return outcome

    def exhausted(self) -> RunOutcome:
        """Exhaustion is terminal: an exhausted budget never reconciles to
        ``complete`` from a "latest shell succeeded" heuristic."""
        context = self._context
        validation = "failed" if self.validation.recheck_needed() else "skipped"
        outcome = self._build_outcome("exhausted", validation, context.max_replans)
        context.emit(
            f"Exhausted {context.max_replans} replan attempts. ({outcome.wall_s:.1f}s total)"
        )
        context.emit(f"Errors: {context.run_state.progress().errors()}")
        context.emit(f"Output in: {context.working_dir}")
        return outcome

    def _build_outcome(self, status: str, validation: str, replans: int) -> RunOutcome:
        """Snapshot the terminal record from the run-scoped state."""
        run_state = self._context.run_state
        progress = run_state.progress()
        errors: list[JSONValue] = []
        if status == "exhausted":
            errors = progress.errors()[-5:]
        return RunOutcome(
            status,
            validation,
            replans,
            round(run_state.elapsed(), 2),
            len(progress.completed_tasks()),
            progress.selected_steps(),
            progress.executed_steps(),
            progress.skipped_steps(),
            errors,
        )
