"""Lookahead cache keys preserve ordered targets and the scalar/singleton alias."""
from json_repair.json_parser import JSONParser
from json_repair.parse_string import StringParseState, _cached_skip_to_character

parser = JSONParser("left' | é🌲\0a[b],:}right", None, logging=False)
state = StringParseState()
distinct: list[list[str]] = [
    [], [""], ["'"], ['"'], ["\\"], ["🌲"], ["\0"], [","], ["ab"], ["a", "b"],
    ["b", "a"], ["a", "a"], ["\0", "a"], ["\0a"], ["a", ""], ["", "a"],
    [",", ":", "}"], [",:", "}"], [",", ":}"], ["\0,:}"],
    ["🌲", "é"], ["é", "🌲"], ["'", "\\"], ["\\", "'"], ["['', 'a']"],
]
for index, targets in enumerate(distinct):
    expected = parser.skip_to_character(targets)
    assert _cached_skip_to_character(parser, state, targets) == expected
    assert len(state.lookahead_cache) == index + 1
    if len(targets) == 1:
        assert _cached_skip_to_character(parser, state, targets[0]) == expected
        assert len(state.lookahead_cache) == index + 1

targets = ["a", "}"]
first = _cached_skip_to_character(parser, state, targets)
targets[0] = ":"
second = _cached_skip_to_character(parser, state, targets)
assert first == parser.json_str.index("a")
assert second == parser.json_str.index(":")
targets[0] = "a"
assert _cached_skip_to_character(parser, state, targets) == first
assert len(state.lookahead_cache) == len(distinct) + 2
print("lookahead targets checked", len(distinct))
