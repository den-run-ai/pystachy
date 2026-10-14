"""DeltaBlue-shaped receiver dispatch: a plan of constraints executed through base-typed receivers.

The census (docs/archive/skew-specialization-candidates.md) finds DeltaBlue's busiest polymorphic
site, `Plan.execute`, at three constraint classes with 82% one of them. The `mixed` plan has that
82/9/9 skew; `mono` holds only the dominant class but keeps the `list[Constraint]` type, so it
pays dispatch with perfectly predictable branches. tools/bench_receiver_dispatch.py derives the
concrete control (a `list[EqualityConstraint]` plan) from this file without changing any method.

Each block of 100 restarts its value chain at an EditConstraint counter, so values stay below
about 512 * ROUNDS: no 64-bit overflow for any practical ROUNDS.

usage: receiver_skew.py mixed|mono ROUNDS   (result on stdout, seconds on stderr)
"""
import sys
import time


class Variable:
    def __init__(self, value: int) -> None:
        self.value = value


class Constraint:
    def __init__(self, strength: int, output: Variable) -> None:
        self.strength = strength
        self.output = output

    def execute(self) -> None:
        pass

    def is_input(self) -> bool:
        return False


class EqualityConstraint(Constraint):
    def __init__(self, strength: int, source: Variable, output: Variable) -> None:
        super().__init__(strength, output)
        self.source = source

    def execute(self) -> None:
        self.output.value = self.source.value


class ScaleConstraint(Constraint):
    def __init__(self, strength: int, source: Variable, scale: int, offset: int, output: Variable) -> None:
        super().__init__(strength, output)
        self.source = source
        self.scale = scale
        self.offset = offset

    def execute(self) -> None:
        self.output.value = self.source.value * self.scale + self.offset


class EditConstraint(Constraint):
    def execute(self) -> None:
        self.output.value += 1

    def is_input(self) -> bool:
        return True


def build(n: int, mix: bool) -> list[Constraint]:
    plan: list[Constraint] = []
    previous = Variable(1)
    for i in range(n):
        current = Variable(0)
        k = i % 100
        if mix and k < 9:
            plan.append(ScaleConstraint(1, previous, 2, 1, current))
        elif mix and k < 18:
            plan.append(EditConstraint(2, current))
        else:
            plan.append(EqualityConstraint(1, previous, current))
        previous = current
    return plan


def execute(plan: list[Constraint]) -> int:
    inputs = 0
    for c in plan:
        c.execute()
        if c.is_input():
            inputs += 1
    return inputs


mode = sys.argv[1] if len(sys.argv) > 1 else "mixed"
rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
plan = build(1000, mode == "mixed")
start = time.perf_counter()
total = 0
for _ in range(rounds):
    total += execute(plan)
elapsed = time.perf_counter() - start
print(mode, rounds, total, plan[-1].output.value)
print("seconds", elapsed, file=sys.stderr)
