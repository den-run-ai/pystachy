# pystachy: dynamic-any
from typing import TYPE_CHECKING

from .utils.constants import JSONReturnType
from .utils.json_context import ContextValues

if TYPE_CHECKING:
    from .json_parser import JSONParser


def skip_comment(self: "JSONParser") -> None:
    """Consume one comment without parsing any following JSON value."""
    char = self.get_char_at()
    if char == "#" or (char == "/" and self.get_char_at(1) == "/"):
        termination_characters = ["\n", "\r"]
        if char == "#":
            if ContextValues.ARRAY in self.context.context:
                termination_characters.append("]")
            if ContextValues.OBJECT_VALUE in self.context.context:
                termination_characters.append("}")
            if ContextValues.OBJECT_KEY in self.context.context:
                termination_characters.append(":")
        # Pystachy port: find the earliest terminator directly, without building the comment
        # one character at a time. Each search is bounded to a growing window, so a long
        # document of short lines without carriage returns is not searched to its end.
        start = self.index
        length = len(self.json_str)
        span = 64
        while self.index < length:
            end = min(self.index + span, length)
            stop = end
            for terminator in termination_characters:
                at = self.json_str.find(terminator, self.index, stop)
                if at >= 0:
                    stop = at
            self.index = stop
            if stop < end:
                break
            span *= 2
        if self.logging:
            self.log(f"Found line comment: {self.json_str[start : self.index]}, ignoring")
    elif char == "/" and self.get_char_at(1) == "*":
        # Pystachy port: find the closing delimiter directly. The search starts at the opener's
        # star, which can also close the comment (/*/), as the loop it replaces accepted.
        start = self.index
        end = self.json_str.find("*/", start + 1)
        if end == -1:
            self.index = len(self.json_str)
            self.log("Reached end-of-string while parsing block comment; unclosed block comment.")
        else:
            self.index = end + 2
        if self.logging:
            self.log(f"Found block comment: {self.json_str[start : self.index]}, ignoring")
    elif char == "/":
        # Make progress on standalone slashes that reach the repair fallback.
        self.index += 1


def parse_comment(self: "JSONParser", record_top_level_value: bool = False) -> JSONReturnType:
    """Skip comments and resume value parsing only at the top level."""
    while True:
        skip_comment(self)
        if not self.context.empty:
            return ""
        # Keep long runs of top-level comments iterative.
        self.skip_whitespaces()
        if self.get_char_at() not in ["#", "/"]:
            return self.parse_json(record_top_level_value=record_top_level_value)
