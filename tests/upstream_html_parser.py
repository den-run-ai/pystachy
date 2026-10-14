# CPython 3.13.16 Lib/test/test_htmlparser.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256
# e472b02e738497694caa519a5ccf9b9ae84442cfe3d027ec760f533460a1c175.
# Complete assertion sets from the upstream IDs beside each function.
# Adaptations: unittest helpers become functions/assertions; heterogeneous
# event tuples gain an empty attrs list so all records have one static shape.
# Reused expected-event locals are annotated for optional attribute values.
# The collector normalizes adjacent data events as upstream get_events does.
# Each str source is fed both whole and one indexing unit at a time; explicit
# upstream fragment lists keep their boundaries. Pystachy indexing uses bytes.
# Selected methods avoid mock/decorators/str.format and dynamic helper collectors.
# Exclusions: script/rawtext/rcdata decorator tables, autocdata, default conversion
# collector tests and CPU-resource stress tests; add separate probes for these.
# PSF License Version 2; see THIRD_PARTY_NOTICES.
from html.parser import HTMLParser


class Collector(HTMLParser):
    def __init__(self, convert_charrefs: bool = False, extra: bool = False) -> None:
        self.events: list[tuple[str, str, list[tuple[str, str | None]]]] = []
        self.extra = extra
        super().__init__(convert_charrefs=convert_charrefs)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.events.append(('starttag', tag, attrs))
        if self.extra:
            text = self.get_starttag_text()
            assert text is not None
            self.events.append(('starttag_text', text, []))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.events.append(('startendtag', tag, attrs))

    def handle_endtag(self, tag: str) -> None:
        self.events.append(('endtag', tag, []))

    def handle_data(self, data: str) -> None:
        if self.events and self.events[-1][0] == 'data':
            self.events[-1] = ('data', self.events[-1][1] + data, [])
        else:
            self.events.append(('data', data, []))

    def handle_comment(self, data: str) -> None:
        self.events.append(('comment', data, []))

    def handle_charref(self, data: str) -> None:
        self.events.append(('charref', data, []))

    def handle_entityref(self, data: str) -> None:
        self.events.append(('entityref', data, []))

    def handle_decl(self, data: str) -> None:
        self.events.append(('decl', data, []))

    def handle_pi(self, data: str) -> None:
        self.events.append(('pi', data, []))

    def unknown_decl(self, data: str) -> None:
        self.events.append(('unknown decl', data, []))


def run_check(source, expected: list[tuple[str, str, list[tuple[str, str | None]]]],
              convert_charrefs: bool = False, extra: bool = False) -> None:
    if isinstance(source, str):
        full = Collector(convert_charrefs, extra)
        full.feed(source)
        full.close()
        assert full.events == expected, source
    parser = Collector(convert_charrefs, extra)
    for chunk in source:
        parser.feed(chunk)
    parser.close()
    assert parser.events == expected, source


def run_check_extra(source, expected: list[tuple[str, str, list[tuple[str, str | None]]]]) -> None:
    run_check(source, expected, extra=True)

# test_htmlparser.HTMLParserTestCase.test_processing_instruction_only
def test_processing_instruction_only() -> None:
    run_check('<?processing instruction>', [('pi', 'processing instruction', [])])
    run_check('<?processing instruction ?>', [('pi', 'processing instruction ?', [])])

# test_htmlparser.HTMLParserTestCase.test_simple_html
def test_simple_html() -> None:
    run_check("\n<!DOCTYPE html PUBLIC 'foo'>\n<HTML>&entity;&#32;\n<!--comment1a\n-></foo><bar>&lt;<?pi?></foo<bar\ncomment1b-->\n<Img sRc='Bar' isMAP>sample\ntext\n&#x201C;\n<!--comment2a-- --comment2b-->\n</Html>\n", [('data', '\n', []), ('decl', "DOCTYPE html PUBLIC 'foo'", []), ('data', '\n', []), ('starttag', 'html', []), ('entityref', 'entity', []), ('charref', '32', []), ('data', '\n', []), ('comment', 'comment1a\n-></foo><bar>&lt;<?pi?></foo<bar\ncomment1b', []), ('data', '\n', []), ('starttag', 'img', [('src', 'Bar'), ('ismap', None)]), ('data', 'sample\ntext\n', []), ('charref', 'x201C', []), ('data', '\n', []), ('comment', 'comment2a-- --comment2b', []), ('data', '\n', []), ('endtag', 'html', []), ('data', '\n', [])])

# test_htmlparser.HTMLParserTestCase.test_malformatted_charref
def test_malformatted_charref() -> None:
    run_check('<p>&#bad;</p>', [('starttag', 'p', []), ('data', '&#bad;', []), ('endtag', 'p', [])])
    run_check(['<div>&#bad;</div>'], [('starttag', 'div', []), ('data', '&#bad;', []), ('endtag', 'div', [])])

# test_htmlparser.HTMLParserTestCase.test_unclosed_entityref
def test_unclosed_entityref() -> None:
    run_check('&gt &lt;', [('entityref', 'gt', []), ('data', ' ', []), ('entityref', 'lt', [])], convert_charrefs=False)
    run_check('&gt &lt;', [('data', '> <', [])], convert_charrefs=True)
    run_check('&undefined &lt;', [('entityref', 'undefined', []), ('data', ' ', []), ('entityref', 'lt', [])], convert_charrefs=False)
    run_check('&undefined &lt;', [('data', '&undefined <', [])], convert_charrefs=True)
    run_check('&gtundefined &lt;', [('entityref', 'gtundefined', []), ('data', ' ', []), ('entityref', 'lt', [])], convert_charrefs=False)
    run_check('&gtundefined &lt;', [('data', '>undefined <', [])], convert_charrefs=True)
    run_check('& &lt;', [('data', '& ', []), ('entityref', 'lt', [])], convert_charrefs=False)
    run_check('& &lt;', [('data', '& <', [])], convert_charrefs=True)

# test_htmlparser.HTMLParserTestCase.test_eof_in_entityref
def test_eof_in_entityref() -> None:
    run_check('&gt', [('entityref', 'gt', [])], convert_charrefs=False)
    run_check('&gt', [('data', '>', [])], convert_charrefs=True)
    run_check('&g', [('entityref', 'g', [])], convert_charrefs=False)
    run_check('&g', [('data', '&g', [])], convert_charrefs=True)
    run_check('&undefined', [('entityref', 'undefined', [])], convert_charrefs=False)
    run_check('&undefined', [('data', '&undefined', [])], convert_charrefs=True)
    run_check('&gtundefined', [('entityref', 'gtundefined', [])], convert_charrefs=False)
    run_check('&gtundefined', [('data', '>undefined', [])], convert_charrefs=True)
    run_check('&', [('data', '&', [])], convert_charrefs=False)
    run_check('&', [('data', '&', [])], convert_charrefs=True)

# test_htmlparser.HTMLParserTestCase.test_unclosed_charref
def test_unclosed_charref() -> None:
    run_check('&#123 &lt;', [('charref', '123', []), ('data', ' ', []), ('entityref', 'lt', [])], convert_charrefs=False)
    run_check('&#123 &lt;', [('data', '{ <', [])], convert_charrefs=True)
    run_check('&#xab &lt;', [('charref', 'xab', []), ('data', ' ', []), ('entityref', 'lt', [])], convert_charrefs=False)
    run_check('&#xab &lt;', [('data', '« <', [])], convert_charrefs=True)
    run_check('&#123456789 &lt;', [('charref', '123456789', []), ('data', ' ', []), ('entityref', 'lt', [])], convert_charrefs=False)
    run_check('&#123456789 &lt;', [('data', '� <', [])], convert_charrefs=True)
    run_check('&#x123456789 &lt;', [('charref', 'x123456789', []), ('data', ' ', []), ('entityref', 'lt', [])], convert_charrefs=False)
    run_check('&#x123456789 &lt;', [('data', '� <', [])], convert_charrefs=True)
    run_check('&# &lt;', [('data', '&# ', []), ('entityref', 'lt', [])], convert_charrefs=False)
    run_check('&# &lt;', [('data', '&# <', [])], convert_charrefs=True)
    run_check('&#x &lt;', [('data', '&#x ', []), ('entityref', 'lt', [])], convert_charrefs=False)
    run_check('&#x &lt;', [('data', '&#x <', [])], convert_charrefs=True)

# test_htmlparser.HTMLParserTestCase.test_eof_in_charref
def test_eof_in_charref() -> None:
    run_check('&#123', [('charref', '123', [])], convert_charrefs=False)
    run_check('&#123', [('data', '{', [])], convert_charrefs=True)
    run_check('&#xab', [('charref', 'xab', [])], convert_charrefs=False)
    run_check('&#xab', [('data', '«', [])], convert_charrefs=True)
    run_check('&#123456789', [('charref', '123456789', [])], convert_charrefs=False)
    run_check('&#123456789', [('data', '�', [])], convert_charrefs=True)
    run_check('&#x123456789', [('charref', 'x123456789', [])], convert_charrefs=False)
    run_check('&#x123456789', [('data', '�', [])], convert_charrefs=True)
    run_check('&#', [('data', '&#', [])], convert_charrefs=False)
    run_check('&#', [('data', '&#', [])], convert_charrefs=True)
    run_check('&#x', [('data', '&#x', [])], convert_charrefs=False)
    run_check('&#x', [('data', '&#x', [])], convert_charrefs=True)

# test_htmlparser.HTMLParserTestCase.test_bad_nesting
def test_bad_nesting() -> None:
    run_check('<a><b></a></b>', [('starttag', 'a', []), ('starttag', 'b', []), ('endtag', 'a', []), ('endtag', 'b', [])])

# test_htmlparser.HTMLParserTestCase.test_bare_ampersands
def test_bare_ampersands() -> None:
    run_check('this text & contains & ampersands &', [('data', 'this text & contains & ampersands &', [])])

# test_htmlparser.HTMLParserTestCase.test_bare_pointy_brackets
def test_bare_pointy_brackets() -> None:
    run_check('this < text > contains < bare>pointy< brackets', [('data', 'this < text > contains < bare>pointy< brackets', [])])

# test_htmlparser.HTMLParserTestCase.test_starttag_end_boundary
def test_starttag_end_boundary() -> None:
    run_check("<a b='<'>", [('starttag', 'a', [('b', '<')])])
    run_check("<a b='>'>", [('starttag', 'a', [('b', '>')])])

# test_htmlparser.HTMLParserTestCase.test_buffer_artefacts
def test_buffer_artefacts() -> None:
    output: list[tuple[str, str, list[tuple[str, str | None]]]] = [('starttag', 'a', [('b', '<')])]
    run_check(["<a b='<'>"], output)
    run_check(['<a ', "b='<'>"], output)
    run_check(['<a b', "='<'>"], output)
    run_check(['<a b=', "'<'>"], output)
    run_check(["<a b='<", "'>"], output)
    run_check(["<a b='<'", '>'], output)
    output: list[tuple[str, str, list[tuple[str, str | None]]]] = [('starttag', 'a', [('b', '>')])]
    run_check(["<a b='>'>"], output)
    run_check(['<a ', "b='>'>"], output)
    run_check(['<a b', "='>'>"], output)
    run_check(['<a b=', "'>'>"], output)
    run_check(["<a b='>", "'>"], output)
    run_check(["<a b='>'", '>'], output)
    output: list[tuple[str, str, list[tuple[str, str | None]]]] = [('comment', 'abc', [])]
    run_check(['', '<!--abc-->'], output)
    run_check(['<', '!--abc-->'], output)
    run_check(['<!', '--abc-->'], output)
    run_check(['<!-', '-abc-->'], output)
    run_check(['<!--', 'abc-->'], output)
    run_check(['<!--a', 'bc-->'], output)
    run_check(['<!--ab', 'c-->'], output)
    run_check(['<!--abc', '-->'], output)
    run_check(['<!--abc-', '->'], output)
    run_check(['<!--abc--', '>'], output)
    run_check(['<!--abc-->', ''], output)

# test_htmlparser.HTMLParserTestCase.test_valid_doctypes
def test_valid_doctypes() -> None:
    dtds = ['HTML', 'HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"', 'HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd"', 'html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"', 'html PUBLIC "-//W3C//DTD XHTML 1.0 Frameset//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd"', 'math PUBLIC "-//W3C//DTD MathML 2.0//EN" "http://www.w3.org/Math/DTD/mathml2/mathml2.dtd"', 'html PUBLIC "-//W3C//DTD XHTML 1.1 plus MathML 2.0 plus SVG 1.1//EN" "http://www.w3.org/2002/04/xhtml-math-svg/xhtml-math-svg.dtd"', 'svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"', 'html PUBLIC "-//IETF//DTD HTML 2.0//EN"', 'html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN"']
    for dtd in dtds:
        run_check('<!DOCTYPE %s>' % dtd, [('decl', 'DOCTYPE ' + dtd, [])])

# test_htmlparser.HTMLParserTestCase.test_startendtag
def test_startendtag() -> None:
    run_check('<p/>', [('startendtag', 'p', [])])
    run_check('<p></p>', [('starttag', 'p', []), ('endtag', 'p', [])])
    run_check("<p><img src='foo' /></p>", [('starttag', 'p', []), ('startendtag', 'img', [('src', 'foo')]), ('endtag', 'p', [])])

# test_htmlparser.HTMLParserTestCase.test_get_starttag_text
def test_get_starttag_text() -> None:
    s = '<foo:bar   \n   one="1"\ttwo=2   >'
    run_check_extra(s, [('starttag', 'foo:bar', [('one', '1'), ('two', '2')]), ('starttag_text', s, [])])

# test_htmlparser.HTMLParserTestCase.test_comments
def test_comments() -> None:
    html = "<!-- I'm a valid comment --><!--me too!--><!------><!-----><!----><!---><!--><!----I have many hyphens----><!-- I have a > in the middle --><!-- and I have -- in the middle! --><!--incorrectly-closed-comment--!><!----!><!----!--><!---- >--><!---!>--><!--!>--><!-- <!-- nested --> --><!--<!--><!--<!--!><!-->x--><!--->y-->"
    expected: list[tuple[str, str, list[tuple[str, str | None]]]] = [('comment', " I'm a valid comment ", []), ('comment', 'me too!', []), ('comment', '--', []), ('comment', '-', []), ('comment', '', []), ('comment', '', []), ('comment', '', []), ('comment', '--I have many hyphens--', []), ('comment', ' I have a > in the middle ', []), ('comment', ' and I have -- in the middle! ', []), ('comment', 'incorrectly-closed-comment', []), ('comment', '', []), ('comment', '--!', []), ('comment', '-- >', []), ('comment', '-!>', []), ('comment', '!>', []), ('comment', ' <!-- nested ', []), ('data', ' -->', []), ('comment', '<!', []), ('comment', '<!', []), ('comment', '', []), ('data', 'x-->', []), ('comment', '', []), ('data', 'y-->', [])]
    run_check(html, expected)

# test_htmlparser.HTMLParserTestCase.test_condcoms
def test_condcoms() -> None:
    html = "<!--[if IE & !(lte IE 8)]>aren't<![endif]--><!--[if IE 8]>condcoms<![endif]--><!--[if lte IE 7]>pretty?<![endif]-->"
    expected: list[tuple[str, str, list[tuple[str, str | None]]]] = [('comment', "[if IE & !(lte IE 8)]>aren't<![endif]", []), ('comment', '[if IE 8]>condcoms<![endif]', []), ('comment', '[if lte IE 7]>pretty?<![endif]', [])]
    run_check(html, expected)

# test_htmlparser.HTMLParserTestCase.test_tolerant_parsing
def test_tolerant_parsing() -> None:
    run_check('<html <html>te>>xt&a<<bc</a></html>\n<img src="URL><//img></html</html>', [('starttag', 'html', [('<html', None)]), ('data', 'te>>xt', []), ('entityref', 'a', []), ('data', '<', []), ('starttag', 'bc<', [('a', None)]), ('endtag', 'html', []), ('data', '\n', [])])

# test_htmlparser.HTMLParserTestCase.test_slashes_in_endtag
def test_slashes_in_endtag() -> None:
    run_check('</a/>', [('endtag', 'a', [])])
    run_check('</a foo="var"/>', [('endtag', 'a', [])])

# test_htmlparser.HTMLParserTestCase.test_declaration_junk_chars
def test_declaration_junk_chars() -> None:
    run_check('<!DOCTYPE foo $ >', [('decl', 'DOCTYPE foo $ ', [])])

# test_htmlparser.HTMLParserTestCase.test_illegal_declarations
def test_illegal_declarations() -> None:
    run_check('<!spacer type="block" height="25">', [('comment', 'spacer type="block" height="25"', [])])

# test_htmlparser.HTMLParserTestCase.test_invalid_end_tags
def test_invalid_end_tags() -> None:
    html = '<br></label</p><br></div end tmAd-leaderBoard><br></<h4><br></li class="unit"><br></li\r\n\t\t\t\t\t\t</ul><br></><br>'
    expected: list[tuple[str, str, list[tuple[str, str | None]]]] = [('starttag', 'br', []), ('endtag', 'label<', []), ('starttag', 'br', []), ('endtag', 'div', []), ('starttag', 'br', []), ('comment', '<h4', []), ('starttag', 'br', []), ('endtag', 'li', []), ('starttag', 'br', []), ('endtag', 'li', []), ('starttag', 'br', []), ('starttag', 'br', [])]
    run_check(html, expected)

# test_htmlparser.HTMLParserTestCase.test_broken_invalid_end_tag
def test_broken_invalid_end_tag() -> None:
    html = '<b>This</b attr=">"> confuses the parser'
    expected: list[tuple[str, str, list[tuple[str, str | None]]]] = [('starttag', 'b', []), ('data', 'This', []), ('endtag', 'b', []), ('data', ' confuses the parser', [])]
    run_check(html, expected)

# test_htmlparser.HTMLParserTestCase.test_correct_detection_of_start_tags
def test_correct_detection_of_start_tags() -> None:
    html = '<div style=""    ><b>The <a href="some_url">rain</a> <br /> in <span>Spain</span></b></div>'
    expected: list[tuple[str, str, list[tuple[str, str | None]]]] = [('starttag', 'div', [('style', '')]), ('starttag', 'b', []), ('data', 'The ', []), ('starttag', 'a', [('href', 'some_url')]), ('data', 'rain', []), ('endtag', 'a', []), ('data', ' ', []), ('startendtag', 'br', []), ('data', ' in ', []), ('starttag', 'span', []), ('data', 'Spain', []), ('endtag', 'span', []), ('endtag', 'b', []), ('endtag', 'div', [])]
    run_check(html, expected)
    html = '<div style="", foo = "bar" ><b>The <a href="some_url">rain</a>'
    expected: list[tuple[str, str, list[tuple[str, str | None]]]] = [('starttag', 'div', [('style', ''), (',', None), ('foo', 'bar')]), ('starttag', 'b', []), ('data', 'The ', []), ('starttag', 'a', [('href', 'some_url')]), ('data', 'rain', []), ('endtag', 'a', [])]
    run_check(html, expected)

# test_htmlparser.HTMLParserTestCase.test_eof_in_comments
def test_eof_in_comments() -> None:
    data: list[tuple[str, list[tuple[str, str, list[tuple[str, str | None]]]]]] = [('<!--', [('comment', '', [])]), ('<!---', [('comment', '', [])]), ('<!----', [('comment', '', [])]), ('<!-----', [('comment', '-', [])]), ('<!------', [('comment', '--', [])]), ('<!----!', [('comment', '', [])]), ('<!---!', [('comment', '-!', [])]), ('<!---!>', [('comment', '-!>', [])]), ('<!--foo', [('comment', 'foo', [])]), ('<!--foo-', [('comment', 'foo', [])]), ('<!--foo--', [('comment', 'foo', [])]), ('<!--foo--!', [('comment', 'foo', [])]), ('<!--<!--', [('comment', '<!', [])]), ('<!--<!--!', [('comment', '<!', [])])]
    for html, expected in data:
        run_check(html, expected)

# test_htmlparser.HTMLParserTestCase.test_eof_in_declarations
def test_eof_in_declarations() -> None:
    data: list[tuple[str, list[tuple[str, str, list[tuple[str, str | None]]]]]] = [('<!', [('comment', '', [])]), ('<!-', [('comment', '-', [])]), ('<![', [('comment', '[', [])]), ('<!DOCTYPE', [('decl', 'DOCTYPE', [])]), ('<!DOCTYPE ', [('decl', 'DOCTYPE ', [])]), ('<!DOCTYPE html', [('decl', 'DOCTYPE html', [])]), ('<!DOCTYPE html ', [('decl', 'DOCTYPE html ', [])]), ('<!DOCTYPE html PUBLIC', [('decl', 'DOCTYPE html PUBLIC', [])]), ('<!DOCTYPE html PUBLIC "foo', [('decl', 'DOCTYPE html PUBLIC "foo', [])]), ('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "foo', [('decl', 'DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "foo', [])])]
    for html, expected in data:
        run_check(html, expected)

# test_htmlparser.HTMLParserTestCase.test_bogus_comments
def test_bogus_comments() -> None:
    html = '<!ELEMENT br EMPTY><! not really a comment ><! not a comment either --><! -- close enough --><!><!<-- this was an empty comment><!!! another bogus comment !!!><![with square brackets]!><![\nmultiline\nbogusness\n]!><![more brackets]-[and a hyphen]!><![cdata[should be uppercase]]><![CDATA [whitespaces are not ignored]]><![CDATA]]>'
    expected: list[tuple[str, str, list[tuple[str, str | None]]]] = [('comment', 'ELEMENT br EMPTY', []), ('comment', ' not really a comment ', []), ('comment', ' not a comment either --', []), ('comment', ' -- close enough --', []), ('comment', '', []), ('comment', '<-- this was an empty comment', []), ('comment', '!! another bogus comment !!!', []), ('comment', '[with square brackets]!', []), ('comment', '[\nmultiline\nbogusness\n]!', []), ('comment', '[more brackets]-[and a hyphen]!', []), ('comment', '[cdata[should be uppercase]]', []), ('comment', '[CDATA [whitespaces are not ignored]]', []), ('comment', '[CDATA]]', [])]
    run_check(html, expected)

# test_htmlparser.HTMLParserTestCase.test_broken_condcoms
def test_broken_condcoms() -> None:
    html = '<![if !(IE)]>broken condcom<![endif]><![if ! IE]><link href="favicon.tiff"/><![endif]><![if !IE 6]><img src="firefox.png" /><![endif]><![if !ie 6]><b>foo</b><![endif]><![if (!IE)|(lt IE 9)]><img src="mammoth.bmp" /><![endif]>'
    expected: list[tuple[str, str, list[tuple[str, str | None]]]] = [('comment', '[if !(IE)]', []), ('data', 'broken condcom', []), ('comment', '[endif]', []), ('comment', '[if ! IE]', []), ('startendtag', 'link', [('href', 'favicon.tiff')]), ('comment', '[endif]', []), ('comment', '[if !IE 6]', []), ('startendtag', 'img', [('src', 'firefox.png')]), ('comment', '[endif]', []), ('comment', '[if !ie 6]', []), ('starttag', 'b', []), ('data', 'foo', []), ('endtag', 'b', []), ('comment', '[endif]', []), ('comment', '[if (!IE)|(lt IE 9)]', []), ('startendtag', 'img', [('src', 'mammoth.bmp')]), ('comment', '[endif]', [])]
    run_check(html, expected)

# test_htmlparser.AttributesTestCase.test_attr_syntax
def test_attr_syntax() -> None:
    output: list[tuple[str, str, list[tuple[str, str | None]]]] = [('starttag', 'a', [('b', 'v'), ('c', 'v'), ('d', 'v'), ('e', None)])]
    run_check('<a b=\'v\' c="v" d=v e>', output)
    run_check('<a foo==bar>', [('starttag', 'a', [('foo', '=bar')])])
    run_check('<a foo =bar>', [('starttag', 'a', [('foo', 'bar')])])
    run_check('<a foo\t=bar>', [('starttag', 'a', [('foo', 'bar')])])
    run_check('<a foo\x0b=bar>', [('starttag', 'a', [('foo\x0b', 'bar')])])
    run_check('<a foo\xa0=bar>', [('starttag', 'a', [('foo\xa0', 'bar')])])
    run_check('<a foo= bar>', [('starttag', 'a', [('foo', 'bar')])])
    run_check('<a foo=\tbar>', [('starttag', 'a', [('foo', 'bar')])])
    run_check('<a foo=\x0bbar>', [('starttag', 'a', [('foo', '\x0bbar')])])
    run_check('<a foo=\xa0bar>', [('starttag', 'a', [('foo', '\xa0bar')])])

# test_htmlparser.AttributesTestCase.test_attr_values
def test_attr_values() -> None:
    run_check('<a b=\'xxx\n\txxx\' c="yyy\t\nyyy" d=\'\txyz\n\'>', [('starttag', 'a', [('b', 'xxx\n\txxx'), ('c', 'yyy\t\nyyy'), ('d', '\txyz\n')])])
    run_check('<a b=\'\' c="">', [('starttag', 'a', [('b', ''), ('c', '')])])
    run_check('<a b=\tx c=\ny>', [('starttag', 'a', [('b', 'x'), ('c', 'y')])])
    run_check('<a b=\x0b c=\xa0>', [('starttag', 'a', [('b', '\x0b'), ('c', '\xa0')])])
    run_check('<e a=rgb(1,2,3)>', [('starttag', 'e', [('a', 'rgb(1,2,3)')])])
    run_check('<a href=mailto:xyz@example.com>', [('starttag', 'a', [('href', 'mailto:xyz@example.com')])])

# test_htmlparser.AttributesTestCase.test_attr_nonascii
def test_attr_nonascii() -> None:
    run_check('<img src=/foo/bar.png alt=中文>', [('starttag', 'img', [('src', '/foo/bar.png'), ('alt', '中文')])])
    run_check("<a title='テスト' href='テスト.html'>", [('starttag', 'a', [('title', 'テスト'), ('href', 'テスト.html')])])
    run_check('<a title="テスト" href="テスト.html">', [('starttag', 'a', [('title', 'テスト'), ('href', 'テスト.html')])])

# test_htmlparser.AttributesTestCase.test_attr_entity_replacement
def test_attr_entity_replacement() -> None:
    run_check("<a b='&amp;&gt;&lt;&quot;&apos;'>", [('starttag', 'a', [('b', '&><"\'')])])

# test_htmlparser.AttributesTestCase.test_attr_funky_names
def test_attr_funky_names() -> None:
    run_check("<a a.b='v' c:d=v e-f=v>", [('starttag', 'a', [('a.b', 'v'), ('c:d', 'v'), ('e-f', 'v')])])

# test_htmlparser.AttributesTestCase.test_entityrefs_in_attributes
def test_entityrefs_in_attributes() -> None:
    run_check("<html foo='&euro;&amp;&#97;&#x61;&unsupported;'>", [('starttag', 'html', [('foo', '€&aa&unsupported;')])])

# test_htmlparser.AttributesTestCase.test_attr_funky_names2
def test_attr_funky_names2() -> None:
    run_check('<a $><b $=%><c \\=/>', [('starttag', 'a', [('$', None)]), ('starttag', 'b', [('$', '%')]), ('starttag', 'c', [('\\', '/')])])

# test_htmlparser.AttributesTestCase.test_entities_in_attribute_value
def test_entities_in_attribute_value() -> None:
    for entity in ['&', '&amp;', '&#38;', '&#x26;']:
        run_check('<a href="%s">' % entity, [('starttag', 'a', [('href', '&')])])
        run_check("<a href='%s'>" % entity, [('starttag', 'a', [('href', '&')])])
        run_check('<a href=%s>' % entity, [('starttag', 'a', [('href', '&')])])

# test_htmlparser.AttributesTestCase.test_malformed_attributes
def test_malformed_attributes() -> None:
    html = "<a href=test'style='color:red;bad1'>test - bad1</a><a href=test'+style='color:red;ba2'>test - bad2</a><a href=test'&nbsp;style='color:red;bad3'>test - bad3</a><a href = test'&nbsp;style='color:red;bad4'  >test - bad4</a>"
    expected: list[tuple[str, str, list[tuple[str, str | None]]]] = [('starttag', 'a', [('href', "test'style='color:red;bad1'")]), ('data', 'test - bad1', []), ('endtag', 'a', []), ('starttag', 'a', [('href', "test'+style='color:red;ba2'")]), ('data', 'test - bad2', []), ('endtag', 'a', []), ('starttag', 'a', [('href', "test'\xa0style='color:red;bad3'")]), ('data', 'test - bad3', []), ('endtag', 'a', []), ('starttag', 'a', [('href', "test'\xa0style='color:red;bad4'")]), ('data', 'test - bad4', []), ('endtag', 'a', [])]
    run_check(html, expected)

# test_htmlparser.AttributesTestCase.test_malformed_adjacent_attributes
def test_malformed_adjacent_attributes() -> None:
    run_check('<x><y z=""o"" /></x>', [('starttag', 'x', []), ('startendtag', 'y', [('z', ''), ('o""', None)]), ('endtag', 'x', [])])
    run_check('<x><y z="""" /></x>', [('starttag', 'x', []), ('startendtag', 'y', [('z', ''), ('""', None)]), ('endtag', 'x', [])])

# test_htmlparser.AttributesTestCase.test_adjacent_attributes
def test_adjacent_attributes() -> None:
    run_check('<a width="100%"cellspacing=0>', [('starttag', 'a', [('width', '100%'), ('cellspacing', '0')])])
    run_check('<a id="foo"class="bar">', [('starttag', 'a', [('id', 'foo'), ('class', 'bar')])])

# test_htmlparser.AttributesTestCase.test_missing_attribute_value
def test_missing_attribute_value() -> None:
    run_check('<a v=>', [('starttag', 'a', [('v', '')])])

# test_htmlparser.AttributesTestCase.test_javascript_attribute_value
def test_javascript_attribute_value() -> None:
    run_check("<a href=javascript:popup('/popup/help.html')>", [('starttag', 'a', [('href', "javascript:popup('/popup/help.html')")])])

# test_htmlparser.AttributesTestCase.test_end_tag_in_attribute_value
def test_end_tag_in_attribute_value() -> None:
    run_check('<a href=\'http://www.example.org/">;\'>spam</a>', [('starttag', 'a', [('href', 'http://www.example.org/">;')]), ('data', 'spam', []), ('endtag', 'a', [])])

# test_htmlparser.AttributesTestCase.test_with_unquoted_attributes
def test_with_unquoted_attributes() -> None:
    html = "<html><body bgcolor=d0ca90 text='181008'><table cellspacing=0 cellpadding=1 width=100% ><tr><td align=left><font size=-1>- <a href=/rabota/><span class=en> software-and-i</span></a>- <a href='/1/'><span class=en> library</span></a></table>"
    expected: list[tuple[str, str, list[tuple[str, str | None]]]] = [('starttag', 'html', []), ('starttag', 'body', [('bgcolor', 'd0ca90'), ('text', '181008')]), ('starttag', 'table', [('cellspacing', '0'), ('cellpadding', '1'), ('width', '100%')]), ('starttag', 'tr', []), ('starttag', 'td', [('align', 'left')]), ('starttag', 'font', [('size', '-1')]), ('data', '- ', []), ('starttag', 'a', [('href', '/rabota/')]), ('starttag', 'span', [('class', 'en')]), ('data', ' software-and-i', []), ('endtag', 'span', []), ('endtag', 'a', []), ('data', '- ', []), ('starttag', 'a', [('href', '/1/')]), ('starttag', 'span', [('class', 'en')]), ('data', ' library', []), ('endtag', 'span', []), ('endtag', 'a', []), ('endtag', 'table', [])]
    run_check(html, expected)

# test_htmlparser.AttributesTestCase.test_comma_between_attributes
def test_comma_between_attributes() -> None:
    html = '<div class=bar,baz=asd><div class="bar",baz="asd"><div class=bar, baz=asd,><div class="bar", baz="asd",><div class="bar",><div class=,bar baz=,asd><div class=,"bar" baz=,"asd"><div ,class=bar ,baz=asd><div class,="bar" baz,="asd">'
    expected: list[tuple[str, str, list[tuple[str, str | None]]]] = [('starttag', 'div', [('class', 'bar,baz=asd')]), ('starttag', 'div', [('class', 'bar'), (',baz', 'asd')]), ('starttag', 'div', [('class', 'bar,'), ('baz', 'asd,')]), ('starttag', 'div', [('class', 'bar'), (',', None), ('baz', 'asd'), (',', None)]), ('starttag', 'div', [('class', 'bar'), (',', None)]), ('starttag', 'div', [('class', ',bar'), ('baz', ',asd')]), ('starttag', 'div', [('class', ',"bar"'), ('baz', ',"asd"')]), ('starttag', 'div', [(',class', 'bar'), (',baz', 'asd')]), ('starttag', 'div', [('class,', 'bar'), ('baz,', 'asd')])]
    run_check(html, expected)

# test_htmlparser.AttributesTestCase.test_weird_chars_in_unquoted_attribute_values
def test_weird_chars_in_unquoted_attribute_values() -> None:
    run_check('<form action=bogus|&#()value>', [('starttag', 'form', [('action', 'bogus|&#()value')])])

test_processing_instruction_only()
test_simple_html()
test_malformatted_charref()
test_unclosed_entityref()
test_eof_in_entityref()
test_unclosed_charref()
test_eof_in_charref()
test_bad_nesting()
test_bare_ampersands()
test_bare_pointy_brackets()
test_starttag_end_boundary()
test_buffer_artefacts()
test_valid_doctypes()
test_startendtag()
test_get_starttag_text()
test_comments()
test_condcoms()
test_tolerant_parsing()
test_slashes_in_endtag()
test_declaration_junk_chars()
test_illegal_declarations()
test_invalid_end_tags()
test_broken_invalid_end_tag()
test_correct_detection_of_start_tags()
test_eof_in_comments()
test_eof_in_declarations()
test_bogus_comments()
test_broken_condcoms()
test_attr_syntax()
test_attr_values()
test_attr_nonascii()
test_attr_entity_replacement()
test_attr_funky_names()
test_entityrefs_in_attributes()
test_attr_funky_names2()
test_entities_in_attribute_value()
test_malformed_attributes()
test_malformed_adjacent_attributes()
test_adjacent_attributes()
test_missing_attribute_value()
test_javascript_attribute_value()
test_end_tag_in_attribute_value()
test_with_unquoted_attributes()
test_comma_between_attributes()
test_weird_chars_in_unquoted_attribute_values()
print('45 upstream HTMLParser methods passed')
