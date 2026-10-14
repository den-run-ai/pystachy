# Direct boundary probes supplement tests/upstream_html_parser.py's complete
# upstream method selections. Event payloads stay strings; missing attributes
# retain None. ASCII positions follow upstream; Unicode column offsets have a
# separate deviation because Pystachy's string indices count UTF-8 bytes.
from html.parser import HTMLParser


class Recorder(HTMLParser):
    def __init__(self, convert_charrefs: bool = True, scripting: bool = False) -> None:
        self.events: list[str] = []
        self.last_attrs: list[tuple[str, str | None]] = []
        super().__init__(convert_charrefs=convert_charrefs, scripting=scripting)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.events.append('start:' + tag)
        self.last_attrs = attrs

    def handle_endtag(self, tag: str) -> None:
        self.events.append('end:' + tag)

    def handle_data(self, data: str) -> None:
        if self.events and self.events[-1].startswith('data:'):
            self.events[-1] += data
        else:
            self.events.append('data:' + data)

    def handle_comment(self, data: str) -> None:
        self.events.append('comment:' + data)

    def handle_decl(self, data: str) -> None:
        self.events.append('decl:' + data)

    def handle_pi(self, data: str) -> None:
        self.events.append('pi:' + data)

    def unknown_decl(self, data: str) -> None:
        self.events.append('unknown:' + data)

    def handle_entityref(self, name: str) -> None:
        self.events.append('entity:' + name)

    def handle_charref(self, name: str) -> None:
        self.events.append('char:' + name)


def check_chunks(chunks: list[str], expected: list[str],
                 convert_charrefs: bool = True, scripting: bool = False) -> None:
    parser = Recorder(convert_charrefs, scripting)
    for chunk in chunks:
        parser.feed(chunk)
    parser.close()
    assert parser.events == expected, parser.events


# RAWTEXT keeps tags and references verbatim, including split end tags.
check_chunks(['<script>if (a < b) x = "&amp;";</scr', 'ipt>'],
             ['start:script', 'data:if (a < b) x = "&amp;";', 'end:script'])
check_chunks(['<STYLE>a>b{content:"&amp;"}', '</StYlE>'],
             ['start:style', 'data:a>b{content:"&amp;"}', 'end:style'])

# RCDATA decodes references while retaining nonmatching markup as data.
check_chunks(['<textarea>&am', 'p;<b>x</b></text', 'area>'],
             ['start:textarea', 'data:&<b>x</b>', 'end:textarea'])
check_chunks(['<title>&lt;z&gt;</title>'],
             ['start:title', 'data:<z>', 'end:title'])
check_chunks(['<textarea>&amp;<b>x</b></textarea>'],
             ['start:textarea', 'entity:amp', 'data:<b>x</b>', 'end:textarea'],
             convert_charrefs=False)

# Scripting changes noscript to RAWTEXT; plaintext has no closing token.
check_chunks(['<noscript><b>&amp;</b></noscript>'],
             ['start:noscript', 'start:b', 'data:&', 'end:b', 'end:noscript'])
check_chunks(['<noscript><b>&amp;</b></noscript>'],
             ['start:noscript', 'data:<b>&amp;</b>', 'end:noscript'], scripting=True)
check_chunks(['<plaintext><b>&amp;</plaintext>'],
             ['start:plaintext', 'data:<b>&amp;</plaintext>'])

# Conversion, disabled conversion, large numeric refs and Unicode payloads.
check_chunks(['A &a', 'mp; &#x1F600; &#999999999999999999999999999999; Z'],
             ['data:A & 😀 � Z'])
check_chunks(['A &a', 'mp; &#x1F600; Z'],
             ['data:A ', 'entity:amp', 'data: ', 'char:x1F600', 'data: Z'],
             convert_charrefs=False)
check_chunks(['<p>café ', '😀 &amp; 中文</p>'],
             ['start:p', 'data:café 😀 & 中文', 'end:p'])
check_chunks(['<![CDATA[one <b> &amp;]]>'], ['unknown:CDATA[one <b> &amp;'])
check_chunks(['<!-- split ', 'comment --><!DOCTYPE html><?p?>'],
             ['comment: split comment ', 'decl:DOCTYPE html', 'pi:p?'])

# Inherited handle_startendtag dispatches both concrete callbacks.
parser = Recorder()
assert parser.get_starttag_text() is None
parser.feed('<A x="&amp;" disabled/>')
parser.close()
assert parser.events == ['start:a', 'end:a']
assert parser.last_attrs == [('x', '&'), ('disabled', None)]
assert parser.get_starttag_text() == '<A x="&amp;" disabled/>'

# reset retains the last completed tag text, as upstream does.
parser.reset()
assert parser.get_starttag_text() == '<A x="&amp;" disabled/>'
# Starting an incomplete tag clears that text; reset discards the partial markup.
parser.feed('<incomplete')
parser.reset()
assert parser.getpos() == (1, 0)
assert parser.get_starttag_text() is None
parser.events.clear()
parser.feed('ok\n<q>next\n')
parser.close()
assert parser.events == ['data:ok\n', 'start:q', 'data:next\n']
assert parser.getpos() == (3, 0)
parser.feed('last')
parser.close()
assert parser.getpos() == (3, 4)

# A base-typed receiver still calls a derived callback.
def feed_base(parser: HTMLParser) -> None:
    parser.feed('<z/>')
    parser.close()

other = Recorder()
feed_base(other)
assert other.events == ['start:z', 'end:z']
print('HTMLParser boundary probes passed')
