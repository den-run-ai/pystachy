# pystachy: dynamic-any
"""Original qualification cases for the maintained json_repair port.

The parser returns recursive JSON values and repair logs, so these open payloads
use its existing explicit Any contract. Parameters and runner state stay typed.
These cases supplement, rather than replace, the 943-case upstream replay.
"""

from typing import Any

from json_repair import loads, repair_json
import pytest


@pytest.mark.parametrize("source,expected", [
    ('{name: "café", active: true,}', '{"name": "café", "active": true}'),
    ('prefix {"items":[1,2,]} suffix', '{"items": [1, 2]}'),
    ('[1, /* retained item */ 2]', '[1, 2]'),
    ('{界: "é",}', '{"界": "é"}'),
    ('[1e, 2]', '[1, 2]'),
])
def test_repaired_serialization(source: str, expected: str):
    actual: Any = repair_json(source, ensure_ascii=False)
    assert isinstance(actual, str)
    assert actual == expected


@pytest.mark.parametrize("source,expected", [
    ('null', 'null'),
    ('false', 'false'),
    ('0', '0'),
    ('1.5', '1.5'),
    ('""', '""'),
    ('"\\ud83d\\ude00"', '"😀"'),
])
def test_valid_scalar_fast_path(source: str, expected: str):
    assert repair_json(source, ensure_ascii=False) == expected


@pytest.mark.parametrize("source,message", [
    ('[1e, 2]', 'Dangling exponent in strict mode'),
    ('{"count":1,,"next":2}', 'Consecutive commas after an object number'),
])
def test_strict_repair_error(source: str, message: str):
    with pytest.raises(ValueError, match=message):
        loads(source, strict=True)


@pytest.fixture
def repaired_document() -> Any:
    return loads('{tool: "search", arguments: [true, null, 3,],}')


@pytest.fixture
def repaired_alias(repaired_document: Any) -> Any:
    return repaired_document


def test_repaired_fixture_alias(repaired_document: Any, repaired_alias: Any):
    assert repaired_document is repaired_alias
    arguments: Any = repaired_alias["arguments"]
    arguments.append({"ok": False})
    assert arguments is repaired_document["arguments"]
    assert len(repaired_document["arguments"]) == 4
    assert repaired_document["arguments"][0] is True
    assert repaired_document["arguments"][1] is None
    assert repaired_document["arguments"][3]["ok"] is False


def test_repaired_fixture_is_fresh(repaired_document: Any):
    assert len(repaired_document["arguments"]) == 3


def test_repair_log_and_return_objects():
    logged: Any = repair_json('{unquoted: false}', logging=True)
    assert len(logged) == 2
    assert logged[0]["unquoted"] is False
    assert len(logged[1]) > 0
    assert isinstance(logged[1][0]["text"], str)
    assert isinstance(logged[1][0]["context"], str)
    value: Any = repair_json('{unquoted: false}', return_objects=True)
    assert value == logged[0]
