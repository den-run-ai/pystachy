# pystachy: dynamic-any
from typing import Any
import json


class BadHash:
    def __init__(self) -> None:
        self.armed = False

    def __hash__(self) -> int:
        if self.armed:
            raise RuntimeError("hashed again")
        return 1

    def __eq__(self, other: object) -> bool:
        return self is other


class Payload:
    pass


plain_key = BadHash()
plain_doc: Any = {plain_key: 2}
plain_key.armed = True
try:
    print("plain", json.dumps(plain_doc))
except TypeError as exc:
    print("plain", type(exc).__name__, str(exc))
except RuntimeError as exc:
    print("plain", type(exc).__name__, str(exc))


def encode(o: Any) -> Any:
    if mode == 1:
        del doc[key]
        doc["new"] = 4
    elif mode == 3:
        doc[key] = 2
    key.armed = True
    return 1


for mode in range(4):
    key = BadHash()
    doc: dict[Any, Any] = {"first": Payload(), key: 2, "last": 3}
    if mode == 3:
        del doc[key]
    try:
        print(mode, json.dumps(doc, default=encode, skipkeys=mode == 2))
    except TypeError as exc:
        print(mode, type(exc).__name__, str(exc))
    except RuntimeError as exc:
        print(mode, type(exc).__name__, str(exc))
