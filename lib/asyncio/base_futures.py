__all__ = ()

# Pystachy port: no reprlib or format_helpers: a result's repr is not shortened, and the
# callbacks are counted rather than named (lib/compatibility.md#asyncio); isfuture() is
# futures.isfuture

# States for Future.
_PENDING = 'PENDING'
_CANCELLED = 'CANCELLED'
_FINISHED = 'FINISHED'


def _format_callbacks(size: int) -> str:
    """helper function for Future.__repr__"""
    cb = ''
    if size == 1:
        cb = '<callback>'
    elif size == 2:
        cb = '<callback>, <callback>'
    elif size > 2:
        cb = '<callback>, <{} more>, <callback>'.format(size - 2)
    return f'cb=[{cb}]'


def _future_repr_info(future) -> list[str]:
    # (Future) -> str
    """helper function for Future.__repr__"""
    info = [future._state.lower()]
    if future._state == _FINISHED:
        exc = future._exception
        if exc is not None:
            info.append(f'exception={exc!r}')
        else:
            # use reprlib to limit the length of the output, especially
            # for very long strings
            result = future._repr_result()
            info.append(f'result={result}')
    if future._callbacks:
        info.append(_format_callbacks(len(future._callbacks)))
    return info


def _future_repr(future) -> str:
    info = ' '.join(_future_repr_info(future))
    return f'<{future.__class__.__name__} {info}>'
