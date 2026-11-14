# pystachy: dynamic-any
# pystachy: python-int
"""Validators for JSON Schema drafts 4, 6, 7, 2019-09 and 2020-12.

Pystachy port: this follows jsonschema 4.26 (validators.py, _keywords.py, _legacy_keywords.py,
_utils.py, _types.py; MIT, Julian Berman), keyword by keyword: what each accepts, the order in
which a schema's keywords are tried, and each message. A validator reports the first error that
jsonschema's Validator.iter_errors() yields, which is all that json_repair reads.

Left out, each failing with an exception and none silently accepted:
- references other than "#" and "#/..." to the root schema (anchors, other documents, a
  reference inside a subschema that has its own $id): _WrappedReferencingError;
- draft 3: SchemaError from check_schema().
A format is asserted only while a schema is checked against its metaschema, and only "regex",
as with jsonschema installed alone.
"""
import json
import math
import re
from typing import Any

from ._metaschemas import METASCHEMAS
from .exceptions import PointerToNowhere, SchemaError, UnknownType, Unresolvable, ValidationError, _WrappedReferencingError

LATEST = 2020
_DRAFTS = {
    "http://json-schema.org/draft-03/schema": 3,
    "http://json-schema.org/draft-04/schema": 4,
    "http://json-schema.org/draft-06/schema": 6,
    "http://json-schema.org/draft-07/schema": 7,
    "https://json-schema.org/draft/2019-09/schema": 2019,
    "https://json-schema.org/draft/2020-12/schema": 2020,
}
_parsed: dict[int, Any] = {}
_dialects: dict[int, "Dialect"] = {}


def _normalized(uri: str) -> str:
    # as urlsplit(uri).geturl() normalizes a metaschema's URI: a lower-case scheme, no empty fragment
    scheme, colon, rest = uri.partition(":")
    if colon and scheme.isalpha():
        uri = scheme.lower() + colon + rest
    if uri.endswith("#"):
        uri = uri[:-1]
    return uri


def _draft_of(schema: Any, default: int) -> int:
    if not isinstance(schema, dict) or "$schema" not in schema:
        return default
    uri = schema["$schema"]
    if not isinstance(uri, str):
        return default
    draft = _DRAFTS.get(_normalized(uri), default)
    if draft == 3:
        raise SchemaError("Draft 3 schemas are not supported.")
    return draft


def _search(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def _is_regex(pattern: str) -> bool:
    try:
        re.compile(pattern)
    except re.error:
        return False
    return True


def _is_type(instance: Any, name: str, draft: int) -> bool:
    if name == "object":
        return isinstance(instance, dict)
    if name == "array":
        return isinstance(instance, list)
    if name == "string":
        return isinstance(instance, str)
    if name == "boolean":
        return isinstance(instance, bool)
    if name == "null":
        return instance is None
    if isinstance(instance, bool):
        return False
    if name == "number":
        return isinstance(instance, (int, float))
    if name == "integer":
        if isinstance(instance, int):
            return True
        return draft >= 6 and isinstance(instance, float) and instance.is_integer()
    raise UnknownType(f"Type {name!r} is unknown to this type checker")


def _equal(one: Any, two: Any) -> bool:
    # equality that tells True from 1 and False from 0, also inside arrays and objects
    if isinstance(one, str) or isinstance(two, str):
        return bool(one == two)
    if isinstance(one, list) and isinstance(two, list):
        if len(one) != len(two):
            return False
        for index in range(len(one)):
            if not _equal(one[index], two[index]):
                return False
        return True
    if isinstance(one, dict) and isinstance(two, dict):
        if len(one) != len(two):
            return False
        for key, value in one.items():
            if key not in two or not _equal(value, two[key]):
                return False
        return True
    if isinstance(one, bool) or isinstance(two, bool):
        return isinstance(one, bool) and isinstance(two, bool) and bool(one == two)
    return bool(one == two)


def _unique(container: Any) -> bool:
    # jsonschema sorts and compares neighbours, and compares every pair where the elements do not
    # sort: its stand-ins for True and False never do
    pairwise = False
    if len(container) > 1:
        for each in container:
            if isinstance(each, bool):
                pairwise = True
                break
    if not pairwise:
        try:
            ordered = sorted(container)
            for index in range(1, len(ordered)):
                if _equal(ordered[index - 1], ordered[index]):
                    return False
        except TypeError:
            pairwise = True
    if pairwise:
        for index in range(len(container)):
            for earlier in range(index):
                if _equal(container[earlier], container[index]):
                    return False
    return True


def _odd(number: float) -> int:
    # the odd integer that number is a power of two times
    mantissa, _ = math.frexp(number)
    whole = int(abs(mantissa) * 9007199254740992.0)
    while whole > 0 and whole % 2 == 0:
        whole //= 2
    return whole


def _extras(extras: list[Any]) -> str:
    verb = "was" if len(extras) == 1 else "were"
    return ", ".join([repr(extra) for extra in extras]) + " " + verb


def _additional_properties(instance: Any, schema: Any) -> list[Any]:
    properties = schema.get("properties", {})
    patterns = "|".join(schema.get("patternProperties", {}))
    extras: list[Any] = []
    for name in instance:
        if name not in properties:
            if patterns and _search(patterns, name):
                continue
            extras.append(name)
    return extras


def _has_id(schema: Any, draft: int) -> bool:
    # does a subschema start a resource of its own, against which its references resolve
    if not isinstance(schema, dict):
        return False
    if draft >= 2019:
        return isinstance(schema.get("$id"), str)
    if "$ref" in schema:
        return False
    name = schema.get("id" if draft == 4 else "$id")
    return isinstance(name, str) and not name.startswith("#")


def _unquoted(text: str) -> str:
    # urllib.parse.unquote(): %XX is a byte of UTF-8, and what is no UTF-8 a replacement character
    if "%" not in text:
        return text
    out: list[int] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "%" and _is_hex(text[index + 1 : index + 3]):
            out.append(int(text[index + 1 : index + 3], 16))
            index += 3
        else:
            for byte in char.encode("utf-8"):
                out.append(byte)
            index += 1
    return bytes(out).decode("utf-8", "replace")


def _is_hex(pair: str) -> bool:
    if len(pair) != 2:
        return False
    for char in pair:
        if char not in "0123456789abcdefABCDEF":
            return False
    return True


def _more(errors: list[str], found: list[str], full: bool) -> bool:
    """Add what a subschema or keyword found. Whether that ends the evaluation: an error, where
    only the first is wanted."""
    if found:
        errors.extend(found)
        return not full
    return False


def _metaschema(draft: int) -> Any:
    parsed = _parsed.get(draft)
    if parsed is None:
        parsed = json.loads(METASCHEMAS[draft])
        _parsed[draft] = parsed
    return parsed


class Validator:
    def __init__(self, schema: Any, draft: int, root: Any, formats: bool = False) -> None:
        self.schema = schema
        self._draft = draft
        self._root = root
        self._formats = formats

    def evolve(self, schema: Any) -> "Validator":
        return Validator(schema, _draft_of(schema, self._draft), self._root, self._formats)

    def is_valid(self, instance: Any) -> bool:
        return not self._errors(instance, self.schema, self._draft, self._draft, False, False)

    def validate(self, instance: Any) -> None:
        errors = self._errors(instance, self.schema, self._draft, self._draft, False, False)
        if errors:
            raise ValidationError(errors[0])

    def _valid(self, instance: Any, schema: Any, draft: int, embedded: bool) -> bool:
        # evolve(schema=schema).is_valid(instance)
        child = _draft_of(schema, draft)
        return not self._errors(instance, schema, child, child, embedded, False)

    def _descend(self, instance: Any, schema: Any, draft: int, embedded: bool, full: bool) -> list[str]:
        if schema is True:
            return []
        if schema is False:
            return [f"False schema does not allow {instance!r}"]
        return self._errors(instance, schema, draft, _draft_of(schema, draft), embedded or _has_id(schema, draft), full)

    def _errors(self, instance: Any, schema: Any, siblings: int, draft: int, embedded: bool, full: bool) -> list[str]:
        """The errors of instance under schema, in jsonschema's order: all of them with full (as
        where jsonschema lists a subschema's errors, so that what raises there, raises here),
        else the first only. The draft that decides whether $ref hides its siblings is the
        enclosing schema's."""
        if schema is True:
            return []
        if schema is False:
            return [f"False schema does not allow {instance!r}"]
        if siblings < 2019:
            ref = schema.get("$ref")
            if ref is not None:
                return self._reference(ref, instance, draft, embedded, full)
        errors: list[str] = []
        for keyword, value in schema.items():
            if _more(errors, self._keyword(keyword, value, instance, schema, draft, embedded, full), full):
                return errors
        return errors

    def _resolve(self, ref: Any, draft: int, embedded: bool, wrapped: bool = True) -> tuple[Any, bool]:
        """What a reference names in the root schema, and whether that is inside a subschema with
        an $id of its own. A keyword's failure is jsonschema's wrapped error; the search for
        evaluated properties and items raises referencing's own."""
        if not isinstance(ref, str):
            raise AttributeError(f"{type(ref).__name__!r} object has no attribute 'startswith'")
        uri, _, fragment = ref.partition("#")
        root = self._root
        local = not embedded and (not fragment or fragment.startswith("/"))
        if local and uri:
            name = root.get("id" if draft == 4 else "$id") if isinstance(root, dict) else None
            local = isinstance(name, str) and _normalized(name) == uri
        if not local:
            if wrapped:
                raise _WrappedReferencingError(f"Unresolvable: {ref}")
            raise Unresolvable(ref)
        if not fragment:
            return root, False
        contents = root
        for segment in _unquoted(fragment[1:]).split("/"):
            found = True
            if isinstance(contents, list):
                index = int(segment)
                found = -len(contents) <= index < len(contents)
                if found:
                    contents = contents[index]
            else:
                segment = segment.replace("~1", "/").replace("~0", "~")
                if not isinstance(contents, dict):
                    raise TypeError(f"{type(contents).__name__!r} object is not subscriptable")
                found = segment in contents
                if found:
                    contents = contents[segment]
            if not found:
                message = f"{fragment!r} does not exist within {root!r}"
                if fragment == "/":
                    message += (". The pointer '/' is a valid JSON Pointer but it points to an empty string property"
                                " ''. If you intended to point to the entire resource, you should use '#'.")
                if wrapped:
                    raise _WrappedReferencingError("PointerToNowhere: " + message)
                raise PointerToNowhere(message)
            if _has_id(contents, draft):
                embedded = True
        return contents, embedded

    def _reference(self, ref: Any, instance: Any, draft: int, embedded: bool, full: bool) -> list[str]:
        contents, embedded = self._resolve(ref, draft, embedded)
        if contents is True:
            return []
        if contents is False:
            return [f"False schema does not allow {instance!r}"]
        return self._errors(instance, contents, draft, _draft_of(contents, draft), embedded, full)

    def _each(self, instance: Any, schemas: Any, draft: int, embedded: bool, full: bool) -> list[str]:
        # allOf
        errors: list[str] = []
        for subschema in schemas:
            if _more(errors, self._descend(instance, subschema, draft, embedded, full), full):
                return errors
        return errors

    def _keyword(self, keyword: str, value: Any, instance: Any, schema: Any, draft: int, embedded: bool,
                 full: bool) -> list[str]:
        """The errors of one keyword of a schema. A keyword that the draft does not define, as
        any other name in a schema, has none: each draft's own are those of jsonschema's
        validator for it."""
        errors: list[str] = []
        if keyword == "type":
            types: Any = value
            if isinstance(value, str):
                types = [value]
            for name in types:
                if _is_type(instance, name, draft):
                    return []
            reprs = ", ".join([repr(name) for name in types])
            return [f"{instance!r} is not of type {reprs}"]
        if keyword == "properties":
            return self._properties(value, instance, draft, embedded, full)
        if keyword == "required":
            if not isinstance(instance, dict):
                return []
            for name in value:
                if name not in instance and _more(errors, [f"{name!r} is a required property"], full):
                    break
            return errors
        if keyword == "$ref" or (keyword == "$dynamicRef" and draft == 2020):
            return self._reference(value, instance, draft, embedded, full)
        if keyword == "$recursiveRef" and draft == 2019:
            return self._reference("#", instance, draft, embedded, full)
        if keyword == "items":
            return self._items(value, instance, schema, draft, embedded, full)
        if keyword == "enum":
            for each in value:
                if _equal(each, instance):
                    return []
            return [f"{instance!r} is not one of {value!r}"]
        if keyword == "const" and draft >= 6:
            if not _equal(instance, value):
                return [f"{value!r} was expected"]
            return []
        if keyword == "additionalProperties":
            return self._additional(value, instance, schema, draft, embedded, full)
        if keyword == "allOf":
            return self._each(instance, value, draft, embedded, full)
        if keyword == "anyOf":
            for subschema in value:
                if not self._descend(instance, subschema, draft, embedded, True):
                    return []
            return [f"{instance!r} is not valid under any of the given schemas"]
        if keyword == "oneOf":
            return self._one_of(value, instance, draft, embedded)
        if keyword == "not":
            if self._valid(instance, value, draft, embedded):
                return [f"{instance!r} should not be valid under {value!r}"]
            return []
        if keyword == "if" and draft >= 7:
            if self._valid(instance, value, draft, embedded):
                if "then" in schema:
                    return self._descend(instance, schema["then"], draft, embedded, full)
            elif "else" in schema:
                return self._descend(instance, schema["else"], draft, embedded, full)
            return []
        if keyword == "minimum" or keyword == "maximum":
            return self._bound(keyword, value, instance, schema, draft)
        if keyword == "exclusiveMinimum":  # (in draft 4 it is minimum's flag)
            if draft >= 6 and _is_type(instance, "number", draft) and instance <= value:
                return [f"{instance!r} is less than or equal to the minimum of {value!r}"]
            return []
        if keyword == "exclusiveMaximum":
            if draft >= 6 and _is_type(instance, "number", draft) and instance >= value:
                return [f"{instance!r} is greater than or equal to the maximum of {value!r}"]
            return []
        if keyword == "multipleOf":
            return self._multiple(value, instance, draft)
        if keyword == "minLength":
            if isinstance(instance, str) and len(instance) < value:
                return [f"{instance!r} " + ("should be non-empty" if value == 1 else "is too short")]
            return []
        if keyword == "maxLength":
            if isinstance(instance, str) and len(instance) > value:
                return [f"{instance!r} " + ("is expected to be empty" if value == 0 else "is too long")]
            return []
        if keyword == "pattern":
            if isinstance(instance, str) and not _search(value, instance):
                return [f"{instance!r} does not match {value!r}"]
            return []
        if keyword == "format":
            if self._formats and value == "regex" and isinstance(instance, str) and not _is_regex(instance):
                return [f"{instance!r} is not a {value!r}"]
            return []
        if keyword == "minItems":
            if isinstance(instance, list) and len(instance) < value:
                return [f"{instance!r} " + ("should be non-empty" if value == 1 else "is too short")]
            return []
        if keyword == "maxItems":
            if isinstance(instance, list) and len(instance) > value:
                return [f"{instance!r} " + ("is expected to be empty" if value == 0 else "is too long")]
            return []
        if keyword == "uniqueItems":
            if value and isinstance(instance, list) and not _unique(instance):
                return [f"{instance!r} has non-unique elements"]
            return []
        if keyword == "prefixItems" and draft == 2020:
            if not isinstance(instance, list):
                return []
            for index in range(min(len(instance), len(value))):
                if _more(errors, self._descend(instance[index], value[index], draft, embedded, full), full):
                    return errors
            return errors
        if keyword == "additionalItems" and draft < 2020:
            return self._additional_items(value, instance, schema, draft, embedded, full)
        if keyword == "contains" and draft >= 6:
            return self._contains(value, instance, schema, draft, embedded)
        if keyword == "minProperties":
            if isinstance(instance, dict) and len(instance) < value:
                return [f"{instance!r} " + ("should be non-empty" if value == 1 else "does not have enough properties")]
            return []
        if keyword == "maxProperties":
            if isinstance(instance, dict) and len(instance) > value:
                return [f"{instance!r} " + ("is expected to be empty" if value == 0 else "has too many properties")]
            return []
        if keyword == "patternProperties":
            return self._pattern_properties(value, instance, draft, embedded, full)
        if keyword == "propertyNames" and draft >= 6:
            if not isinstance(instance, dict):
                return []
            for name in instance:
                if _more(errors, self._descend(name, value, draft, embedded, full), full):
                    return errors
            return errors
        if keyword == "dependencies" and draft < 2019:
            return self._dependencies(value, instance, draft, embedded, full, True, True)
        if draft < 2019:
            return []
        if keyword == "dependentRequired":
            return self._dependencies(value, instance, draft, embedded, full, True, False)
        if keyword == "dependentSchemas":
            return self._dependencies(value, instance, draft, embedded, full, False, True)
        if keyword == "unevaluatedProperties":
            return self._unevaluated_properties(value, instance, schema, draft, embedded)
        if keyword == "unevaluatedItems":
            if not isinstance(instance, list):
                return []
            evaluated = self._evaluated_items(instance, schema, draft, embedded)
            unevaluated = [instance[index] for index in range(len(instance)) if index not in evaluated]
            if unevaluated:
                return ["Unevaluated items are not allowed (" + _extras(unevaluated) + " unexpected)"]
            return []
        return []

    def _properties(self, properties: Any, instance: Any, draft: int, embedded: bool, full: bool) -> list[str]:
        if not isinstance(instance, dict):
            return []
        errors: list[str] = []
        for name, subschema in properties.items():
            if name in instance:
                if _more(errors, self._descend(instance[name], subschema, draft, embedded, full), full):
                    return errors
        return errors

    def _pattern_properties(self, patterns: Any, instance: Any, draft: int, embedded: bool, full: bool) -> list[str]:
        if not isinstance(instance, dict):
            return []
        errors: list[str] = []
        for pattern, subschema in patterns.items():
            for name, value in instance.items():
                if _search(pattern, name):
                    if _more(errors, self._descend(value, subschema, draft, embedded, full), full):
                        return errors
        return errors

    def _additional(self, allowed: Any, instance: Any, schema: Any, draft: int, embedded: bool,
                    full: bool) -> list[str]:
        if not isinstance(instance, dict):
            return []
        extras = _additional_properties(instance, schema)
        if isinstance(allowed, dict):
            # (jsonschema tries these in the order of a set of names; here, in the instance's)
            errors: list[str] = []
            for name in extras:
                if _more(errors, self._descend(instance[name], allowed, draft, embedded, full), full):
                    return errors
            return errors
        if not allowed and extras:
            if "patternProperties" in schema:
                verb = "does" if len(extras) == 1 else "do"
                joined = ", ".join([repr(each) for each in sorted(extras)])
                patterns = ", ".join([repr(each) for each in sorted(schema["patternProperties"])])
                return [f"{joined} {verb} not match any of the regexes: {patterns}"]
            return ["Additional properties are not allowed (" + _extras(sorted(extras)) + " unexpected)"]
        return []

    def _items(self, items: Any, instance: Any, schema: Any, draft: int, embedded: bool, full: bool) -> list[str]:
        if not isinstance(instance, list):
            return []
        errors: list[str] = []
        start = 0
        stop = len(instance)
        if draft == 2020:
            prefix = len(schema.get("prefixItems", []))
            extra = len(instance) - prefix
            if extra <= 0:
                return []
            if items is False:
                rest = instance[prefix:] if extra != 1 else instance[prefix]
                noun = "items" if prefix != 1 else "item"
                return [f"Expected at most {prefix} {noun} but found {extra} extra: {rest!r}"]
            start = prefix
        elif isinstance(items, list) if draft >= 6 else not isinstance(items, dict):
            # one schema for each position (drafts 3 and 4 take anything but an object so)
            for index in range(min(len(instance), len(items))):
                if _more(errors, self._descend(instance[index], items[index], draft, embedded, full), full):
                    return errors
            return errors
        for index in range(start, stop):
            if _more(errors, self._descend(instance[index], items, draft, embedded, full), full):
                return errors
        return errors

    def _additional_items(self, allowed: Any, instance: Any, schema: Any, draft: int, embedded: bool,
                          full: bool) -> list[str]:
        if not isinstance(instance, list) or isinstance(schema.get("items", {}), dict):
            return []
        count = len(schema.get("items", []))
        if isinstance(allowed, dict):
            errors: list[str] = []
            for index in range(count, len(instance)):
                if _more(errors, self._descend(instance[index], allowed, draft, embedded, full), full):
                    return errors
            return errors
        if not allowed and len(instance) > count:
            return ["Additional items are not allowed (" + _extras(instance[count:]) + " unexpected)"]
        return []

    def _contains(self, contains: Any, instance: Any, schema: Any, draft: int, embedded: bool) -> list[str]:
        if not isinstance(instance, list):
            return []
        if draft < 2019:
            for each in instance:
                if self._valid(each, contains, draft, embedded):
                    return []
            return [f"None of {instance!r} are valid under the given schema"]
        matches = 0
        least = schema.get("minContains", 1)
        most = schema.get("maxContains", len(instance))
        for each in instance:
            if self._valid(each, contains, draft, embedded):
                matches += 1
                if matches > most:
                    return [f"Too many items match the given schema (expected at most {most})"]
        if matches < least:
            if not matches:
                return [f"{instance!r} does not contain items matching the given schema"]
            return [f"Too few items match the given schema (expected at least {least} but only {matches} matched)"]
        return []

    def _one_of(self, schemas: Any, instance: Any, draft: int, embedded: bool) -> list[str]:
        valid = -1
        for index in range(len(schemas)):
            if not self._descend(instance, schemas[index], draft, embedded, True):
                valid = index
                break
        if valid < 0:
            return [f"{instance!r} is not valid under any of the given schemas"]
        more = [schemas[index] for index in range(valid + 1, len(schemas))
                if self._valid(instance, schemas[index], draft, embedded)]
        if more:
            more.append(schemas[valid])
            reprs = ", ".join([repr(each) for each in more])
            return [f"{instance!r} is valid under each of {reprs}"]
        return []

    def _bound(self, keyword: str, bound: Any, instance: Any, schema: Any, draft: int) -> list[str]:
        if not _is_type(instance, "number", draft):
            return []
        least = keyword == "minimum"
        exclusive = draft == 4 and bool(schema.get("exclusiveMinimum" if least else "exclusiveMaximum", False))
        if least:
            if (instance <= bound) if exclusive else (instance < bound):
                return [f"{instance!r} is less than" + (" or equal to" if exclusive else "") + f" the minimum of {bound!r}"]
        elif (instance >= bound) if exclusive else (instance > bound):
            return [f"{instance!r} is greater than" + (" or equal to" if exclusive else "") + f" the maximum of {bound!r}"]
        return []

    def _multiple(self, divisor: Any, instance: Any, draft: int) -> list[str]:
        if not _is_type(instance, "number", draft):
            return []
        if isinstance(divisor, float):
            quotient = instance / divisor
            try:
                failed = int(quotient) != quotient
            except OverflowError:
                # An infinite quotient: exactly, as jsonschema does with fractions. The divisor is an
                # odd number over a power of two that the instance has to spare, so it divides the
                # instance where that odd number divides the instance's own odd part.
                odd = _odd(divisor)
                failed = bool((_odd(instance) if isinstance(instance, float) else instance) % odd)
        else:
            failed = bool(instance % divisor)
        if failed:
            return [f"{instance!r} is not a multiple of {divisor}"]
        return []

    def _dependencies(self, dependencies: Any, instance: Any, draft: int, embedded: bool, full: bool, names: bool,
                      schemas: bool) -> list[str]:
        # dependentRequired (names), dependentSchemas (schemas), and the dependencies of drafts 4 to 7 (either)
        if not isinstance(instance, dict):
            return []
        errors: list[str] = []
        for name, dependency in dependencies.items():
            if name not in instance:
                continue
            found: list[str] = []
            if names and (not schemas or isinstance(dependency, list)):
                for each in dependency:
                    if each not in instance:
                        found.append(f"{each!r} is a dependency of {name!r}")
            else:
                found = self._descend(instance, dependency, draft, embedded, full)
            if _more(errors, found, full):
                return errors
        return errors

    def _unevaluated_properties(self, allowed: Any, instance: Any, schema: Any, draft: int,
                                embedded: bool) -> list[str]:
        if not isinstance(instance, dict):
            return []
        evaluated = self._evaluated_properties(instance, schema, draft, embedded)
        unevaluated: list[Any] = []
        for name in instance:
            if name not in evaluated:
                # (once for each error, as jsonschema lists them)
                for _ in self._descend(instance[name], allowed, draft, embedded, True):
                    unevaluated.append(name)
        if not unevaluated:
            return []
        if allowed is False:
            return ["Unevaluated properties are not allowed (" + _extras(sorted(unevaluated)) + " unexpected)"]
        return ["Unevaluated properties are not valid under the given schema (" + _extras(unevaluated)
                + " unevaluated and invalid)"]

    def _evaluated_properties(self, instance: Any, schema: Any, draft: int, embedded: bool) -> list[str]:
        if isinstance(schema, bool):
            return []
        evaluated: list[str] = []
        for keyword in ("$ref", "$dynamicRef") if draft == 2020 else ("$ref", "$recursiveRef"):
            if keyword == "$recursiveRef":
                ref = "#" if keyword in schema else None
            else:
                ref = schema.get(keyword)
            if ref is not None:
                contents, inside = self._resolve(ref, draft, embedded, False)
                evaluated += self._evaluated_properties(instance, contents, _draft_of(contents, draft), inside)
        if draft == 2020:
            properties = schema.get("properties")
            if isinstance(properties, dict):
                evaluated += [name for name in properties if name in instance]
            for keyword in ("additionalProperties", "unevaluatedProperties"):
                subschema = schema.get(keyword)
                if subschema is None:
                    continue
                for name, value in instance.items():
                    if not self._descend(value, subschema, draft, embedded, False):
                        evaluated.append(name)
        else:
            for keyword in ("properties", "additionalProperties", "unevaluatedProperties"):
                if keyword in schema:
                    value = schema[keyword]
                    if isinstance(value, bool) and value:
                        evaluated += list(instance)
                    elif isinstance(value, dict):
                        evaluated += [name for name in value if name in instance]
        if "patternProperties" in schema:
            for name in instance:
                for pattern in schema["patternProperties"]:
                    if _search(pattern, name):
                        evaluated.append(name)
        if "dependentSchemas" in schema:
            for name, subschema in schema["dependentSchemas"].items():
                if name in instance:
                    evaluated += self._evaluated_properties(instance, subschema, draft, embedded)
        for keyword in ("allOf", "oneOf", "anyOf"):
            for subschema in schema.get(keyword, []):
                if not self._descend(instance, subschema, draft, embedded, False):
                    evaluated += self._evaluated_properties(instance, subschema, draft, embedded)
        if "if" in schema:
            if self._valid(instance, schema["if"], draft, embedded):
                evaluated += self._evaluated_properties(instance, schema["if"], draft, embedded)
                if "then" in schema:
                    evaluated += self._evaluated_properties(instance, schema["then"], draft, embedded)
            elif "else" in schema:
                evaluated += self._evaluated_properties(instance, schema["else"], draft, embedded)
        return evaluated

    def _evaluated_items(self, instance: Any, schema: Any, draft: int, embedded: bool) -> list[int]:
        if isinstance(schema, bool):
            return []
        evaluated: list[int] = []
        if draft == 2020 and "items" in schema:
            return list(range(len(instance)))
        for keyword in ("$ref", "$dynamicRef") if draft == 2020 else ("$ref", "$recursiveRef"):
            if keyword == "$recursiveRef":
                ref = "#" if keyword in schema else None
            else:
                ref = schema.get(keyword)
            if ref is not None:
                contents, inside = self._resolve(ref, draft, embedded, False)
                evaluated += self._evaluated_items(instance, contents, _draft_of(contents, draft), inside)
        if draft == 2020:
            if "prefixItems" in schema:
                evaluated += list(range(len(schema["prefixItems"])))
        elif "items" in schema:
            if "additionalItems" in schema or isinstance(schema["items"], dict):
                return list(range(len(instance)))
            evaluated += list(range(len(schema["items"])))
        if "if" in schema:
            if self._valid(instance, schema["if"], draft, embedded):
                evaluated += self._evaluated_items(instance, schema["if"], draft, embedded)
                if "then" in schema:
                    evaluated += self._evaluated_items(instance, schema["then"], draft, embedded)
            elif "else" in schema:
                evaluated += self._evaluated_items(instance, schema["else"], draft, embedded)
        for keyword in ("contains", "unevaluatedItems"):
            if keyword in schema:
                for index in range(len(instance)):
                    if self._valid(instance[index], schema[keyword], draft, embedded):
                        evaluated.append(index)
        for keyword in ("allOf", "oneOf", "anyOf"):
            if keyword in schema:
                for subschema in schema[keyword]:
                    if not self._descend(instance, subschema, draft, embedded, False):
                        evaluated += self._evaluated_items(instance, subschema, draft, embedded)
        return evaluated


class Dialect:
    """What jsonschema.validators.validator_for() returns: called with a schema, a validator."""

    def __init__(self, draft: int) -> None:
        self.draft = draft

    def __call__(self, schema: Any) -> Validator:
        return Validator(schema, self.draft, schema)

    def check_schema(self, schema: Any) -> None:
        if self.draft == 3:
            raise SchemaError("Draft 3 schemas are not supported.")
        metaschema = _metaschema(self.draft)
        errors = Validator(metaschema, self.draft, metaschema, True)._errors(
            schema, metaschema, self.draft, self.draft, False, False
        )
        if errors:
            raise SchemaError(errors[0])


def validator_for(schema: Any) -> Dialect:
    draft = LATEST
    if isinstance(schema, dict) and isinstance(schema.get("$schema"), str):
        draft = _DRAFTS.get(_normalized(schema["$schema"]), LATEST)
    dialect = _dialects.get(draft)
    if dialect is None:
        dialect = Dialect(draft)
        _dialects[draft] = dialect
    return dialect
