# html.parser lowers tag and attribute names of any script, as str.lower() does (#120).
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
