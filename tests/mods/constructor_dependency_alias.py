from typing import Annotated
from mods.constructor_dependency import Errors as Problems, Root
import mods.constructor_dependency as models


class Aliased(Root):
    def __init__(self, errors: Problems) -> None:
        self.errors: Problems = errors
        self.value: int = errors.count()


class Qualified(Root):
    def __init__(self, errors: models.Errors) -> None:
        self.errors: models.Errors = errors
        self.value: int = errors.count()


class Quoted(Root):
    def __init__(self, errors: "Problems") -> None:
        self.errors: Problems = errors
        self.value: int = errors.count()


class Wrapped(Root):
    def __init__(self, errors: Annotated[Problems, "storage"]) -> None:
        self.errors: Problems = errors
        self.value: int = errors.count()
