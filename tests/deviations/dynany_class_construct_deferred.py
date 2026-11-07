# pystachy: dynamic-any
# An imported ordinary initializer must be compiled by a static call first.
# Argument effects still occur before the explicit deferred-constructor error.
from typing import Any
from string import Template


def argument() -> str:
    print("argument")
    return "$value"


factory: Any = Template
try:
    factory(argument())
    print("constructed")
except NotImplementedError as exc:
    print(str(exc))
