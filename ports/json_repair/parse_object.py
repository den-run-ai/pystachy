# pystachy: dynamic-any
# Pystachy port: specialize schema-free parsing; recursive values use dynamic Any.
from typing import Any

from .utils.constants import STRING_DELIMITERS
from .utils.json_context import ContextValues

def _strip_comments_for_empty_object_classification(body: str) -> str:
    stripped = []
    in_quote: str | None = None
    backslashes = 0
    index = 0
    while index < len(body):
        char = body[index]
        next_char = body[index + 1] if index + 1 < len(body) else ""

        if char == "\\":
            backslashes += 1
            stripped.append(char)
            index += 1
            continue
        if in_quote is not None:
            stripped.append(char)
            if char == in_quote and backslashes % 2 == 0:
                in_quote = None
            backslashes = 0
            index += 1
            continue
        if char in STRING_DELIMITERS and backslashes % 2 == 0:
            in_quote = char
            stripped.append(char)
            backslashes = 0
            index += 1
            continue
        backslashes = 0

        if char == "#" or (char == "/" and next_char == "/"):
            index += 2 if char == "/" else 1
            while index < len(body) and body[index] not in ["\n", "\r"]:
                index += 1
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index < len(body) - 1 and body[index : index + 2] != "*/":
                index += 1
            index = min(index + 2, len(body))
            continue

        stripped.append(char)
        index += 1

    return "".join(stripped)


def _classify_empty_object_repair(
    self,
    start_index: int,
    schema: dict[str, Any] | bool | None,
) -> tuple[str, str | None]:
    attempted_object = self.json_str[start_index - 1 : self.index + 1]
    body = attempted_object[1:]
    body = body.removesuffix("}")
    body = body.lstrip()
    if not body:
        return "keep", None
    if (body.startswith('\\"') and '\\":' in body) or (body.startswith("\\'") and "\\':" in body):
        normalized_object = attempted_object.replace('\\"', '"').replace("\\'", "'")
        self.log(
            "Parsed object is empty but the input starts like an escaped object key, normalizing and reparsing it as an object",
        )
        return "object", normalized_object
    body = _strip_comments_for_empty_object_classification(body).lstrip()
    if not body:
        return "keep", None

    in_quote: str | None = None
    backslashes = 0
    for char in body:
        if char == "\\":
            backslashes += 1
            continue
        if in_quote is not None:
            if char == in_quote and backslashes % 2 == 0:
                in_quote = None
        elif char in STRING_DELIMITERS and backslashes % 2 == 0:
            in_quote = char
        elif char == ":" and backslashes % 2 == 0:
            self.log(
                "Parsed object is empty but the input still contains an object-style separator, keeping object repair",
            )
            return "keep", None
        backslashes = 0
    return "array", None


def _merge_object_array_continuation(
    self,
    obj: dict[str, Any],
) -> bool:
    prev_key = list(obj.keys())[-1] if obj else None
    if not prev_key or not isinstance(obj[prev_key], list) or self.strict:
        return False

    self.index += 1
    new_array = self.parse_array()
    if isinstance(new_array, list):
        prev_value = obj[prev_key]
        if isinstance(prev_value, list):
            list_lengths = [len(item) for item in prev_value if isinstance(item, list)]
            expected_len = (
                list_lengths[0] if list_lengths and all(length == list_lengths[0] for length in list_lengths) else None
            )
            if expected_len:
                tail = []
                while prev_value and not isinstance(prev_value[-1], list):
                    tail.append(prev_value.pop())
                if tail:
                    tail.reverse()
                    if len(tail) % expected_len == 0:
                        self.log(
                            "While parsing an object we found row values without an inner array, grouping them into rows",
                        )
                        for i in range(0, len(tail), expected_len):
                            prev_value.append(tail[i : i + expected_len])
                    else:
                        prev_value.extend(tail)
                if new_array:
                    if all(isinstance(item, list) for item in new_array):
                        self.log(
                            "While parsing an object we found additional rows, appending them without flattening",
                        )
                        prev_value.extend(new_array)
                    else:
                        prev_value.append(new_array)
            else:
                prev_value.extend(new_array[0] if len(new_array) == 1 and isinstance(new_array[0], list) else new_array)

    self.skip_whitespaces()
    if self.get_char_at() == ",":
        self.index += 1
    self.skip_whitespaces()
    return True


def _parse_object_key(
    self,
    obj: dict[str, Any],
) -> tuple[str, int]:
    key = ""
    rollback_index = self.index
    self.context.set(ContextValues.OBJECT_KEY)
    try:
        while self.get_char_at():
            rollback_index = self.index
            if self.get_char_at() == "[" and key == "" and _merge_object_array_continuation(self, obj):
                continue

            raw_key = self.parse_string()
            assert isinstance(raw_key, str)
            key = raw_key
            if key == "":
                self.skip_whitespaces()
            if key != "" or (key == "" and self.get_char_at() in [":", "}"]):
                if key == "" and self.strict:
                    self.log(
                        "Empty key found in strict mode while parsing object, raising an error",
                    )
                    raise ValueError("Empty key found in strict mode while parsing object.")
                break
    finally:
        self.context.reset()
    return key, rollback_index


def _should_split_duplicate_object(self, rollback_index: int) -> bool:
    lookback_idx = rollback_index - self.index - 1
    prev_non_whitespace = self.get_char_at(lookback_idx)
    while prev_non_whitespace and prev_non_whitespace.isspace():
        lookback_idx -= 1
        prev_non_whitespace = self.get_char_at(lookback_idx)
    key_start_char = self.get_char_at(rollback_index - self.index)
    next_non_whitespace = self.get_char_at(self.scroll_whitespaces())
    return not (key_start_char in STRING_DELIMITERS and prev_non_whitespace == "," and next_non_whitespace == ":")


def _split_object_on_duplicate_key(self, rollback_index: int) -> None:
    self.index = rollback_index - 1
    self.json_str = self.json_str[: self.index + 1] + "{" + self.json_str[self.index + 1 :]


def _parse_object_value(
    self,
) -> Any:
    self.context.set(ContextValues.OBJECT_VALUE)
    try:
        self.skip_whitespaces()
        char = self.get_char_at()
        if char in [",", "}"]:
            self.log(
                f"While parsing an object value we found a stray {char}, ignoring it",
            )
            return ""

        return self.parse_json()
    finally:
        self.context.reset()


def _repair_empty_object_result(
    self,
    obj: dict[str, Any],
    start_index: int,
    schema: dict[str, Any] | bool | None,
    path: str,
) -> tuple[bool, Any]:
    if obj or self.index - start_index <= 2:
        return False, None

    if self.strict:
        self.log(
            "Parsed object is empty but contains extra characters in strict mode, raising an error",
        )
        raise ValueError("Parsed object is empty but contains extra characters in strict mode.")

    empty_object_repair, normalized_object = _classify_empty_object_repair(self, start_index, schema)
    if empty_object_repair == "object" and normalized_object is not None:
        end_index = self.index + 1
        self.json_str = self.json_str[: start_index - 1] + normalized_object + self.json_str[end_index:]
        self.index = start_index
        with self.context.enter(ContextValues.OBJECT_KEY):
            repaired_value = self.parse_object(schema, path)
        self.deferred_contexts.append(ContextValues.OBJECT_KEY)
        return True, repaired_value
    if empty_object_repair == "array":
        self.log("Parsed object is empty, we will try to parse this as an array instead")
        self.index = start_index
        with self.context.enter(ContextValues.OBJECT_KEY):
            repaired_array = self.parse_array()
        self.deferred_contexts.append(ContextValues.OBJECT_KEY)
        return True, repaired_array
    return False, None


def _complete_object_parse(
    self,
    obj: dict[str, Any],
    schema: dict[str, Any] | bool | None,
    path: str,
) -> Any:
    if not self.context.empty:
        if self.get_char_at() == "}" and self.context.current not in [
            ContextValues.OBJECT_KEY,
            ContextValues.OBJECT_VALUE,
        ]:
            self.log(
                "Found an extra closing brace that shouldn't be there, skipping it",
            )
            self.index += 1
        return obj

    self.skip_whitespaces()
    if self.get_char_at() == ",":
        self.index += 1
        self.skip_whitespaces()
        if self.get_char_at() in STRING_DELIMITERS and not self.strict:
            self.log(
                "Found a comma and string delimiter after object closing brace, checking for additional key-value pairs",
            )
            additional_obj = self.parse_object(schema, path)
            if isinstance(additional_obj, dict):
                obj.update(additional_obj)

    return obj


def parse_object(
    self,
    schema: dict[str, Any] | bool | None = None,
    path: str = "$",
) -> Any:
    # <object> ::= '{' [ <member> *(', ' <member>) ] '}' ; A sequence of 'members'
    obj: dict[str, Any] = {}
    start_index = self.index
    parsing_object_value = self.context.current == ContextValues.OBJECT_VALUE
    # Pystachy port: the public entry point rejects schemas.
    if schema is not None:
        raise ValueError("This port supports schema-free repair only.")

    while (self.get_char_at() or "}") != "}":
        self.skip_whitespaces()

        if self.get_char_at() == ":":
            self.log(
                "While parsing an object we found a : before a key, ignoring",
            )
            self.index += 1

        key, rollback_index = _parse_object_key(self, obj)
        if ContextValues.ARRAY in self.context.context and key in obj:
            if self.strict:
                self.log("Duplicate key found in strict mode while parsing object, raising an error")
                raise ValueError("Duplicate key found in strict mode while parsing object.")
            if not parsing_object_value:
                if _should_split_duplicate_object(self, rollback_index):
                    self.log(
                        "While parsing an object we found a duplicate key, closing the object here and rolling back the index",
                    )
                    _split_object_on_duplicate_key(self, rollback_index)
                    break
                self.log(
                    "While parsing an object we found a duplicate key with a normal comma separator, keeping duplicate-key overwrite behavior",
                )

        self.skip_whitespaces()
        if (self.get_char_at() or "}") == "}":
            continue

        self.skip_whitespaces()
        if self.get_char_at() != ":":
            if self.strict:
                self.log(
                    "Missing ':' after key in strict mode while parsing object, raising an error",
                )
                raise ValueError("Missing ':' after key in strict mode while parsing object.")
            self.log(
                "While parsing an object we missed a : after a key",
            )

        self.index += 1
        value = _parse_object_value(self)

        if value == "" and self.strict and self.get_char_at(-1) not in STRING_DELIMITERS:
            self.log(
                "Parsed value is empty in strict mode while parsing object, raising an error",
            )
            raise ValueError("Parsed value is empty in strict mode while parsing object.")

        obj[key] = value

        if self.get_char_at() in [",", "'", '"']:
            self.index += 1
        if self.get_char_at() == "]" and ContextValues.ARRAY in self.context.context:
            self.log(
                "While parsing an object we found a closing array bracket, closing the object here and rolling back the index"
            )
            self.index -= 1
            break
        self.skip_whitespaces()

    self.index += 1

    repaired_empty_object, repaired_value = _repair_empty_object_result(
        self,
        obj,
        start_index,
        schema,
        path,
    )
    if repaired_empty_object:
        return repaired_value

    return _complete_object_parse(
        self,
        obj,
        schema,
        path,
    )
