from collections import defaultdict
from mods.constructor_dependency import Options as Configuration, Variable
import mods.constructor_dependency as models


class QuotedErrors:
    def __init__(self, options: "Configuration") -> None:
        self.options: Configuration = options
        self.items: defaultdict[str, set[str]] = defaultdict(set)


class QualifiedErrors:
    def __init__(self, options: models.Options) -> None:
        self.options: models.Options = options
        self.items: defaultdict[str, set[str]] = defaultdict(set)


class VariableErrors:
    def __init__(self, options: Variable) -> None:
        self.options: Variable = options
        self.items: defaultdict[str, set[str]] = defaultdict(set)
