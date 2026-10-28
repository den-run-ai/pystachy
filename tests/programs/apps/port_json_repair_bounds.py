from json_repair.json_parser import JSONParser
from json_repair.utils.json_context import ContextValues, JsonContext


# Retain the upstream exception-based operations as independent oracles for
# negative positions, EOF, backwards scans, Unicode and whitespace-only input.
def original_get(text: str, index: int) -> str | None:
    try:
        return text[index]
    except IndexError:
        return None


def original_skip(text: str, index: int) -> int:
    try:
        char = text[index]
        while char.isspace():
            index += 1
            char = text[index]
    except IndexError:
        pass
    return index


def original_scroll(text: str, index: int, idx: int, backwards: bool) -> int:
    step = -1 if backwards else 1
    try:
        char = text[index + idx]
        while index + idx >= 0 and char.isspace():
            idx += step
            char = text[index + idx]
    except IndexError:
        pass
    return idx


checks = 0
for text in ["", " ", "\t\n ", " a ", "a", "\u2003é😀\u2003", "é\t😀 "]:
    parser = JSONParser(text, False)
    for index in range(-len(text) - 2, len(text) + 3):
        parser.index = index
        parser.skip_whitespaces()
        assert parser.index == original_skip(text, index)
        checks += 1
        parser.index = index
        for offset in range(-len(text) - 2, len(text) + 3):
            assert parser.get_char_at(offset) == original_get(text, index + offset)
            checks += 1
            for backwards in [False, True]:
                assert parser.scroll_whitespaces(offset, backwards=backwards) == original_scroll(
                    text, index, offset, backwards
                )
                assert parser.index == index
                checks += 1
print("position comparisons", checks)

context = JsonContext()
context.reset()
assert context.context == [] and context.current is None and context.empty
context.set(ContextValues.ARRAY)
context.set(ContextValues.OBJECT_KEY)
context.reset()
assert context.context == [ContextValues.ARRAY]
assert context.current == ContextValues.ARRAY and not context.empty
context.reset()
assert context.context == [] and context.current is None and context.empty
context.reset()
assert context.context == [] and context.current is None and context.empty
with context.enter(ContextValues.OBJECT_VALUE):
    assert context.current == ContextValues.OBJECT_VALUE and not context.empty
    with context.enter(ContextValues.ARRAY):
        assert context.current == ContextValues.ARRAY and not context.empty
    assert context.current == ContextValues.OBJECT_VALUE and not context.empty
assert context.context == [] and context.current is None and context.empty
context.set(ContextValues.OBJECT_KEY)
context.clear()
context.reset()
assert context.context == [] and context.current is None and context.empty
print("context transitions ok")
