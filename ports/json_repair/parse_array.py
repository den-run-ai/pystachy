# pystachy: dynamic-any
# Pystachy port: specialize schema-free parsing; recursive values use dynamic Any.
from typing import Any

from .utils.constants import STRING_DELIMITERS
from .utils.json_context import ContextValues
from .utils.object_comparer import ObjectComparer

def parse_array(
    self,
    schema: dict[str, Any] | bool | None = None,
    path: str = "$",
    closing_delimiter: str = "]",
) -> list[Any]:
    # <array> ::= '[' [ <json> *(', ' <json>) ] ']' ; A sequence of JSON values separated by commas
    # Pystachy port: the public entry point rejects schemas.
    if schema is not None:
        raise ValueError("This port supports schema-free repair only.")
    array_is_object_value = self.context.current == ContextValues.OBJECT_VALUE
    closed_before_parent_member = False

    arr: list[Any] = []
    with self.context.enter(ContextValues.ARRAY):
        self.skip_whitespaces()
        char = self.get_char_at()
        while char and char not in [closing_delimiter, "}"]:
            if char is not None and char in STRING_DELIMITERS:
                # A string followed by ':' is often a missing object start; treat it as an object.
                i = 1
                i = self.skip_to_character(char, i)
                i = self.scroll_whitespaces(idx=i + 1)
                if self.get_char_at(i) == ":":
                    if array_is_object_value and arr and all(not isinstance(item, (dict, list)) for item in arr):
                        self.log("Closed unclosed array before object member after scalar items")
                        closed_before_parent_member = True
                        break
                    value = self.parse_object()
                else:
                    value = self.parse_string()
            else:
                value = self.parse_json()

            if ObjectComparer.is_strictly_empty(value) and self.get_char_at() not in [closing_delimiter, ","]:
                self.index += 1
            elif value == "..." and self.get_char_at(-1) == ".":
                self.log(
                    "While parsing an array, found a stray '...'; ignoring it",
                )
            else:
                arr.append(value)

            char = self.get_char_at()
            while char and char != closing_delimiter and (char.isspace() or char == ","):
                self.index += 1
                char = self.get_char_at()

        if char != closing_delimiter:
            self.log(
                f"While parsing an array we missed the closing {closing_delimiter}, ignoring it",
            )

        if not closed_before_parent_member:
            self.index += 1

    return arr
