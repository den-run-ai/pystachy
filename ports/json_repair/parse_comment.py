# pystachy: dynamic-any
# Pystachy port: annotate recursive JSON values directly with dynamic Any.
from typing import Any

from .utils.json_context import ContextValues


def skip_comment(self) -> None:
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
        start = self.index
        length = len(self.json_str)
        # Bound each delimiter search to this comment even on a long document
        # containing many short lines with no carriage returns.
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
            self.log(f"Found line comment: {self.json_str[start:self.index]}, ignoring")
    elif char == "/" and self.get_char_at(1) == "*":
        start = self.index
        # Upstream accepts /*/ because the opener's star can also close it.
        end = self.json_str.find("*/", start + 1)
        if end == -1:
            self.index = len(self.json_str)
            self.log("Reached end-of-string while parsing block comment; unclosed block comment.")
        else:
            self.index = end + 2
        if self.logging:
            self.log(f"Found block comment: {self.json_str[start:self.index]}, ignoring")
    elif char == "/":
        # Make progress on standalone slashes that reach the repair fallback.
        self.index += 1


def parse_comment(self, record_top_level_value: bool = False) -> Any:
    # Pystachy's parse_json loop resumes top-level parsing without recursion.
    while True:
        skip_comment(self)
        if not self.context.empty:
            return ""
        self.skip_whitespaces()
        if self.get_char_at() not in ["#", "/"]:
            return ""
