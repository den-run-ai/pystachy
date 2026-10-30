# pystachy: dynamic-any
# Pystachy port: annotate recursive JSON values directly with dynamic Any.
from typing import Any
import json
from collections.abc import Callable

# Pystachy port: explicit native Any decoder; ordinary CPython keeps its decoder.
try:
    from json import _raw_decode as raw_decode
except ImportError:
    def raw_decode(s: str, idx: int = 0) -> tuple[Any, int]:
        return json.JSONDecoder().raw_decode(s, idx)

from .parse_array import parse_array as _parse_array
from .parse_comment import parse_comment as _parse_comment
from .parse_number import parse_number as _parse_number
from .parse_object import parse_object as _parse_object
from .parse_string import parse_string as _parse_string
from .parser_parenthesized import parenthesized_is_explicit_tuple, top_level_parenthesized_can_start_value
from .utils.constants import STRING_DELIMITERS
from .utils.json_context import JsonContext
from .utils.object_comparer import ObjectComparer



class JSONParser:
    # Split the parse methods into separate files because this one was like 3000 lines
    def parse_array(
        self,
        schema: dict[str, Any] | bool | None = None,
        path: str = "$",
        closing_delimiter: str = "]",
    ) -> list[Any]:
        return _parse_array(self, schema, path, closing_delimiter)

    def parse_comment(self, record_top_level_value: bool = False) -> Any:
        return _parse_comment(self, record_top_level_value=record_top_level_value)

    def parse_number(self) -> Any:
        return _parse_number(self)

    def parse_object(
        self,
        schema: dict[str, Any] | bool | None = None,
        path: str = "$",
    ) -> Any:
        return _parse_object(self, schema, path)

    def parse_string(self) -> Any:
        return _parse_string(self)

    def __init__(
        self,
        json_str: str,
        logging: bool | None,
        stream_stable: bool = False,
        strict: bool = False,
        try_valid_json_suffix: bool = False,
    ) -> None:
        # The string to parse
        # Pystachy port: in-memory strings only.
        self.json_str: str = json_str
        # Index is our iterator that will keep track of which character we are looking at right now
        self.index: int = 0
        # This is used in the object member parsing to manage the special cases of missing quotes in key or value
        self.context = JsonContext()
        self.deferred_contexts: list[int] = []
        # Use this to log the activity, but only if logging is active

        self.logging = logging
        self.logger: list[Any] = []
        # Pystachy port: log() guards logging instead of rebinding a method.
        # When the json to be repaired is the accumulation of streaming json at a certain moment.
        # e.g. json obtained from llm response.
        # If this parameter to True will keep the repair results stable. For example:
        #   case 1:  '{"key": "val\\' => '{"key": "val"}'
        #   case 2:  '{"key": "val\\n' => '{"key": "val\\n"}'
        #   case 3:  '{"key": "val\\n123,`key2:value2' => '{"key": "val\\n123,`key2:value2"}'
        #   case 4:  '{"key": "val\\n123,`key2:value2`"}' => '{"key": "val\\n123,`key2:value2`"}'
        self.stream_stable = stream_stable
        # Over time the library got more and more complex heuristics to repair JSON. Some of these heuristics
        # may not be desirable in some use cases and the user would prefer json_repair to return an exception.
        # So strict mode was added to disable some of those heuristics.
        self.strict = strict
        self.try_valid_json_suffix = try_valid_json_suffix
        self.has_tried_valid_json_suffix = False
        self._last_parse_found_value = False

    def parse(
        self,
    ) -> Any:
        return self._parse_top_level(self.parse_json)



    # Consolidate top-level parsing so we handle multiple sequential JSON values consistently
    # (including update semantics and strict-mode validation).
    def _parse_top_level(self, parse_element: Callable[[], Any]) -> Any:
        json = parse_element()
        if self.index < len(self.json_str):
            self.log(
                "The parser returned early, checking if there's more json elements",
            )
            json = [json]
            while self.index < len(self.json_str):
                self.context.clear()
                self.deferred_contexts.clear()
                is_comma_separated = self._next_top_level_value_is_comma_separated()
                element_start_index = self.index
                j = parse_element()
                if self.strict and self.index > element_start_index:
                    self.log(
                        "Multiple top-level JSON elements found in strict mode, raising an error",
                    )
                    raise ValueError("Multiple top-level JSON elements found in strict mode.")
                if j:
                    if not is_comma_separated and ObjectComparer.is_same_object(json[-1], j):
                        # Treat repeated objects as updates: keep the newest value.
                        json.pop()
                    else:
                        if not json[-1]:
                            json.pop()
                    json.append(j)
                else:
                    self.index += 1
            if len(json) == 1:
                self.log(
                    "There were no more elements, returning the element without the array",
                )
                json = json[0]
        return json

    def _next_top_level_value_is_comma_separated(self) -> bool:
        idx = self.scroll_whitespaces()
        if self.get_char_at(idx) == ",":
            return True

        idx = self.index - 1
        while idx >= 0 and self.json_str[idx].isspace():
            idx -= 1
        return idx >= 0 and self.json_str[idx] == ","

    def _initial_container_has_non_comma_trailing_content(self) -> bool:
        if self.index != 0 or not isinstance(self.json_str, str):
            return True

        containers: list[str] = []
        in_string = False
        escaped = False
        closing_delimiters = {"{": "}", "[": "]"}
        for index, char in enumerate(self.json_str):
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char in closing_delimiters:
                containers.append(char)
            elif char in ["}", "]"]:
                if not containers or char != closing_delimiters[containers.pop()]:
                    return False
                if not containers:
                    trailing_index = index + 1
                    while trailing_index < len(self.json_str) and self.json_str[trailing_index].isspace():
                        trailing_index += 1
                    return trailing_index < len(self.json_str) and self.json_str[trailing_index] != ","

        return False

    def _try_parse_valid_json_value(self) -> tuple[bool, Any]:
        if (
            not self.try_valid_json_suffix
            or self.has_tried_valid_json_suffix
            or not self.context.empty
            or not isinstance(self.json_str, str)
        ):
            return False, ""

        self.has_tried_valid_json_suffix = True
        try:
            value, end_idx = raw_decode(self.json_str[self.index :])
        except (json.JSONDecodeError, OverflowError):
            # Pystachy port: retry integer tokens beyond the native codec's
            # int64 range through parse_number(), which uses promoting ints.
            return False, ""

        self.index += end_idx
        return True, value

    def _try_parse_missing_opening_object(self, delimiter: str) -> tuple[bool, Any]:
        if self.scroll_whitespaces(-self.index) != 0:
            return False, ""

        offset = self.skip_to_character(delimiter, idx=1)
        if self.get_char_at(offset) is None:
            return False, ""

        offset = self.scroll_whitespaces(offset + 1)
        if self.get_char_at(offset) != ":":
            return False, ""

        end_offset = self.scroll_whitespaces(len(self.json_str) - self.index - 1, backwards=True)
        if self.get_char_at(end_offset) != "}":
            return False, ""

        # Require a single insertion to explain the whole input, rather than
        # treating a quoted prose prefix or an inner container as an object.
        candidate = "{" + self.json_str[:]
        try:
            value, end_idx = raw_decode(candidate)
        except ValueError:
            # Decoder limits (such as oversized integers) also mean the
            # insertion is insufficient; leave these inputs to normal repair.
            return False, ""
        if candidate[end_idx:].strip(" \t\r\n"):
            return False, ""

        if self.strict:
            raise ValueError("Missing opening object brace in strict mode.")
        self.log("Inserted missing opening object brace")
        self.index = len(self.json_str)
        return True, value

    def parse_json(
        self,
        schema: dict[str, Any] | bool | None = None,
        path: str = "$",
        finalize_schema: bool = True,
        record_top_level_value: bool = False,
    ) -> Any:
        """Parse the next JSON value (Pystachy port: schema-free)."""
        if record_top_level_value:
            self._last_parse_found_value = False
        if self.deferred_contexts:
            deferred_contexts, self.deferred_contexts = self.deferred_contexts, []
            # Pystachy port: all deferred managers are JsonContext entries.
            # Explicit unwind preserves ExitStack's reverse-order cleanup.
            for context_value in deferred_contexts:
                self.context.set(context_value)
            try:
                return self.parse_json(schema, path, finalize_schema, record_top_level_value)
            finally:
                for context_value in reversed(deferred_contexts):
                    self.context.reset()

        repairer = None  # Pystachy port: schema-free parser.
        check_initial_quote = self.index == 0 and self.context.empty

        while True:
            char = self.get_char_at()
            # None means that we are at the end of the string provided
            if char is None:
                return ""
            if (
                self.try_valid_json_suffix
                and char in ["{", "["]
                and self._initial_container_has_non_comma_trailing_content()
            ):
                parsed_suffix, value = self._try_parse_valid_json_value()
                if parsed_suffix:
                    return self._finalize_parsed_value(
                        value, repairer, schema, path, finalize_schema, record_top_level_value
                    )
            # <object> starts with '{'
            if char == "{":
                self.index += 1
                value = self.parse_object(schema, path) if repairer else self.parse_object()
                return self._finalize_parsed_value(
                    value, repairer, schema, path, finalize_schema, record_top_level_value
                )
            # <array> starts with '['
            if char == "[":
                self.index += 1
                value = self.parse_array(schema, path) if repairer else self.parse_array()
                return self._finalize_parsed_value(
                    value, repairer, schema, path, finalize_schema, record_top_level_value
                )
            # Python tuple literals and grouped values start with '('
            if char == "(":
                # Keep top-level tuple detection conservative so inline prose like
                # "note (clarification):" does not hijack later JSON blocks.
                if not self.context.empty or self.top_level_parenthesized_can_start_value():
                    value = self.parse_parenthesized(schema, path) if repairer else self.parse_parenthesized()
                    return self._finalize_parsed_value(
                        value, repairer, schema, path, finalize_schema, record_top_level_value
                    )
                self.index += 1
                continue
            # <string> starts with a quote
            if not self.context.empty and (char in STRING_DELIMITERS or char.isalpha()):
                value = self.parse_string()
                return self._finalize_parsed_value(
                    value, repairer, schema, path, finalize_schema, record_top_level_value
                )
            # <number> starts with [0-9] or minus
            if not self.context.empty and (char.isdigit() or char == "-" or char == "."):
                value = self.parse_number()
                return self._finalize_parsed_value(
                    value, repairer, schema, path, finalize_schema, record_top_level_value
                )
            if char in ["#", "/"]:
                value = self.parse_comment(record_top_level_value)
                return self._finalize_parsed_value(value, repairer, schema, path, finalize_schema)
            # Only probe a missing brace when normal dispatch would discard the
            # initial quote; later quoted prose must not start this recovery.
            if char in STRING_DELIMITERS and check_initial_quote:
                check_initial_quote = False
                parsed_object, value = self._try_parse_missing_opening_object(char)
                if parsed_object:
                    return self._finalize_parsed_value(
                        value, repairer, schema, path, finalize_schema, record_top_level_value
                    )
            # If everything else fails, we just ignore and move on
            self.index += 1


    def _finalize_parsed_value(
        self,
        value: Any,
        repairer,
        schema: dict[str, Any] | bool | None,
        path: str,
        finalize_schema: bool = True,
        record_top_level_value: bool = False,
    ) -> Any:
        if record_top_level_value:
            self._last_parse_found_value = True
        # Pystachy port: schema-free values need no finalization.
        return value

    def get_char_at(self, count: int = 0) -> str | None:
        # Pystachy port: EOF probes are normal; avoid native exception unwinding.
        index = self.index + count
        if -len(self.json_str) <= index < len(self.json_str):
            return self.json_str[index]
        return None

    def skip_whitespaces(self) -> None:
        """
        This function quickly iterates on whitespaces, moving the self.index forward
        """
        # Preserve Python's negative-index behavior for callers outside parse().
        length = len(self.json_str)
        while -length <= self.index < length and self.json_str[self.index].isspace():
            self.index += 1

    def scroll_whitespaces(self, idx: int = 0, *, backwards: bool = False) -> int:
        """
        Skip whitespace at idx without moving self.index, returning the relative offset.
        Set backwards to scan toward the start.
        """
        step = -1 if backwards else 1
        # Unlike skip_whitespaces(), this scan stops at a negative position.
        while 0 <= self.index + idx < len(self.json_str) and self.json_str[self.index + idx].isspace():
            idx += step
        return idx

    def skip_to_character(self, character: str | list[str], idx: int = 0) -> int:
        """
        Advance from (self.index + idx) until we hit an *unescaped* target character.
        Returns the offset (idx) from self.index to that position, or the distance to the end if not found.
        """
        i = self.index + idx
        n = len(self.json_str)
        # Pystachy port: use native search while preserving upstream escape boundaries.
        if (
            isinstance(self.json_str, str)
            and isinstance(character, str)
            and len(character) == 1
            and character != "\\"
            and i >= 0
        ):
            while i < n:
                match = self.json_str.find(character, i)
                if match < 0:
                    return n - self.index
                preceding = match - 1
                # Preserve the scan's escape boundary when idx starts inside a backslash run.
                while preceding >= i and self.json_str[preceding] == "\\":
                    preceding -= 1
                if (match - preceding - 1) % 2 == 0:
                    return match - self.index
                i = match + 1
            return n - self.index

        targets = set(character) if isinstance(character, list) else {character}
        backslashes = 0  # count of consecutive '\' immediately before current char

        while i < n:
            ch = self.json_str[i]

            if ch == "\\":
                backslashes += 1
                i += 1
                continue

            # ch is not a backslash; if it's a target and not escaped (even backslashes), we're done
            if ch in targets and (backslashes % 2 == 0):
                return i - self.index

            # reset backslash run when we see a non-backslash
            backslashes = 0
            i += 1

        # not found; return distance to end
        return n - self.index

    def parenthesized_is_explicit_tuple(self) -> bool:
        return parenthesized_is_explicit_tuple(self)

    def top_level_parenthesized_can_start_value(self) -> bool:
        return top_level_parenthesized_can_start_value(self)

    def parse_parenthesized(
        self,
        schema: dict[str, Any] | bool | None = None,
        path: str = "$",
    ) -> Any:
        explicit_tuple = self.parenthesized_is_explicit_tuple()
        self.index += 1
        values = self.parse_array(schema, path, closing_delimiter=")")
        if explicit_tuple or len(values) != 1:
            return values
        return values[0]

    def log(self, text: str) -> None:
        # Pystachy port: avoid assigning bound methods/lambdas in __init__.
        if not self.logging:
            return
        window: int = 10
        start: int = max(self.index - window, 0)
        end: int = min(self.index + window, len(self.json_str))
        context: str = self.json_str[start:end]
        self.logger.append(
            {
                "text": text,
                "context": context,
            }
        )
