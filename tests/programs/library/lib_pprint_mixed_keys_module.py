# pprint orders the keys whose < raises TypeError by the names of their types, as CPython's
# _safe_key does: Card's, "<class 'Cards.Card'>", before None's, "<class 'NoneType'>", and an
# enum class's, "<enum 'Suit'>", after it (tests/pprint_keys/Cards.py).
import pprint

from Cards import Card, Suit

cards: dict[Card | None, str] = {None: "none", Card(3): "three", Card(1): "one"}
print(pprint.pformat(cards))
print(pprint.pformat(cards, width=16))
print(pprint.saferepr(cards))
suits: dict[Suit | None, int] = {Suit.SPADES: 2, None: 0}
print(pprint.pformat(suits))
pprint.pprint(suits, width=14)
