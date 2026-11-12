"""Provider settings, response codecs and the LLM client (mirrors ``llm.py``).

Importing this module does not read the environment, load ``.env`` or call a
provider. The client takes explicit immutable settings, a transport function
and optional sinks. Executor actions arrive as native tool calls; planner,
task-replan and validation replies are plain JSON objects.
"""

from __future__ import annotations

import json
import os
import re
from typing import Callable

from native_actions import (
    ACTION_ORDER,
    ActionTransport,
    DecodedAction,
    parse_action_envelope,
)
from native_host import HttpReply
from native_json import JSONValue, as_dict, get_dict, get_str, truthy

REASONING_POLICIES = ("gated", "off")

_EFFORT_RANK = {"low": 0, "medium": 1, "high": 2}

LLM_TIMEOUT = 120  # seconds; covers slow first-token on local LLM
LLM_TIMEOUT_REPLAN = 180  # replans carry heavier state + thinking
MAX_LLM_RETRIES = 2

OPENROUTER_CHAT_API = "https://openrouter.ai/api/v1/chat/completions"
_OPENROUTER_DEFAULT_MODEL = "google/gemma-4-26b-a4b-it"

# Executor action transport: native tool calls only. Planner, task-replan and
# validation responses remain plain JSON because they are not actions.
ACTION_TRANSPORT = "tools"


def ignore_sleep(_seconds: float) -> None:
    """Backoff sleeper for transports without a real network."""


def never_truncated() -> bool:
    """The live decoder rejects cut-off arguments instead of salvaging them."""
    return False


def _parse_reasoning_effort(raw: str) -> str:
    effort = raw.strip().lower()
    if effort and effort not in _EFFORT_RANK:
        raise ValueError("OPENROUTER_REASONING_EFFORT must be low, medium, or high (or unset)")
    return effort


def py_str(value: JSONValue) -> str:
    """``str(value)`` as an f-string would render one decoded JSON value."""
    if isinstance(value, str):
        return value
    return str(value)


def json_type_name(value: JSONValue) -> str:
    """``type(value).__name__`` for one decoded JSON value."""
    if value is None:
        return "NoneType"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    return "dict"


class CapabilityProfile:
    """Model-facing context and output limits for one immutable run.

    Profiles make the model contract explicit and hashable instead of
    following the serving backend. ``context_window`` and ``server_slots``
    are optional declared deployment expectations; generic profiles do not
    invent server topology.
    """

    def __init__(
        self,
        name: str,
        step_tokens: int,
        step_write_tokens: int,
        planner_tokens: int = 768,
        task_replan_tokens: int = 96,
        validation_tokens: int = 768,
        reasoning_token_floors: tuple[int, int, int] = (1024, 1536, 2048),
        context_window: int | None = None,
        server_slots: int | None = None,
    ) -> None:
        if not name.strip():
            raise ValueError("capability profile name must be non-empty")
        if step_tokens < 1:
            raise ValueError("step_tokens must be a positive integer")
        if step_write_tokens < 1:
            raise ValueError("step_write_tokens must be a positive integer")
        if planner_tokens < 1:
            raise ValueError("planner_tokens must be a positive integer")
        if task_replan_tokens < 1:
            raise ValueError("task_replan_tokens must be a positive integer")
        if validation_tokens < 1:
            raise ValueError("validation_tokens must be a positive integer")
        if context_window is not None and context_window < 1:
            raise ValueError("context_window must be a positive integer or None")
        if server_slots is not None and server_slots < 1:
            raise ValueError("server_slots must be a positive integer or None")
        if (
            reasoning_token_floors[0] < 1
            or reasoning_token_floors[1] < 1
            or reasoning_token_floors[2] < 1
        ):
            raise ValueError("reasoning_token_floors must contain three positive integers")
        self.name = name
        self.step_tokens = step_tokens
        self.step_write_tokens = step_write_tokens
        self.planner_tokens = planner_tokens
        self.task_replan_tokens = task_replan_tokens
        self.validation_tokens = validation_tokens
        self.reasoning_token_floors = reasoning_token_floors
        self.context_window = context_window
        self.server_slots = server_slots

    def floors(self) -> dict[str, JSONValue]:
        table: dict[str, JSONValue] = {
            "low": self.reasoning_token_floors[0],
            "medium": self.reasoning_token_floors[1],
            "high": self.reasoning_token_floors[2],
        }
        return table

    def describe(self) -> dict[str, JSONValue]:
        record: dict[str, JSONValue] = {
            "name": self.name,
            "step_tokens": self.step_tokens,
            "step_write_tokens": self.step_write_tokens,
            "planner_max_tokens": self.planner_tokens,
            "task_replan_max_tokens": self.task_replan_tokens,
            "final_validation_max_tokens": self.validation_tokens,
            "reasoning_token_floors": self.floors(),
            "context_window": self.context_window,
            "server_slots": self.server_slots,
        }
        return record


_LEGACY_E4B_PROFILE = CapabilityProfile(
    "legacy-e4b-m1-16k-v1",
    256,
    512,
    768,
    96,
    768,
    (512, 512, 768),
    16384,
    1,
)
_GENERAL_PROFILE = CapabilityProfile("generic-feature-scale-v1", 4096, 8192)
CAPABILITY_PROFILE_NAMES = (_GENERAL_PROFILE.name, _LEGACY_E4B_PROFILE.name)


def get_capability_profile(name: str) -> CapabilityProfile:
    """Return a built-in immutable profile by name."""
    if name == _GENERAL_PROFILE.name:
        return _GENERAL_PROFILE
    if name == _LEGACY_E4B_PROFILE.name:
        return _LEGACY_E4B_PROFILE
    choices = ", ".join(CAPABILITY_PROFILE_NAMES)
    raise ValueError(f"LLM_CAPABILITY_PROFILE must be one of {choices}")


def _default_capability_profile() -> CapabilityProfile:
    """Return the generic contract; legacy reproduction is always explicit."""
    return _GENERAL_PROFILE


class LLMSettings:
    """Immutable client-local LLM configuration.

    Distinct settings let two clients share one process without global
    leakage. Run composition resolves the optional request-policy defaults
    into one snapshot before the first call.
    """

    def __init__(
        self,
        backend: str,
        api: str,
        model: str,
        api_key: str,
        provider: str,
        allow_fallbacks: bool,
        require_parameters: bool,
        reasoning_effort: str,
        timeout: int,
        capability_profile: CapabilityProfile,
        replan_timeout: int = LLM_TIMEOUT_REPLAN,
        max_retries: int = MAX_LLM_RETRIES,
    ) -> None:
        self.backend = backend
        self.api = api
        self.model = model
        self.api_key = api_key
        self.provider = provider
        self.allow_fallbacks = allow_fallbacks
        self.require_parameters = require_parameters
        self.reasoning_effort = reasoning_effort
        self.timeout = timeout
        self.capability_profile = capability_profile
        self.replan_timeout = replan_timeout
        self.max_retries = max_retries

    def resolved_capability_profile(self) -> CapabilityProfile:
        return self.capability_profile

    def write_retry_tokens(self) -> int:
        """Decode-retry budget for truncated write/edit payloads."""
        return self.capability_profile.step_write_tokens

    def step_tokens(self) -> int:
        """Executor step budget for this run."""
        return self.capability_profile.step_tokens

    def reasoning_token_floor(self, effort: str) -> int:
        floors = self.capability_profile.reasoning_token_floors
        if effort == "low":
            return floors[0]
        if effort == "medium":
            return floors[1]
        if effort == "high":
            return floors[2]
        raise KeyError(effort)

    def reasoning_token_floor_metadata(self) -> dict[str, JSONValue]:
        return self.capability_profile.floors()

    def with_profile(self, profile: CapabilityProfile) -> LLMSettings:
        return LLMSettings(
            self.backend,
            self.api,
            self.model,
            self.api_key,
            self.provider,
            self.allow_fallbacks,
            self.require_parameters,
            self.reasoning_effort,
            self.timeout,
            profile,
            self.replan_timeout,
            self.max_retries,
        )


def settings_from_env() -> LLMSettings:
    """Derive settings from the process environment."""
    backend = os.environ.get("LLM_BACKEND", "local")  # "local" or "openrouter"
    if backend == "openrouter":
        api = OPENROUTER_CHAT_API
        model = os.environ.get("OPENROUTER_MODEL", _OPENROUTER_DEFAULT_MODEL)
    else:
        api = os.environ.get("LLM_API_URL", "http://localhost:8080/v1/chat/completions")
        model = os.environ.get("LLM_MODEL", "local-model")
    requested = os.environ.get("LLM_CAPABILITY_PROFILE", "").strip()
    profile = get_capability_profile(requested) if requested else _default_capability_profile()
    return LLMSettings(
        backend,
        api,
        model,
        os.environ.get("OPENROUTER_API_KEY", ""),
        os.environ.get("OPENROUTER_PROVIDER", "Parasail").strip(),
        os.environ.get("OPENROUTER_ALLOW_FALLBACKS", "1") == "1",
        os.environ.get("OPENROUTER_REQUIRE_PARAMETERS", "0") == "1",
        _parse_reasoning_effort(os.environ.get("OPENROUTER_REASONING_EFFORT", "")),
        LLM_TIMEOUT,
        profile,
        LLM_TIMEOUT_REPLAN,
        MAX_LLM_RETRIES,
    )


def _merge_effort(think_level: str, baseline: str = "") -> str:
    """Effort to request from OpenRouter: the gated level, raised to the
    explicit baseline. An empty result means request reasoning disabled."""
    if baseline and think_level:
        return baseline if _EFFORT_RANK[baseline] >= _EFFORT_RANK[think_level] else think_level
    return baseline if baseline else think_level


class LLMTransportError(Exception):
    """Raised when all LLM request retries are exhausted."""


class LLMApiError(Exception):
    """An API-error body or a reply without the expected envelope.

    ``askme.py`` raises ``KeyError`` here; its text is the quoted key.
    """

    def __init__(self, key: str) -> None:
        super().__init__(repr(key))


class ReplyDecodeError(Exception):
    """A reply that could not be decoded into the expected response type.

    Stands in for ``json.JSONDecodeError`` and the typed attributes the client
    attaches to it; the message keeps that exception's formatted text.
    """

    def __init__(self, message: str, cleaned_text: str = "") -> None:
        super().__init__(message)
        self.cleaned_text = cleaned_text
        self.attempted_action = ""
        self.malformed_action = False
        self.response_truncated = False
        self.envelope_error = ""


def _decode_error_text(message: str) -> str:
    """Text of ``json.JSONDecodeError(message, doc, 0)``."""
    return message + ": line 1 column 1 (char 0)"


def _loads(text: str) -> JSONValue:
    """``json.loads`` whose every failure is a :class:`ReplyDecodeError`."""
    try:
        value: JSONValue = json.loads(text)
        return value
    except json.JSONDecodeError as e:
        raise ReplyDecodeError(str(e)) from None
    except (OverflowError, RecursionError):
        raise ReplyDecodeError(_decode_error_text("JSON value exceeds supported limits")) from None


_TOOL_FIELD_TYPES = {
    "arg": "string",
    "content": "string",
    "append": "boolean",
    "find": "string",
    "replace": "string",
    "offset": "integer",
    "limit": "integer",
    "cursor": "integer",
    "sha256": "string",
    "path": "string",
    "timeout": "integer",
    "reasoning": "string",
}
_TOOL_DESCRIPTIONS = {
    "shell": "Run a shell command in the working directory.",
    "write": "Create or overwrite a file; set append=true to append the next chunk.",
    "edit": "Replace exact text in a file.",
    "read": "Read a file window; continuation pages echo the output's cursor/limit/sha256.",
    "search": "Bounded literal search; pattern in arg, optional path (default '.').",
    "tree": "Bounded directory listing; directory in arg (default '.').",
    "done": "Declare the FULL task complete.",
    "fail": "Give up on the task; one-line reason in arg.",
}


def _action_tools() -> list[JSONValue]:
    """OpenAI-style tool definitions for the registry's action set."""
    tools: list[JSONValue] = []
    for spec in ACTION_ORDER:
        properties: dict[str, JSONValue] = {}
        for field in spec.allowed:
            if field != "action":
                schema: dict[str, JSONValue] = {"type": _TOOL_FIELD_TYPES[field]}
                properties[field] = schema
        parameters: dict[str, JSONValue] = {"type": "object", "properties": properties}
        if spec.requires:
            required: list[JSONValue] = []
            for field in spec.requires:
                required.append(field)
            parameters["required"] = required
        function: dict[str, JSONValue] = {
            "name": spec.name,
            "description": _TOOL_DESCRIPTIONS[spec.name],
            "parameters": parameters,
        }
        tool: dict[str, JSONValue] = {"type": "function", "function": function}
        tools.append(tool)
    return tools


_TRAILING_COMMA_RE = re.compile(r",(\s*})\s*$")


def _repair_json(text: str) -> dict[str, JSONValue] | None:
    """Return a semantics-preserving JSON object repair, or ``None``.

    Safe trailing prose extraction and insertion-only container completion
    are allowed. A partial key/value, string, or scalar is never deleted,
    defaulted, or rewritten to make a reply acceptable.
    """
    if not text or "{" not in text:
        return None
    candidate = text[text.index("{") :].strip()
    try:
        obj, end = json.JSONDecoder().raw_decode(candidate)
        remainder = candidate[end:].lstrip()
        if isinstance(obj, dict) and (not remainder or remainder[0] not in '{}[],:"'):
            return obj
    except json.JSONDecodeError:
        pass
    except (OverflowError, RecursionError):
        return None

    # A trailing comma is syntax only; removing exactly that delimiter does
    # not remove or default a field.
    without_trailing_comma = _TRAILING_COMMA_RE.sub(r"\1", candidate)
    if without_trailing_comma != candidate:
        try:
            # The candidate begins at its first ``{``, so any successful
            # parse is necessarily an object.
            repaired = json.loads(without_trailing_comma)
            if isinstance(repaired, dict):
                return repaired
        except json.JSONDecodeError:
            pass
        except (OverflowError, RecursionError):
            return None

    stack: list[str] = []
    in_string = False
    escaped = False
    for char in candidate:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{" or char == "[":
            stack.append(char)
        elif char == "}" or char == "]":
            if not stack or stack.pop() != ("{" if char == "}" else "["):
                return None
    if in_string or escaped or not stack:
        return None
    stripped = candidate.rstrip()
    if stripped.endswith(",") or stripped.endswith(":"):
        return None
    # A number at EOF may itself be truncated (``12`` vs ``120``). Only close
    # a container after a value token with an unambiguous terminator: string,
    # true/false, null, object, or list.
    if stripped[-1] not in ('"', "e", "l", "}", "]"):
        return None
    suffix = ""
    index = len(stack) - 1
    while index >= 0:
        suffix += "}" if stack[index] == "{" else "]"
        index -= 1
    try:
        completed = json.loads(candidate + suffix)
    except json.JSONDecodeError:
        return None
    except (OverflowError, RecursionError):
        return None
    if isinstance(completed, dict):
        return completed
    return None


class Decoded:
    """One decoded reply: a JSON object, or a parsed action plus transport facts."""

    def __init__(
        self, obj: JSONValue, action: DecodedAction | None, text: str, repaired: bool
    ) -> None:
        self.obj = obj
        self.action = action
        self.text = text
        self.repaired = repaired


def _accept_or_raise(
    obj: dict[str, JSONValue], text: str, repaired: bool, transport: ActionTransport
) -> Decoded:
    if "action" not in obj:
        return Decoded(obj, None, text, repaired)
    parsed = parse_action_envelope(obj)
    if parsed.envelope is not None:
        return Decoded(None, DecodedAction(parsed.envelope, transport), text, repaired)
    if parsed.error_type() == "unknown_action":
        # Preserve the permissive decoder; the action response schema
        # supplies the typed unknown_action classification.
        return Decoded(obj, None, text, repaired)
    raise ReplyDecodeError(_decode_error_text(f"Incomplete action: {parsed.message()}"))


def _action_envelope_error(decoded: Decoded) -> str:
    """Typed rejection reason for a non-dispatchable executor reply, or ``""``.

    Empty and cross-type envelopes (a plan or validator reply at the action
    seam) are ``malformed_action``; a well-formed envelope naming an unknown
    action is ``unknown_action``.
    """
    if decoded.action is not None:
        return ""
    obj = decoded.obj
    if not isinstance(obj, dict) or not obj:
        return "malformed_action"
    return parse_action_envelope(obj).error_type()


class PlanResponse:
    """Typed planner reply: a bounded, non-empty task list."""

    def __init__(self, tasks: list[str]) -> None:
        self.tasks = tasks


def parse_plan(obj: JSONValue, max_tasks: int) -> PlanResponse | None:
    """Accept a planner reply, or return None for a malformed envelope.

    The list is truncated to ``max_tasks`` first and every kept entry must be
    a non-empty string.
    """
    if not isinstance(obj, dict):
        return None
    raw = obj.get("tasks")
    if not isinstance(raw, list):
        return None
    tasks: list[str] = []
    for task in raw[:max_tasks]:
        if not (isinstance(task, str) and task.strip()):
            return None
        tasks.append(task)
    if not tasks:
        return None
    return PlanResponse(tasks)


def parse_task_replan(obj: JSONValue) -> str | None:
    """Accept a replan reply's replacement task, or None for a malformed envelope."""
    if not isinstance(obj, dict):
        return None
    task = obj.get("task")
    if not isinstance(task, str) or not task:
        return None
    return task


class ValidationResponse:
    """Typed final-validation verdict.

    ``valid`` is the verdict; ``deterministic`` marks a verdict derived from
    the deterministic completion check rather than the LLM validator. An
    unavailable or malformed validator reply never becomes a
    ValidationResponse — the caller sees None and must treat the run as
    unverified, not passed.
    """

    def __init__(
        self,
        valid: bool,
        reason: str = "",
        missing: list[str] | None = None,
        deterministic: bool = False,
    ) -> None:
        self.valid = valid
        self.reason = reason
        self.missing: list[str] = [] if missing is None else missing
        self.deterministic = deterministic


def parse_validation(obj: JSONValue) -> ValidationResponse | None:
    """Accept a validator reply, or return None for a malformed envelope."""
    if not isinstance(obj, dict):
        return None
    valid = obj.get("valid")
    if not isinstance(valid, bool):
        return None
    reason = obj.get("reason")
    raw_missing = obj.get("missing")
    missing: list[str] = []
    if isinstance(raw_missing, list):
        for item in raw_missing:
            if isinstance(item, str) and item.strip():
                missing.append(item)
    return ValidationResponse(valid, reason if isinstance(reason, str) else "", missing)


RESPONSE_TYPES = ("action", "plan", "task_replan", "validation")


def _schema_accepts(expect: str, decoded: Decoded, max_tasks: int) -> bool:
    """Decode-time response contract for the expected reply type."""
    if expect == "action":
        return decoded.action is not None
    if decoded.action is not None:
        return False
    if expect == "plan":
        return parse_plan(decoded.obj, max_tasks) is not None
    if expect == "task_replan":
        return parse_task_replan(decoded.obj) is not None
    return parse_validation(decoded.obj) is not None


_STRICT_JSON_SUFFIX = (
    "Output ONLY the JSON object. No reasoning, no explanation, no text outside the JSON."
)
_STRICT_TOOL_SUFFIX = "Call exactly one tool now. No reasoning, no text outside the tool call."

# Truncated write/edit payloads are the most common large-output parse failure;
# detect the attempted action for JSON-text replies. Native tool retries use
# explicit attempted_action metadata, never these diagnostics.
_WRITE_ATTEMPT_RE = re.compile(r'"action"\s*:\s*"(?:write|edit)"')


class ReasoningDecision:
    def __init__(self, requested: str, effective: str, trigger: str) -> None:
        self.requested = requested
        self.effective = effective
        self.trigger = trigger


def _reasoning_decision(
    attempt: int, think: bool, think_level: str, reasoning_policy: str, reasoning_trigger: str
) -> ReasoningDecision:
    """Per-attempt reasoning escalation: requested level, effective level, trigger.

    An explicit think_level pins every attempt; think=True escalates
    medium -> high, then drops to the strict no-thinking contract on the final
    auto-retry (more thinking doesn't fix truncation/format errors); otherwise
    attempt 1 gets the one reasoning-assisted JSON-contract retry. Policy
    "off" suppresses the effective level entirely — for always-on reasoners
    the OpenRouter baseline effort still applies downstream. ``""`` is "none".
    """
    if think_level:
        gated = think_level
        requested = think_level
    elif think:
        requested = "adaptive"
        gated = "" if attempt >= 2 else ("high" if attempt >= 1 else "medium")
    elif attempt == 1:
        gated = "medium"
        requested = "medium"
    else:
        gated = ""
        requested = ""
    trigger = "json_retry" if attempt == 1 and not think and not think_level else reasoning_trigger
    effective = gated if reasoning_policy == "gated" else ""
    return ReasoningDecision(requested, effective, trigger)


class LLMRequest:
    def __init__(self, body: dict[str, JSONValue], headers: list[str], sent_effort: str) -> None:
        self.body = body
        self.headers = headers
        self.sent_effort = sent_effort


def _build_llm_request(
    messages: list[JSONValue],
    budget: int,
    effective_think_level: str,
    strict: bool,
    settings: LLMSettings,
    expect: str,
    tools: list[JSONValue],
) -> LLMRequest:
    """Build one backend-specific request: body, header lines and sent effort.

    ``strict`` appends the strict contract as a final user turn after backend
    shaping. Never mutates the caller's message list. An ``expect="action"``
    call carries the registry-derived tool definitions; every other response
    type keeps the plain JSON contract.
    """
    cfg = settings
    body: dict[str, JSONValue] = {
        "model": cfg.model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": budget,
    }
    tools_transport = expect == "action"
    if tools_transport:
        body["tools"] = tools
        # "auto", never "required": grammar-forced tool choice corrupted
        # native string delimiters on a local server; empty replies are
        # handled by the caller's normal parse-retry policy instead.
        body["tool_choice"] = "auto"
    sent_effort = effective_think_level
    current: list[JSONValue] = messages
    if cfg.backend == "openrouter":
        # Constraints also apply to automatic routing. Keep its default
        # request unchanged, but do not discard explicitly stricter flags.
        if cfg.provider or not cfg.allow_fallbacks or cfg.require_parameters:
            provider: dict[str, JSONValue] = {}
            if cfg.provider:
                order: list[JSONValue] = [cfg.provider]
                provider["order"] = order
            provider["allow_fallbacks"] = cfg.allow_fallbacks
            provider["require_parameters"] = cfg.require_parameters
            body["provider"] = provider
        # Always-on reasoners: the baseline effort applies to every call —
        # strict retries included, since the model cannot stop reasoning and
        # "no thinking" can only mean the baseline.
        sent_effort = _merge_effort(effective_think_level, cfg.reasoning_effort)
        if sent_effort:
            reasoning: dict[str, JSONValue] = {"enabled": True, "effort": sent_effort}
            body["reasoning"] = reasoning
            body["max_tokens"] = max(budget, cfg.reasoning_token_floor(sent_effort))
        else:
            # Some models reason by default. Keep the harness policy model-independent.
            disabled: dict[str, JSONValue] = {"enabled": False}
            body["reasoning"] = disabled
    elif effective_think_level:
        # Local llama-server: prepend <|think|> to system prompt, bump max_tokens
        msgs: list[JSONValue] = []
        for message in messages:
            msgs.append(message)
        if msgs:
            first = msgs[0]
            if isinstance(first, dict) and first.get("role") == "system":
                rewritten: dict[str, JSONValue] = {}
                for key, value in first.items():
                    rewritten[key] = value
                rewritten["content"] = "<|think|>\n" + get_str(first, "content")
                msgs[0] = rewritten
        body["messages"] = msgs
        current = msgs
        body["max_tokens"] = max(budget, cfg.reasoning_token_floor(effective_think_level))
    if strict:
        extended: list[JSONValue] = []
        for message in current:
            extended.append(message)
        suffix: dict[str, JSONValue] = {
            "role": "user",
            "content": _STRICT_TOOL_SUFFIX if tools_transport else _STRICT_JSON_SUFFIX,
        }
        extended.append(suffix)
        body["messages"] = extended
    headers = ["Content-Type: application/json"]
    if cfg.backend == "openrouter" and cfg.api_key:
        headers.append(f"Authorization: Bearer {cfg.api_key}")
        headers.append("X-OpenRouter-Metadata: enabled")
    return LLMRequest(body, headers, sent_effort)


class HttpOutcome:
    """One transport attempt: a JSON object, or a classified failure.

    Kinds: "transport" (connection/timeout), "http_retryable" (429/5xx),
    "http_fatal" (other 4xx), "non_json" (unparseable success body).
    """

    def __init__(
        self, body: dict[str, JSONValue] | None, kind: str, detail: str, error: str, status: int
    ) -> None:
        self.body = body
        self.kind = kind
        self.detail = detail
        self.error = error
        self.status = status


def _llm_http_attempt(
    body: dict[str, JSONValue],
    headers: list[str],
    timeout: int,
    post: Callable[[str, str, list[str], int], HttpReply],
    api: str,
) -> HttpOutcome:
    """One HTTP attempt against the configured chat-completions endpoint."""
    reply = post(api, json.dumps(body), headers, timeout)
    if reply.error:
        return HttpOutcome(None, "transport", f"ConnectionError: {reply.error}", reply.error, 0)
    sc = reply.status
    if sc == 429 or sc >= 500:
        return HttpOutcome(None, "http_retryable", f"HTTP {sc}", "", sc)
    if 400 <= sc < 500:
        return HttpOutcome(None, "http_fatal", f"HTTP {sc}: {reply.text[:200]}", "", sc)
    try:
        decoded = json.loads(reply.text)
    except json.JSONDecodeError as e:
        return HttpOutcome(None, "non_json", reply.text[:100], str(e), sc)
    except (OverflowError, RecursionError):
        return HttpOutcome(None, "non_json", reply.text[:100], "JSON value exceeds limits", sc)
    if not isinstance(decoded, dict):
        # A chat-completions reply is an object; anything else is a gateway glitch.
        return HttpOutcome(None, "non_json", reply.text[:100], "reply is not a JSON object", sc)
    return HttpOutcome(decoded, "", "", "", sc)


def _first_choice(rj: dict[str, JSONValue]) -> dict[str, JSONValue]:
    choices = rj.get("choices")
    if isinstance(choices, list) and choices:
        return as_dict(choices[0])
    empty: dict[str, JSONValue] = {}
    return empty


def _extract_message_text(rj: dict[str, JSONValue]) -> str:
    """Message text with the OpenRouter empty-content reasoning fallback
    (models may put JSON in reasoning when the token budget is tight)."""
    if "choices" not in rj:
        raise LLMApiError("choices")
    choice = _first_choice(rj)
    if "message" not in choice:
        raise LLMApiError("message")
    msg = as_dict(choice["message"])
    text = get_str(msg, "content")
    if not text.strip():
        reasoning = get_str(msg, "reasoning_content")
        if not reasoning:
            r = msg.get("reasoning")
            if isinstance(r, dict):
                reasoning = get_str(r, "content")
            elif isinstance(r, str):
                reasoning = r
        text = reasoning
    return text


_THINK_CLOSED_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_THINK_OPEN_RE = re.compile(r"<think>.*", re.DOTALL)
_CHANNEL_CLOSED_RE = re.compile(r"<\|channel\>.*?<channel\|>", re.DOTALL)
_CHANNEL_OPEN_RE = re.compile(r"<\|channel\>.*", re.DOTALL)
_FENCE_OPEN_RE = re.compile(r"^```(?:json)?\s*")
_FENCE_CLOSE_RE = re.compile(r"\s*```$")


def _decode_json_reply(text: str, finish_reason: str) -> Decoded:
    """Pure decode of one JSON text reply (plan/replan/validation).

    Owns reasoning/fence stripping and JSON extraction/repair. Raises
    :class:`ReplyDecodeError` carrying ``cleaned_text`` when no valid object
    can be recovered; retry policy and typed classification stay with the
    caller."""
    # Strip <think>...</think> (closed) or <think>... (unclosed, truncated at max_tokens)
    text = _THINK_CLOSED_RE.sub("", text).strip()
    text = _THINK_OPEN_RE.sub("", text).strip()
    # Strip <|channel>...<channel|> blocks (local llama-server thinking format)
    text = _CHANNEL_CLOSED_RE.sub("", text).strip()
    text = _CHANNEL_OPEN_RE.sub("", text).strip()
    # Strip markdown code fences if present
    text = _FENCE_OPEN_RE.sub("", text)
    text = _FENCE_CLOSE_RE.sub("", text)
    # Try to extract JSON object from anywhere in the text
    if not text.startswith("{") and "{" in text:
        text = text[text.index("{") :]
    try:
        parsed = _loads(text)
        if not isinstance(parsed, dict):
            raise ReplyDecodeError(
                _decode_error_text("Expected JSON object, got " + json_type_name(parsed))
            )
        return _accept_or_raise(parsed, text, False, ActionTransport())
    except ReplyDecodeError as parse_err:
        # A length-truncated reply must retry; other replies may use
        # insertion-only repair.
        repaired = None if finish_reason == "length" else _repair_json(text)
        if repaired is not None:
            try:
                return _accept_or_raise(repaired, text, True, ActionTransport())
            except ReplyDecodeError:
                pass
        parse_err.cleaned_text = text
        raise parse_err


def _decode_tool_call_reply(rj: dict[str, JSONValue], finish_reason: str) -> Decoded:
    """Decode one native tool-call reply into the action-envelope contract.

    Argument-decode failures carry the native function name in
    ``attempted_action``; ``cleaned_text`` remains a diagnostic, not a source
    of retry policy."""
    msg = get_dict(_first_choice(rj), "message")
    raw_calls = msg.get("tool_calls")
    calls: list[JSONValue] = []
    if isinstance(raw_calls, list):
        calls = raw_calls
    if not calls:
        raise ReplyDecodeError(
            _decode_error_text("reply contains no tool call"),
            get_str(msg, "content").strip()[:200],
        )
    if len(calls) > 1:
        names = ", ".join(
            [py_str(get_dict(as_dict(call), "function").get("name")) for call in calls]
        )
        raise ReplyDecodeError(
            _decode_error_text("reply contains multiple tool calls"), names[:200]
        )
    function = get_dict(as_dict(calls[0]), "function")
    name = function.get("name")
    arguments = function.get("arguments")
    if isinstance(arguments, str):
        raw_arguments = arguments
    elif isinstance(arguments, dict):
        raw_arguments = json.dumps(arguments)
    else:
        raw_arguments = ""
    cleaned = '{"action": "' + py_str(name) + '", "arguments": ' + raw_arguments[:400] + "}"
    if not isinstance(name, str) or not name:
        raise ReplyDecodeError(_decode_error_text("tool call is missing a function name"), cleaned)

    reason = ""
    args: dict[str, JSONValue] = {}
    if raw_arguments.strip():
        try:
            decoded_args = json.loads(raw_arguments)
            if isinstance(decoded_args, dict):
                args = decoded_args
            else:
                reason = "tool call arguments must be a JSON object"
        except json.JSONDecodeError:
            suffix = " (truncated)" if finish_reason == "length" else ""
            reason = f"tool call arguments are not valid JSON{suffix}"
        except (OverflowError, RecursionError):
            reason = "tool call arguments are not valid JSON"
    if not reason and "action" in args:
        reason = "tool call arguments may not carry an action field"
    if reason:
        error = ReplyDecodeError(_decode_error_text(reason), cleaned)
        # The validated name is a string, but need not name a known action.
        # Neither raw argument content nor diagnostic formatting can forge it.
        error.attempted_action = name
        raise error
    envelope: dict[str, JSONValue] = {"action": name}
    for key, value in args.items():
        envelope[key] = value
    return _accept_or_raise(envelope, cleaned, False, ActionTransport())


def _usage_number(usage: dict[str, JSONValue], key: str) -> JSONValue:
    return usage.get(key, 0)


def _log_llm_usage(
    rj: dict[str, JSONValue],
    sent_effort: str,
    attempt: int,
    finish_reason: JSONValue,
    settings: LLMSettings,
    log_sink: Callable[[str], None],
    event_sink: Callable[[dict[str, JSONValue]], None],
) -> None:
    """Console + JSONL usage/route telemetry for one decoded HTTP success."""
    cfg = settings
    usage = get_dict(rj, "usage")
    metadata = get_dict(rj, "openrouter_metadata")
    route = metadata.get("endpoints")
    selected: dict[str, JSONValue] = {}
    if isinstance(route, dict):
        available = route.get("available")
        if isinstance(available, list):
            for endpoint in available:
                if isinstance(endpoint, dict) and truthy(endpoint.get("selected")):
                    selected = endpoint
                    break
    metadata_model = selected.get("model")
    response_model = rj.get("model")
    served_model: JSONValue = None
    if truthy(metadata_model):
        served_model = metadata_model
        served_model_source = "openrouter_metadata"
    elif truthy(response_model):
        served_model = response_model
        served_model_source = "response"
    else:
        served_model_source = "unobserved"
    tok_msg = (
        f"  tokens: prompt={py_str(_usage_number(usage, 'prompt_tokens'))}"
        f" completion={py_str(_usage_number(usage, 'completion_tokens'))}"
        f" total={py_str(_usage_number(usage, 'total_tokens'))}"
    )
    if sent_effort:
        tok_msg += f" thinking={sent_effort}"
    log_sink(tok_msg)
    selected_provider = selected.get("provider")
    event: dict[str, JSONValue] = {
        "event": "tokens",
        "prompt": _usage_number(usage, "prompt_tokens"),
        "completion": _usage_number(usage, "completion_tokens"),
        "total": _usage_number(usage, "total_tokens"),
        "openrouter_cost": _usage_number(usage, "cost"),
        "usage_observed": bool(usage),
        # ``model`` remains the display field. A benchmark contract consumes
        # only ``served_model``: substituting the requested alias when a
        # provider omits route metadata would otherwise manufacture evidence
        # that the expected model served.
        "model": served_model if truthy(served_model) else cfg.model,
        "requested_model": cfg.model,
        "served_model": served_model,
        "served_model_source": served_model_source,
        "provider": selected_provider if truthy(selected_provider) else rj.get("provider", ""),
        "route_attempt": selected.get("attempt"),
        "thinking": sent_effort if sent_effort else None,
        "finish_reason": finish_reason,
        "attempt": attempt,
    }
    event_sink(event)


class LLMClient:
    """LLM provider client: immutable per-client settings plus an injectable
    transport, sleeper, and log/event sinks.

    Settings are explicit; omitted sinks are silent. Constructing clients
    explicitly gives two backends/models in one process without global
    leakage.
    """

    def __init__(
        self,
        settings: LLMSettings,
        post: Callable[[str, str, list[str], int], HttpReply],
        sleep: Callable[[float], None],
        log_sink: Callable[[str], None],
        event_sink: Callable[[dict[str, JSONValue]], None],
        content_truncated: Callable[[], bool] = never_truncated,
    ) -> None:
        self.settings = settings
        self._post = post
        self._sleep = sleep
        self._log = log_sink
        self._event = event_sink
        # Trusted transport metadata for the reply just received. The live
        # HTTP decoder never reports a partial write; a replay transport may.
        self._content_truncated = content_truncated
        self._tools = _action_tools()

    def ask(
        self,
        messages: list[JSONValue],
        max_tokens: int = 256,
        think: bool = False,
        think_level: str = "",
        max_retries: int = MAX_LLM_RETRIES,
        timeout: int = 0,
        reasoning_policy: str = "gated",
        reasoning_trigger: str = "unspecified",
        expect: str = "",
        max_tasks: int = 10,
    ) -> Decoded:
        """Call the backend and decode one plan/action/validator reply.

        This loop owns only retry/backoff policy, the parse-retry budget
        escalation, and the typed errors callers rely on
        (:class:`LLMTransportError`, :class:`LLMApiError` for API-error
        bodies, :class:`ReplyDecodeError` with
        malformed_action/response_truncated). ``expect`` names the response
        schema this call site accepts: a decoded envelope of the wrong type —
        empty, cross-type, or an unknown action — is retried like any parse
        failure and raises typed after the retry budget."""
        if reasoning_policy not in REASONING_POLICIES:
            raise ValueError(f"reasoning_policy must be one of {', '.join(REASONING_POLICIES)}")
        if expect not in RESPONSE_TYPES:
            raise ValueError(f"expect must be one of {', '.join(RESPONSE_TYPES)}")
        cfg = self.settings
        budget = max_tokens
        attempt = 0
        while True:
            decision = _reasoning_decision(
                attempt, think, think_level, reasoning_policy, reasoning_trigger
            )
            baseline: JSONValue = None
            if cfg.backend == "openrouter" and cfg.reasoning_effort:
                baseline = cfg.reasoning_effort
            decision_event: dict[str, JSONValue] = {
                "event": "reasoning_decision",
                "requested_policy": reasoning_policy,
                "requested_trigger": decision.trigger,
                "requested_level": decision.requested if decision.requested else None,
                "effective_level": decision.effective if decision.effective else None,
                "baseline_effort": baseline,
                "attempt": attempt,
            }
            self._event(decision_event)

            # Strict contract on the final auto-retry — suppress reasoning leaks
            request = _build_llm_request(
                messages,
                budget,
                decision.effective,
                attempt >= 2 and not think_level,
                cfg,
                expect,
                self._tools,
            )
            sent_effort = request.sent_effort
            # One transport attempt; retry/backoff policy is enacted here.
            outcome = _llm_http_attempt(
                request.body,
                request.headers,
                timeout if timeout else cfg.timeout,
                self._post,
                cfg.api,
            )
            rj = outcome.body
            if rj is None:
                kind = outcome.kind
                if kind == "http_fatal":
                    # Client errors fail fast: retrying an auth/request-shape bug wastes budget.
                    raise LLMTransportError(outcome.detail)
                if kind == "transport":
                    self._log(f"  Transport error: {outcome.detail}")
                elif kind == "http_retryable":
                    self._log(f"  HTTP {outcome.status}, retrying...")
                else:  # non_json: proxy/gateway glitch returned an unparseable body
                    self._log(f"  Non-JSON response body: {outcome.detail}")
                if attempt < max_retries:
                    self._sleep(1.0 if attempt == 0 else 3.0)
                    attempt += 1
                    continue
                if kind == "transport":
                    raise LLMTransportError(
                        f"Transport failed after {max_retries + 1} attempts: {outcome.error}"
                    )
                if kind == "http_retryable":
                    raise LLMTransportError(
                        f"HTTP {outcome.status} after {max_retries + 1} attempts"
                    )
                raise LLMTransportError(f"Non-JSON response after {max_retries + 1} attempts")
            # Handle API error responses (JSON body with "error" key)
            if "error" in rj:
                api_error = rj["error"]
                shown = api_error
                if isinstance(api_error, dict):
                    shown = api_error.get("message", api_error)
                self._log(f"  API error: {py_str(shown)}")
                if attempt < max_retries:
                    attempt += 1
                    continue
                raise LLMApiError(f"API error: {py_str(api_error)}")
            finish_value = _first_choice(rj).get("finish_reason", "")
            finish_reason = finish_value if isinstance(finish_value, str) else ""
            _log_llm_usage(rj, sent_effort, attempt, finish_value, cfg, self._log, self._event)
            if finish_reason == "length":
                self._log("  output hit token budget (finish_reason=length)")
            text = _extract_message_text(rj)
            try:
                if expect == "action":
                    decoded = _decode_tool_call_reply(rj, finish_reason)
                else:
                    decoded = _decode_json_reply(text, finish_reason)
            except ReplyDecodeError as parse_err:
                cleaned = parse_err.cleaned_text
                if attempt < max_retries:
                    # Action-specific budget: a truncated write/edit payload
                    # needs room for content, not more reasoning. The bound
                    # follows this client's capability profile.
                    write_budget = cfg.write_retry_tokens()
                    if expect == "action":
                        write_attempt = parse_err.attempted_action in ("write", "edit")
                    else:
                        write_attempt = _WRITE_ATTEMPT_RE.search(cleaned) is not None
                    if budget < write_budget and write_attempt:
                        budget = write_budget
                        self._log(f"  write/edit payload budget -> {budget}")
                    think_str = f" thinking={sent_effort}" if sent_effort else ""
                    self._log(
                        f"  [retry {attempt + 1}]{think_str} JSON parse failed, raw: {cleaned[:120]}"
                    )
                    attempt += 1
                    continue
                # Typed classification for the caller: output that hit the
                # token budget is a transport failure of the action envelope,
                # not model noise — the recovery differs.
                parse_err.malformed_action = True
                parse_err.response_truncated = finish_reason == "length"
                raise parse_err
            if decoded.repaired:
                self._log(f"  JSON repaired on attempt {attempt}")
            if not _schema_accepts(expect, decoded, max_tasks):
                if attempt < max_retries:
                    self._log(f"  [retry {attempt + 1}] reply failed the {expect} schema")
                    attempt += 1
                    continue
                schema_err = ReplyDecodeError(
                    _decode_error_text(f"Reply failed the {expect} response schema"), decoded.text
                )
                schema_err.malformed_action = True
                schema_err.response_truncated = finish_reason == "length"
                if expect == "action":
                    schema_err.envelope_error = _action_envelope_error(decoded)
                raise schema_err
            accepted = decoded.action
            if accepted is not None and accepted.envelope.name == "write":
                if self._content_truncated():
                    return Decoded(
                        None,
                        DecodedAction(accepted.envelope, ActionTransport(True)),
                        decoded.text,
                        decoded.repaired,
                    )
            return decoded
