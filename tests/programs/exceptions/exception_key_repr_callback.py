# The key deliberately has neither __hash__ nor __eq__: its lookup descriptor
# uses identity, while formatting a missing key can still call user code.
events: list[str] = []
failure = RuntimeError("representation failed")


class IdentityKey:
    def __init__(self, mode: int) -> None:
        self.mode = mode

    def __repr__(self) -> str:
        events.append("repr")
        if self.mode == 1:
            raise failure
        table[self] = 37
        return "IdentityKey()"


table: dict[IdentityKey, int] = {}


def exercise(mode: int) -> None:
    table.clear()
    events.clear()
    query = IdentityKey(mode)
    try:
        try:
            print("unexpected lookup success", table[query])
        except KeyError as error:
            # CPython formats here; Pystachy already formatted at the miss.
            # Render before recording handler progress to compare their common
            # outcome without changing Pystachy's documented eager formatting.
            message = str(error)
            events.append("key handler")
            print("missing", message)
        finally:
            events.append("inner finally")
    except RuntimeError as error:
        events.append("outer handler")
        print("same exception", error is failure, str(error))
    finally:
        events.append("outer finally")
    print(mode, events, len(table))
    if mode == 2:
        # Formatting inserted this key, but the original read must still fail.
        print(table[query])


exercise(1)
exercise(2)
