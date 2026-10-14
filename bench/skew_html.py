"""Standard-library HTML parsing with a shared caller and concrete callbacks.

Record with tools/skewprofile.py --function parse_documents --parameter parser.
Use check for held-out callback correctness; bench/static report in-process time.
ASCII documents keep the HTML port's Unicode-position deviations out of timings.
"""
import sys
import time
from html.parser import HTMLParser


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        self.links = 0
        self.href_bytes = 0
        super().__init__()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value is not None:
                    self.links += 1
                    self.href_bytes += len(value)


class TextParser(HTMLParser):
    def __init__(self) -> None:
        self.text_bytes = 0
        super().__init__()

    def handle_data(self, data: str) -> None:
        self.text_bytes += len(data)


DOCUMENTS = ['<!doctype html><html><body><a href="/first?q=1&amp;x=2">First</a>'
             '<p>Some <b>bold</b> text &amp; more.</p></body></html>',
             '<div><a href="/second">Second</a><img src="a.png"/><!-- comment -->'
             '<script>if (x < 2) y = "&amp;";</script></div>',
             '<title>A &amp; B</title>\n<a href="/third">Third</a><textarea>&lt;tag&gt;</textarea>']


def parse_documents(parser: HTMLParser, documents: list[str], repeats: int) -> int:
    checksum = 0
    for _ in range(repeats):
        for document in documents:
            parser.reset()
            # Exercise incremental buffering rather than only complete feed calls.
            middle = len(document) // 2
            parser.feed(document[:middle])
            parser.feed(document[middle:])
            parser.close()
            position: tuple[int, int] = parser.getpos()
            checksum += position[0] * 1000 + position[1]
    return checksum


def concrete(parser: LinkParser, documents: list[str], repeats: int) -> int:
    checksum = 0
    for _ in range(repeats):
        for document in documents:
            parser.reset()
            middle = len(document) // 2
            parser.feed(document[:middle])
            parser.feed(document[middle:])
            parser.close()
            position: tuple[int, int] = parser.getpos()
            checksum += position[0] * 1000 + position[1]
    return checksum


mode = sys.argv[1] if len(sys.argv) > 1 else "bench"
links = LinkParser()
text = TextParser()
selected: HTMLParser = links
if mode == "train":
    checksum = 0
    for i in range(200):
        if i == 199:
            selected = text
        else:
            selected = links
        checksum += parse_documents(selected, DOCUMENTS, 1)
    print("train", checksum, links.links, links.href_bytes, text.text_bytes)
elif mode == "check":
    checksum = 0
    # Balanced then reversed held-out types must retain both callback behaviors.
    for i in range(20):
        if i % 2 == 0:
            selected = links
        else:
            selected = text
        checksum += parse_documents(selected, DOCUMENTS, 1)
    for i in range(20):
        if i == 19:
            selected = links
        else:
            selected = text
        checksum += parse_documents(selected, DOCUMENTS, 1)
    print("check", checksum, links.links, links.href_bytes, text.text_bytes)
else:
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    if len(sys.argv) > 3 and sys.argv[3] == "text":
        selected = text
    start = time.perf_counter()
    result = concrete(links, DOCUMENTS, repeats) if mode == "static" else parse_documents(selected, DOCUMENTS, repeats)
    elapsed = time.perf_counter() - start
    print(result, links.links, links.href_bytes, text.text_bytes, elapsed)
