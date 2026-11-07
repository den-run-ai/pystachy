"""Retain DLPack-adapted host batches and score them in native Pystachy."""
from ffi import export
from pyobj import Buffer, import_module

_host = import_module("dlpack_host")
_held: list[Buffer] = []


def _release() -> None:
    for buffer in _held:
        buffer.close()
    _held.clear()


def _retain() -> None:
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


def _score() -> float:
    return _held[0].dot(_held[1])


def _smoke() -> None:
    _retain()
    assert _held[0].readonly() and _held[1].readonly()
    assert _score() == 7.5
    _host.attr("mutate").call([]).close()
    assert _score() == 8.5
    _host.attr("drop").call([]).close()
    assert bool(_host.attr("retained").call([]))
    assert _score() == 8.5
    reverse = _held[0].view(3, 4, -1)
    _held[0].close()
    _held[0] = reverse
    assert _score() == 9.0
    assert bool(_host.attr("retained").call([]))
    _release()
    _release()
    assert bool(_host.attr("released").call([]))
    print("PASS DLPack zero-copy, alias updates, retention, derived stride, final release")


@export
def retain() -> None:
    _retain()


@export
def score() -> float:
    return _score()


@export
def release() -> None:
    _release()


@export
def smoke() -> None:
    _smoke()


if __name__ == "__main__":
    _smoke()
