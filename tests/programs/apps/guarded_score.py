# Independent semantic controls; each path gets fresh mutable inputs and callbacks.
from collections.abc import Callable
import math

from scoring import absolute_error, score_generic, score_guarded, squared_error


def run(guarded: bool, callback: Callable[[float, float], float],
        predicted: list[float], expected: list[float]) -> float:
    if guarded:
        return score_guarded(callback, predicted, expected)
    return score_generic(callback, predicted, expected)


def signed_error(predicted: float, expected: float) -> float:
    return predicted - expected


def shifted_error(shift: float) -> Callable[[float, float], float]:
    def callback(predicted: float, expected: float) -> float:
        return abs(predicted - expected) + shift
    return callback


class Shifted:
    def __init__(self, shift: float):
        self.shift = shift
        self.calls: list[float] = []

    def score(self, predicted: float, expected: float) -> float:
        self.calls.append(predicted)
        return abs(predicted - expected) + self.shift


def batches(guarded: bool) -> None:
    first = Shifted(1.0)
    second = Shifted(5.0)
    # Same closure code, different environments; switch back to known targets.
    callbacks: list[Callable[[float, float], float]] = [
        squared_error, absolute_error, signed_error, shifted_error(1.0),
        shifted_error(5.0), first.score, second.score, squared_error,
        absolute_error,
    ]
    wants = [11.0, 5.0, -1.0, 8.0, 20.0, 8.0, 20.0, 11.0, 5.0]
    for index in range(len(callbacks)):
        result = run(guarded, callbacks[index], [1.0, -2.0, 0.5],
                     [0.0, 1.0, -0.5])
        assert result == wants[index]
    assert first.calls == [1.0, -2.0, 0.5]
    assert second.calls == [1.0, -2.0, 0.5]
    print("batches", guarded, wants)


def edges(guarded: bool) -> None:
    callbacks: list[Callable[[float, float], float]] = [
        squared_error, absolute_error, signed_error,
    ]
    for callback in callbacks:
        assert run(guarded, callback, [], []) == 0.0
        assert run(guarded, callback, [2.0], [1.0]) == 1.0
        zero = run(guarded, callback, [-0.0], [0.0])
        assert zero == 0.0 and math.copysign(1.0, zero) == 1.0
        assert math.isnan(run(guarded, callback, [float("nan")], [1.0]))
        assert math.isnan(run(guarded, callback, [float("inf")], [float("inf")]))
        assert run(guarded, callback, [float("inf")], [0.0]) == float("inf")
    # Sequential accumulation matters: reassociation would change this result.
    assert run(guarded, signed_error, [1e16, 1.0, -1e16], [0.0] * 3) == 0.0
    assert run(guarded, squared_error, [1e8, 1.0, 1.0], [0.0] * 3) == 1e16
    assert run(guarded, absolute_error, [1e16, 1.0, 1.0], [0.0] * 3) == 1e16
    assert run(guarded, absolute_error, [1.0, 1.0, 1e16], [0.0] * 3) == 1e16 + 2.0
    print("edges", guarded, "ok")


def initial_length_errors(guarded: bool) -> None:
    calls: list[float] = []

    def callback(predicted: float, expected: float) -> float:
        calls.append(predicted)
        return predicted - expected

    targets: list[list[float]] = [[], [0.0, 0.0]]
    for expected in targets:
        caught = False
        try:
            run(guarded, callback, [1.0], expected)
        except ValueError as error:
            assert str(error) == "score inputs must have equal length"
            caught = True
        assert caught
    assert calls == []
    print("initial lengths", guarded, "ok")


def callback_exception(guarded: bool) -> None:
    calls: list[float] = []

    def callback(predicted: float, expected: float) -> float:
        calls.append(predicted)
        if len(calls) == 2:
            raise RuntimeError("stop after two")
        return predicted - expected

    caught = False
    try:
        run(guarded, callback, [1.0, 2.0, 3.0], [0.0, 0.0, 0.0])
    except RuntimeError as error:
        assert str(error) == "stop after two"
        caught = True
    assert caught and calls == [1.0, 2.0]
    print("exception", guarded, calls)


def mutation(guarded: bool, mode: int) -> None:
    predicted = [1.0, 2.0, 3.0]
    expected = [0.0, 0.0, 0.0]
    calls: list[float] = []

    def callback(x: float, y: float) -> float:
        calls.append(x)
        if len(calls) == 1:
            if mode == 0:
                predicted[1] = 7.0
                expected[1] = 2.0
                predicted.append(4.0)
                expected.append(1.0)
            elif mode == 1:
                predicted.pop()
                expected.pop()
            else:
                expected.pop()
        return x - y

    caught = False
    result = 0.0
    try:
        result = run(guarded, callback, predicted, expected)
    except IndexError:
        caught = True
    if mode == 0:
        assert not caught and result == 12.0
        assert calls == [1.0, 7.0, 3.0, 4.0]
        assert predicted == [1.0, 7.0, 3.0, 4.0]
        assert expected == [0.0, 2.0, 0.0, 1.0]
    elif mode == 1:
        assert not caught and result == 3.0 and calls == [1.0, 2.0]
        assert predicted == [1.0, 2.0] and expected == [0.0, 0.0]
    else:
        assert caught and calls == [1.0, 2.0]
        assert predicted == [1.0, 2.0, 3.0] and expected == [0.0, 0.0]
    print("mutation", guarded, mode, calls)


for guarded in [False, True]:
    batches(guarded)
    edges(guarded)
    initial_length_errors(guarded)
    callback_exception(guarded)
    for mode in range(3):
        mutation(guarded, mode)
print("guarded scoring controls passed")
