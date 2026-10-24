"""
Benchmark comprehensions.

Author: Carl Meyer
"""

from dataclasses import dataclass
# Pystachy port: use integer kind tags in place of the unavailable Enum module.
from typing import Iterable, List, Optional

# Pystachy port: keep upstream timers, collecting seconds for the deterministic runner.
import time
import sys

TIMED: list[float] = []


# Pystachy port: the benchmark only compares these two kind tags.
class WidgetKind:
    BIG = 1
    SMALL = 2


@dataclass
class Widget:
    widget_id: int
    creator_id: int
    derived_widget_ids: List[int]
    kind: int  # Pystachy port: integer kind tags replace Enum values.
    has_knob: bool
    has_spinner: bool


class WidgetTray:
    def __init__(self, owner_id: int, widgets: List[Widget]) -> None:
        self.owner_id = owner_id
        self.sorted_widgets: List[Widget] = []
        self._add_widgets(widgets)

    def _any_knobby(self, widgets: Iterable[Optional[Widget]]) -> bool:
        return any(w.has_knob for w in widgets if w)

    def _is_big_spinny(self, widget: Widget) -> bool:
        return widget.kind == WidgetKind.BIG and widget.has_spinner

    def _add_widgets(self, widgets: List[Widget]) -> None:
        # sort order: mine first, then any widgets with derived knobby widgets in order of
        # number derived, then other widgets in order of number derived, and we exclude
        # big spinny widgets entirely
        widgets = [w for w in widgets if not self._is_big_spinny(w)]
        id_to_widget = {w.widget_id: w for w in widgets}
        id_to_derived = {
            w.widget_id: [id_to_widget.get(dwid) for dwid in w.derived_widget_ids]
            for w in widgets
        }
        sortable_widgets = [
            (
                w.creator_id == self.owner_id,
                self._any_knobby(id_to_derived[w.widget_id]),
                len(id_to_derived[w.widget_id]),
                w.widget_id,
            )
            for w in widgets
        ]
        sortable_widgets.sort()
        self.sorted_widgets = [id_to_widget[sw[-1]] for sw in sortable_widgets]


def make_some_widgets() -> List[Widget]:
    widget_id = 0
    widgets: List[Widget] = []  # Pystachy port: type storage before the first append.
    for creator_id in range(3):
        for kind in [WidgetKind.BIG, WidgetKind.SMALL]:  # Pystachy port: the two enum members.
            for has_knob in [True, False]:
                for has_spinner in [True, False]:
                    derived = [w.widget_id for w in widgets[::creator_id + 1]]
                    widgets.append(
                        Widget(
                            widget_id, creator_id, derived, kind, has_knob, has_spinner
                        )
                    )
                    widget_id += 1
    assert len(widgets) == 24
    return widgets


# Pystachy port: expose the resulting widget order for differential validation.
def bench_comprehensions(loops: int) -> list[int]:
    range_it = range(loops)
    widgets = make_some_widgets()
    t0 = time.perf_counter()
    for _ in range_it:
        tray = WidgetTray(1, widgets)
        assert len(tray.sorted_widgets) == 18
    # Pystachy port: record time first; check and report the full order outside the timer.
    TIMED.append(time.perf_counter() - t0)
    return [w.widget_id for w in tray.sorted_widgets]


# Pystachy port: a deterministic main replaces pyperf.Runner.
if __name__ == "__main__":
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    result = bench_comprehensions(loops)
    print("seconds", sum(TIMED), file=sys.stderr)
    print("comprehensions", loops, result)
