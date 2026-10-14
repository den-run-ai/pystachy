# Non-ASCII tag/attribute case conversion uses Pystachy's ASCII-only str.lower.
from html.parser import HTMLParser
class Names(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        print(tag, attrs)
    def handle_endtag(self, tag: str) -> None:
        print(tag)
p = Names()
p.feed('<AÜ XÄ="ok"></AÜ>')
p.close()
