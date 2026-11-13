# constargs (constargs.inline): the compiled functions each function still calls once the
# tests of what the whole program leaves constant are decided. repair() is called with its
# schema left None and strict left False, by main and through loads(), which passes its own
# on: it calls neither Helper nor heavy(). Parser.helper is assigned only by attach(), which
# nothing calls, so parse() does not call wrap(), and resolve()'s first item is None, so
# apply() does not call ruled(). shout()'s loud is passed True by one call: it keeps upper().


class Helper:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    def run(self, text: str) -> str:
        return self.tag + text


def heavy(text: str, tag: str) -> str:
    return Helper(tag).run(text)


def repair(text: str, schema: dict[str, str] | None = None, strict: bool = False) -> str:
    helper = Helper(schema["tag"]) if schema is not None else None
    if strict:
        text = clean(text)
    if helper is not None:
        return helper.run(text)
    if schema is not None:
        return heavy(text, "x")
    return text


def clean(text: str) -> str:
    return text.strip()


def loads(text: str, schema: dict[str, str] | None = None) -> str:
    return repair(text, schema=schema)


def upper(text: str) -> str:
    return text.upper()


def shout(text: str, loud: bool = False) -> str:
    if loud:
        return upper(text)
    return text


def wrap(text: str) -> str:
    return "<" + text + ">"


def ruled(key: str) -> str:
    return "ruled " + key


class Parser:
    def __init__(self) -> None:
        self.helper: Parser | None = None

    def attach(self, other: "Parser") -> None:
        self.helper = other

    def parse(self, text: str) -> str:
        if self.helper is not None:
            return wrap(self.helper.parse(text))
        return text

    def resolve(self, key: str) -> tuple["Parser | None", str]:
        found = self.helper if self.helper is not None and key != "" else None
        if found is None:
            return None, key
        return found, key

    def apply(self, key: str) -> str:
        found, key = self.resolve(key)
        if found is not None:
            return ruled(key)
        return key


print(repair(" a "), loads(" b "))
print(shout("c"), shout("d", True))
p = Parser()
print(p.parse("e"), p.apply("f"))
