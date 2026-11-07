"""Retained reward/scoring batch used by cbclient and bench/cpu_buffers."""
from ffi import export
from pyobj import Buffer, import_module, of_int

_host = import_module("cbdata")
_held: list[Buffer] = []


def _release() -> None:
    for b in _held:
        b.close()
    _held.clear()


@export
def release() -> None:
    _release()


@export
def retain() -> None:
    _release()
    data = _host.attr("data")
    weights = _host.attr("weights")
    try:
        _held.append(data.buffer_f64())
        _held.append(weights.buffer_f64())
    except BaseException:
        _release()
        raise
    finally:
        data.close()
        weights.close()


@export
def score() -> float:
    return _held[0].dot(_held[1])


@export
def open_score() -> float:
    data = _host.attr("data")
    try:
        b = data.buffer_f64()
        try:
            return b.dot(_held[1])
        finally:
            b.close()
    finally:
        data.close()


@export
def copied_score() -> float:
    data = _host.attr("copy_data").call([])
    try:
        b = data.buffer_f64()
        try:
            return b.dot(_held[1])
        finally:
            b.close()
    finally:
        data.close()


@export
def boxed_score() -> float:
    data, weights = _host.attr("data"), _host.attr("weights")
    total = 0.0
    try:
        for i in range(len(data)):
            index = of_int(i)
            left, right = data[index], weights[index]
            total += left.to_float() * right.to_float()
            left.close()
            right.close()
            index.close()
        return total
    finally:
        data.close()
        weights.close()


@export
def first() -> float:
    return _held[0].get(0)
