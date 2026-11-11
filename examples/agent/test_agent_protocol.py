"""Pure protocol checks; actual tool processes and HTTP transport stay separate."""
from agent import decode_action
from wire_json import JsonDocument, json_quote, utf8_size
import pytest


@pytest.mark.parametrize("text", ["plain", 'quote" and slash\\', "café 日本語 😀\n"])
def test_unicode_json_quote_roundtrip(text: str):
    document = JsonDocument(json_quote(text))
    assert document.string(document.root) == text
    assert utf8_size(text) == len(text.encode("utf-8"))


def test_json_numbers_retain_their_original_lexemes():
    document = JsonDocument('{"number":123456789012345678901234567890,"items":[1e+02,null]}')
    assert document.raw(document.field(document.root, "number")) == "123456789012345678901234567890"
    items = document.items(document.field(document.root, "items"))
    assert len(items) == 2
    assert document.raw(items[0]) == "1e+02"
    assert document.raw(items[1]) == "null"


@pytest.mark.parametrize("source", ['{"a":1,"a":2}', '"\\ud800"', '"\\udc00"', '01', '[] trailing'])
def test_malformed_wire_json_rejected(source: str):
    with pytest.raises(ValueError):
        JsonDocument(source)


def reply(kind: str, arguments: str) -> str:
    return ('{"choices":[{"message":{"tool_calls":[{"type":"function","function":{"name":'
            + json_quote(kind) + ',"arguments":' + json_quote(arguments) + '}}]}}]}')


def test_action_decode_preserves_unicode_payload():
    action = decode_action(reply("write", '{"path":"note.txt","content":"café 😀"}'))
    assert action.kind == "write"
    assert action.path == "note.txt"
    assert action.content == "café 😀"


@pytest.mark.parametrize("kind,arguments", [("unknown", "{}"), ("write", '{"path":"note.txt"}'),
                                         ("edit", '{"path":"note.txt","old":"","new":"x"}')])
def test_action_shape_rejected(kind: str, arguments: str):
    with pytest.raises(ValueError):
        decode_action(reply(kind, arguments))
