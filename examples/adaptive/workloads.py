"""Small applications for the profile-first adaptive experiment.

These functions run as ordinary, unmodified CPython. They deliberately include
unsupported orchestration and standard-library calls as well as scalar kernels.
The numeric input stream has two common signatures, then unseen inputs and a
changed distribution; it is not evidence that caller cloning discovers more
types than a two-entry function cache.
"""

import importlib.util
from pathlib import Path
import re
import textwrap
from types import FunctionType


PHASES = ("steady", "unseen", "shifted")
NUMERIC_INPUTS = {
    "steady": (3, 5, 7, 0.5),
    "unseen": (True, 2**70, 0.25, 11),
    "shifted": (0.5, 1.25, 2.5, 3),
}
EVENT_NAMES = (
    "orders.created", "users.updated", "billing.payment.completed",
    "orders.cancelled", "system.heartbeat", "users.created",
)
EVENT_PATTERNS = ("orders.*", "users.*", "billing.*.completed", "system.*")
TEXTS = (
    "  A queued event needs normalization before it reaches the worker.  ",
    "Repeated     whitespace and\t tabs occur in imported customer records.",
    "A longer description makes wrapping inspect both whitespace and long-word boundaries.",
)
_route_spec = importlib.util.spec_from_file_location(
    "adaptive_original_event_router", Path(__file__).resolve().parents[1] / "route" / "route.py",
)
assert _route_spec is not None and _route_spec.loader is not None
EVENT_ROUTER = importlib.util.module_from_spec(_route_spec)
_route_spec.loader.exec_module(EVENT_ROUTER)


def numeric_step(x, i):
    return x + (i % 7) * 3


def numeric_batch(x, n):
    for i in range(n):
        x = numeric_step(x, i)
    return x


def run_numeric(phase="steady", iterations=24, *, batch=numeric_batch, step=None, inner=256):
    """Run Python orchestration around scalar batches, optionally substituting code.

    A leaf override creates a new function with the *same* numeric_batch code and
    a copied globals dictionary. It never edits the source or module bindings.
    A batch override replaces the whole call region.
    """
    if phase not in PHASES:
        raise ValueError("unknown workload phase")
    if step is not None:
        if batch is not numeric_batch:
            raise ValueError("choose a leaf override or a batch override")
        namespace = dict(numeric_batch.__globals__)
        namespace["numeric_step"] = step
        batch = FunctionType(numeric_batch.__code__, namespace, numeric_batch.__name__)
    values = NUMERIC_INPUTS[phase]
    records = []
    for index in range(iterations):
        result = batch(values[index % len(values)], inner + index % 3)
        records.append((type(result).__name__, result))
    return records


def run_event(phase="steady", iterations=24):
    if phase not in PHASES:
        raise ValueError("unknown workload phase")
    names = EVENT_NAMES
    if phase == "unseen":
        names = (*names, "unknown.new-event", "billing.refund.completed")
    elif phase == "shifted":
        names = tuple(reversed(names))
    EVENT_ROUTER.load([f"{pattern} destination-{index}" for index, pattern in enumerate(EVENT_PATTERNS)])
    counts = [0] * (len(EVENT_PATTERNS) + 1)
    for index in range(iterations):
        name = names[index % len(names)]
        counts[EVENT_ROUTER.route_fnmatch(name) + 1] += 1
    return counts


def normalize_text(value, width):
    normalized = re.sub(r"\s+", " ", value).strip()
    return textwrap.fill(normalized, width=width)


def run_text(phase="steady", iterations=24):
    if phase not in PHASES:
        raise ValueError("unknown workload phase")
    texts = TEXTS
    if phase == "unseen":
        texts = (*texts, "Unicode café résumé — imported text.", "a" * 120)
    elif phase == "shifted":
        texts = tuple(reversed(texts))
    lengths = []
    for index in range(iterations):
        output = normalize_text(texts[index % len(texts)], 32 + index % 3)
        lengths.append(len(output))
    return lengths


WORKLOADS = {"event": run_event, "text": run_text, "numeric": run_numeric}


def run_workload(name, phase="steady", iterations=24):
    return WORKLOADS[name](phase, iterations)
