# pystachy: dynamic-any
# Existing nominal and native-list adapters retain their storage through a factory.
from typing import Any


class Payload:
    def __init__(self, value: int) -> None:
        self.value = value

    def read(self) -> int:
        return self.value


class Envelope:
    __slots__ = ("payload", "pair", "items")

    def __init__(self, payload: Payload, pair: tuple[Payload, int], items: list[int]) -> None:
        self.payload = payload
        self.pair = pair
        self.items = items


payload = Payload(7)
boxed: Any = payload
number = int("123456")
pair: tuple[Payload, int] = (payload, number)
items: list[int] = [number, 2]
factory: Any = Envelope
wrapped = factory(boxed, pair, items)
print(type(wrapped) is Envelope, wrapped.payload is payload)
# Typed tuple numeric items retain the existing identity boundary; their
# values and nominal references still cross through the supported adapter.
print(wrapped.pair[0] is payload, wrapped.pair[1] == number)
print(wrapped.items is items, wrapped.items[0] is number)
wrapped.items.append(3)
print(items, wrapped.payload.read())
