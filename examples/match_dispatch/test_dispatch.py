"""The same command cases run in original pytest and the native runner."""
import dispatch
import pytest


@pytest.mark.parametrize("text,total,expected", [
    ("add:7", 0, 7), ("sub:2", 7, 5), ("scale:3", 5, 15),
    ("reset:0", 15, 0), ("add:-4", 0, -4),
])
def test_commands(text: str, total: int, expected: int):
    assert dispatch.apply(total, dispatch.parse(text)) == expected


@pytest.mark.parametrize("text", ["scale:0", "scale:-2", "reset:1", "unknown:3", "add"])
def test_invalid_commands(text: str):
    with pytest.raises(ValueError):
        dispatch.parse(text)


def test_command_order_is_preserved():
    assert dispatch.evaluate(["add:7", "sub:2", "scale:3", "reset:0", "add:-4"]) == [7, 5, 15, 0, -4]
