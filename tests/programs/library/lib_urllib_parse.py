# lib/urllib/parse.py (CPython 3.13's urllib.parse, ported) against CPython's: quote(),
# quote_plus(), unquote(), unquote_plus(), parse_qs(), parse_qsl() and urlencode() with their
# keyword arguments, on characters past ASCII and on percent-escapes that are no UTF-8, with each
# codec and error handler the port has; and urlsplit(), urlparse(), urlunsplit(), urlunparse(),
# urljoin() and urldefrag(). The str cases of CPython 3.13's Lib/test/test_urlparse.py and of
# test_urllib.py's QuotingTests, UnquotingTests and urlencode_Tests come first; then every
# percent-escape of one and two bytes, and of three and four bytes from a set that takes each path
# of CPython's UTF-8 decoder, and code points of each length of UTF-8, which digest() sums up. A
# str holds UTF-8 in Pystachy, so a str of a code point is "%c" % cp (chr() of one below 256 is a
# byte); results are printed as ascii() or repr(), which CPython can print with surrogates in them.
# Where CPython raises UnicodeEncodeError or UnicodeDecodeError, the port raises UnicodeError with
# their message (tests/deviations/lib_urllib_parse.py): the cases print the message.
import urllib.parse
from urllib.parse import (parse_qs, parse_qsl, quote, quote_plus, unquote, unquote_plus,
                          urldefrag, urlencode, urljoin, urlparse, urlsplit, urlunparse,
                          urlunsplit)


def digest(xs: list[str]) -> int:
    # a digest of the strs' ascii(), which escapes their characters as CPython's does
    h = 0
    for x in xs:
        for c in ascii(x):
            h = (h * 131 + ord(c)) % 1000000007
        h = (h * 131 + 10) % 1000000007
    return h


def q(s: str, safe: str = "/", encoding: str = "utf-8", errors: str = "strict") -> str:
    try:
        return quote(s, safe, encoding, errors)
    except UnicodeError as e:
        return "UnicodeError: " + str(e)
    except LookupError as e:
        return "LookupError: " + str(e)


def u(s: str, encoding: str = "utf-8", errors: str = "replace") -> str:
    try:
        return ascii(unquote(s, encoding, errors))
    except UnicodeError as e:
        return "UnicodeError: " + str(e)
    except LookupError as e:
        return "LookupError: " + str(e)
    except TypeError as e:
        return "TypeError: " + str(e)


def esc(bs: list[int]) -> str:
    # the percent-escapes of the bytes bs
    return "".join(["%%%02X" % b for b in bs])


print("-- quote")
never = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-~"
print(quote(never) == never, quote_plus(never) == never)
ascii_chars = "".join(["%c" % i for i in range(128)])
print(quote(ascii_chars))
print(quote(ascii_chars, safe=""))
print(quote_plus(ascii_chars))
print(quote_plus(ascii_chars, safe="/ "))
print(quote("<>", safe="<>"), quote_plus("<>", safe="<>"))
print(quote("a\xfcb", encoding="latin-1", safe="\xfc"), quote("a\xfcb", encoding="latin-1", safe=""))
print(quote("ab[]cd"), quote_plus("ab[]cd"))
print(quote(" "), quote_plus(" "), quote("a b cd e f"), quote_plus("a b cd e f"))
print(quote_plus("alpha+beta gamma"), quote_plus("alpha+beta gamma", "+"))
print(quote(""), quote_plus(""), repr(quote("", encoding="nosuch")))
print(quote("\xa2\xd8ab\xff"), quote("\xa2\xd8ab\xff", encoding=None, errors=None))
print(quote("\xa2\xd8ab\xff", encoding="latin-1"))
print(quote("\u6f22\u5b57"), q("\u6f22\u5b57", encoding="latin-1"))
print(quote("\u6f22\u5b57", encoding="latin-1", errors="replace"))
print(quote("\u6f22\u5b57", encoding="latin-1", errors="xmlcharrefreplace"))
print(quote_plus("\xa2\xd8 \xff", encoding="latin-1"))
print(quote_plus("ab\u6f22\u5b57 cd", encoding="latin-1", errors="replace"))
print(quote("caf\xe9 cr\xe8me/\u20ac?\U0001f600", safe="/?"))
print(quote("caf\xe9", safe="\xe9"), quote("%41%", safe="%"), quote("a/b:c@d", safe=":@"))
print(quote("~-._", safe=""), quote("\x00\x7f"))
for enc in ["utf-8", "UTF8", "u8", "utf_8", " utf-8 ", "cp65001", "latin-1", "Latin1", "ISO-8859-1",
            "iso8859_1", "L1", "8859", "cp819", "ascii", "US-ASCII", "646", "ANSI_X3.4-1968",
            "iso_646.irv:1991", "us"]:
    print(repr(enc), q("\xe9\u20ac", "", enc, "backslashreplace"), q("\xe9", "", enc))
for errors in ["strict", "ignore", "replace", "backslashreplace", "xmlcharrefreplace",
               "surrogateescape", "surrogatepass", "nosuch", "Strict"]:
    print(errors, q("a\xe9\u20ac\U0001f600b", "", "ascii", errors), q("\xe9\u20ac\U0001f600", "", "latin-1", errors))
    print(errors, q("x" + "%c" % 0xD800 + "%c" % 0xDFFF + "y" + "%c" % 0xDCE9, "", "utf-8", errors))
    print(errors, q("%c" % 0xDC80 + "%c" % 0xDCFF + "%c" % 0xDC7F, "", "latin-1", errors), q("%c" % 0xDCE9, "", "ascii", errors))
    print(errors, q("ok", "", "utf-8", errors), q("\xe9", "", "utf-8", errors))

some_s: str | None = "a b+%41"
none_s: str | None = None
print(quote(some_s), quote_plus(some_s), unquote(some_s), unquote_plus(some_s), quote(some_s, encoding="latin-1"))
try:
    print(quote(none_s))
except TypeError as e:
    print("TypeError:", e)
try:
    print(quote_plus(none_s, safe="/"))
except TypeError as e:
    print("TypeError:", e)
try:
    print(unquote(none_s))
except TypeError as e:
    print("TypeError:", e)
try:
    print(unquote_plus(none_s))
except AttributeError as e:
    print("AttributeError:", e)

print("-- unquote")
for i in range(128):
    if unquote("%%%02x" % i) != "%c" % i or unquote_plus("%%%02X" % i) != "%c" % i:
        print("unquote", i)
print(unquote("".join(["%%%02x" % i for i in range(128)])).count("%"))
for s in ["%xab", "%x", "%", "%%", "%2", "%G0", "%%41", "%4%41", "abc", "", "%20%2", "a%2xb%41"]:
    print(repr(s), repr(unquote(s)), repr(unquote_plus(s)))
print(unquote("ab%sd" % "%63"), unquote_plus("ab%sd" % "%63"))
print(unquote("are+there+spaces..."), unquote_plus("are+there+spaces..."))
print(ascii(unquote("br%C3%BCckner_sapporo_20050930.doc")), ascii(unquote("br%C3%BCckner", encoding=None, errors=None)))
print(ascii(unquote("br%FCckner_sapporo_20050930.doc", encoding="latin-1")))
print(ascii(unquote("%E6%BC%A2%E5%AD%97")), ascii(unquote("%F3%B1")), ascii(unquote("%F3%B1", errors="replace")))
print(ascii(unquote("%F3%B1", errors="ignore")), ascii(unquote("\u6f22%C3%BC")), ascii(unquote("\u6f22%FC", encoding="latin-1")))
print(ascii(unquote("%Ab%eA", encoding="latin-1")), ascii(unquote("caf%C3%A9 cr%C3%A8me")), ascii(unquote_plus("caf%C3%A9+cr%C3%A8me")))
print(ascii(unquote("\xe9%C3%A9\u20ac%E2%82%AC\U0001f600%F0%9F%98%80")))
print(ascii(unquote("%C3\xe9%A9")), ascii(unquote("%E2%82\xe9%AC")), ascii(unquote("x%C3")), ascii(unquote("%C3x")))
for errors in ["replace", "ignore", "backslashreplace", "surrogateescape", "surrogatepass", "strict",
               "xmlcharrefreplace", "namereplace", "nosuch"]:
    print(errors, u("a%E9b%C3%A9%ED%A0%80%ED%A0c%F0%9F%98", "utf-8", errors), u("%ED%B3%A9%ED%A0%80", "utf-8", errors))
    print(errors, u("a%E9b%C3%A9", "ascii", errors), u("%41", "ascii", errors), u("%e9", "latin-1", errors))
for enc in ["UTF-8", "utf8", "latin1", "ISO8859-1", "ASCII", "us_ascii"]:
    print(enc, u("%C3%A9%E9", enc), u("%C3%A9%E9", enc, "strict"))

print("-- parse_qsl and parse_qs")
for qs in ["", "&", "&&", "=", "=a", "a", "a=", "a=b=c", "a%3Db=c", "a=b&c=d", "a=b%26c=d", "&a=b",
           "a=a+b&b=b+c", "a=1&a=2", ";a=b", "a=a+b;b=b+c", "\u0141=\xe9", "%C5%81=%C3%A9", "%81=%A9",
           "a=%ZZ", "x=1&&y=%7E&z", "  a = b  "]:
    print(repr(qs), parse_qsl(qs, keep_blank_values=True), parse_qsl(qs, keep_blank_values=False))
    print(" ", parse_qs(qs, keep_blank_values=True), parse_qs(qs))
for qs in [";", ";;", ";a=b", "a=a+b;b=b+c", "a=1;a=2", "a=1&b=2;c=3"]:
    print(repr(qs), parse_qsl(qs, separator=";"), parse_qs(qs, separator=";"))
print(parse_qsl("a=1<>b=2<>c", True, separator="<>"), parse_qs("a=1&b=2", True, False))
print(parse_qs("key=\u0141%E9", encoding="latin-1"), parse_qs("key=\u0141%C3%A9", encoding="utf-8"))
print(parse_qs("key=\u0141%C3%A9", encoding="ascii"), parse_qs("key=\u0141%E9-", encoding="ascii"))
print(parse_qs("key=\u0141%E9-", encoding="ascii", errors="ignore"))
print(parse_qsl("key=\u0141%E9", encoding="latin-1"), parse_qsl("k=%E9", errors="backslashreplace"))
print(len(parse_qsl("&".join(["a=a"] * 10), max_num_fields=10)))
for args in ["a=a&" * 10 + "a=a", "a=1;b=2", "a=1&b"]:
    try:
        print(parse_qsl(args, max_num_fields=10, strict_parsing=True, separator=";"))
    except ValueError as e:
        print("ValueError:", e)
for qs in ["a=1&b", "a=1&&b=2", "a=1&\xe9", "=&a=b", "a=b&"]:
    try:
        print(parse_qsl(qs, strict_parsing=True))
    except ValueError as e:
        print("ValueError:", e)
    try:
        print(parse_qs(qs, True, True))
    except ValueError as e:
        print("ValueError:", e)
try:
    parse_qsl("a=b", separator="")
except ValueError as e:
    print("ValueError:", e)
try:
    print(parse_qsl("a=%E9", errors="strict"))
except UnicodeError as e:
    print("UnicodeError:", e)
d = parse_qs("q=caf%C3%A9+cr%C3%A8me&page=2&filter=color%3Ared&filter=size%3AM&q=t%C3%A9")
print(d, sorted(d), d["q"], d.get("page"), len(d["filter"]))

print("-- urlencode")
print(urlencode({"1st": "1", "2nd": "2", "3rd": "3"}), urlencode([("1st", "1"), ("2nd", "2"), ("3rd", "3")]))
print(urlencode({"&": "="}), urlencode({"key name": "A bunch of pluses"}))
print(urlencode({"sequence": ["1", "2", "3"]}), urlencode({"sequence": ["1", "2", "3"]}, True))
empty: dict[str, str] = {}
no_pairs: list[tuple[str, str]] = []
print(repr(urlencode(empty)), repr(urlencode(no_pairs)), urlencode({"a": 1}), urlencode({"a": [1, 2]}, True))
print(urlencode({"a": [1, 2], "b": [3, 4, 5]}, True), urlencode({"a": (3, 4, 5)}, True), urlencode({"a": 5}, True))
print(urlencode({"a": 1.5, "b": 2.0}), urlencode({"a": True}, doseq=True), urlencode({1: "x", 22: "y"}))
print(urlencode((("\u00a0", "\u00c1"),), encoding="ASCII", errors="replace"), urlencode((("\u00a0", "\u00c1"),)))
print(urlencode((("\u00a0", "\u00c1"),), encoding="latin-1"), urlencode((("\u00a0", "\u00c1"),), doseq=True, encoding="ASCII", errors="replace"))
print(urlencode((("\u00a0", ("1", "\u00c1")),), True, encoding="ASCII", errors="replace"))
print(urlencode((("\u00a0", ("42", "\u00c1")),), True), urlencode((("\u00a0", ("42", "\u00c1")),), True, encoding="latin-1"))
print(urlencode({"a": "some value"}), urlencode({"a": "some value/another"}, quote_via=quote))
print(urlencode({"a": "some value/another"}, safe="/", quote_via=quote), urlencode({"a/b": "c d:e"}, safe=":/"))
print(urlencode({"q": "caf\xe9 cr\xe8me", "n": "\u20ac\U0001f600"}), urlencode({"q": "caf\xe9"}, encoding="latin-1"))
print(urlencode({"a": ["\xe9", "b c"]}, True, "", "latin-1"), urlencode([("a", "1"), ("a", "2"), ("b", "")]))
print(urlencode({"x": ["\u6f22"]}, True, encoding="latin-1", errors="xmlcharrefreplace"))
opt: dict[str, str | None] = {"a": "x", "b": None}
print(urlencode(opt), urlencode(opt, True))
try:
    urlencode({"a": "\u6f22"}, encoding="latin-1")
except UnicodeError as e:
    print("UnicodeError:", e)
try:
    urlencode("foo")
except TypeError as e:
    print("TypeError:", e)

print("-- urlsplit, urlparse, urlunsplit, urlunparse")
cases = ["path/to/file", "/path/to/file", "//path/to/file", "////path/to/file", "/////path/to/file",
         "scheme:path/to/file", "scheme:/path/to/file", "scheme://path/to/file", "scheme:////path/to/file",
         "scheme://///path/to/file", "file:tmp/junk.txt", "file:///tmp/junk.txt", "file:////tmp/junk.txt",
         "file://///tmp/junk.txt", "http:tmp/junk.txt", "http://example.com/tmp/junk.txt",
         "http:///example.com/tmp/junk.txt", "http:////example.com/tmp/junk.txt",
         "imap://mail.python.org/mbox1", "mms://wms.sys.hinet.net/cts/Drama/09006251100.asf",
         "nfs://server/path/to/file.txt", "svn+ssh://svn.zope.org/repos/main/ZConfig/trunk/",
         "git+ssh://git@github.com/user/project.git",
         "itms-services://?action=download-manifest&url=https://example.com/app",
         "+scheme:path/to/file", "sch_me:path/to/file", "sch\xe8me:path/to/file", "///path/to/file",
         "scheme:///path/to/file", "file:/tmp/junk.txt", "http:/tmp/junk.txt", "https:/tmp/junk.txt",
         "http://www.python.org", "http://www.python.org#abc", "https://www.python.org?q=abc",
         "http://www.python.org/#abc", "https://a/b/c/d;p?q#f", "Python", "./Python",
         "x-newscheme://foo.com/stuff", "x://y", "x:/y", "x:/", "/", "mailto:1337@example.org",
         "http://example.com?blahblah=/foo", "path", "//www.python.org:80", "http://www.python.org:80",
         "http:80", "https:80", "path:80", "http:", "https:", "s3://foo.com/stuff",
         "x-newscheme://foo.com/stuff?query#fragment", "x-newscheme://foo.com/stuff?query",
         "tel:+31-641044153", "tel:123-4;phone-context=+1-650-516", "tel:7042;phone-context=example.com",
         "sip:alice@atlanta.com;maddr=239.255.255.1;ttl=15", "http://User:Pass@www.python.org:080/doc/?query=yes#frag",
         "\x00\x01 \x1f\x20http://u@h/p?q#f", "www.pypi.org ", "https://www.python.org:88/doc/?query=    ",
         "http\t://www.python\n.org\t/java\nscript:\talert('msg\r\n')/?query\n=\tsomething#frag\nment",
         ".://www.example.net", "+://x", "-://x", "0://x", "http&://x", "\u0966http://x",
         "http://[::1]:5432/foo/", "http://[dead:beef:cafe:5417:affe:8FA3:deaf:feed]/foo/",
         "http://[::12.34.56.78]:/foo/", "http://[::ffff:12.34.56.78]/foo/",
         "scheme://user@[v6a.ip]:1234/path?query", "scheme://user@[0439:23af:2309::fae7%test]/path?query",
         "scheme://user@[0439:23af:2309::fae7:1234:192.0.2.146%test]/path?query",
         "http://[FE80::822a:a8ff:fe49:470c%tESt]:1234", "http://\u30d5\u309a:80", "http://caf\xe9.example/x",
         "HTTP://Example.COM/A", "a:b:c", "1a:b", "http://a@b@c/d", "http://h/p;a;b?q", "http://h/p/;a"]
for url in cases:
    sr = urlsplit(url)
    pr = urlparse(url)
    print(ascii(url), sr, pr, ascii(urlunsplit(sr)), ascii(urlunparse(pr)), sr.geturl() == urlunsplit(sr), pr.geturl() == urlunparse(pr))
for url in ["http://::12.34.56.78]/", "http://[::1/foo/", "ftp://[::1/foo/bad]/bad", "http://[::1/foo/bad]/bad",
            "http://[::ffff:12.34.56.78", "Scheme://user@[192.0.2.146]/Path?Query",
            "Scheme://user@[important.com:8000]/Path?Query", "Scheme://user@[v123r.IP]/Path?Query",
            "Scheme://user@[v12ae]/Path?Query", "Scheme://user@[v.IP]/Path?Query", "Scheme://user@[v123.]/Path?Query",
            "Scheme://user@[v]/Path?Query", "Scheme://user@[0439:23af::2309::fae7:1234]/Path?Query",
            "Scheme://user@[0439:23af:2309::fae7:1234:2342:438e:192.0.2.146]/Path?Query", "Scheme://user@]v6a.ip[/Path",
            "scheme://prefix.[v6a.ip]", "scheme://[v6a.ip].suffix", "scheme://prefix.[::1]:a", "scheme://[::1].suffix:1a",
            "scheme://[::1]x", "scheme://[]", "scheme://[::1%]", "scheme://[::1%a%b]", "scheme://[1.2.3.4.5]",
            "scheme://[::01.2.3.4]", "scheme://[::256.2.3.4]", "scheme://[1:2:3:4:5:6:7:8:9]", "scheme://[:1::]",
            "scheme://[1::2:]", "scheme://[12345::]", "scheme://[\u0661::]", "scheme://[1:2:3:4:5:6:7::]",
            "scheme://[1:2:3:4:5:6::7:8]", "scheme://[::1:2:3:4:5:6:7]", "scheme://[1:2:3:4:5:6:1.2.3.4]",
            "scheme://[1:2:3:4:5:6:7:1.2.3.4]", "scheme://[0123:4567:89ab:cdef:0123:4567:89ab:cdef]",
            "scheme://[" + "1:" * 30 + "1]", "scheme://[v1.:]", "scheme://[V0.x\n]", "http://\u30d5\u309a\ufe1380",
            "http://netloc\u2100false.netloc/path", "http://n\uff03user@netloc/path", "http://a\u2a74b/",
            "http://a\uff1fb/", "http://u\ufe6bh/", "http://\u2047x/", "http://a\u2050b/"]:
    try:
        print(ascii(url), urlsplit(url))
    except ValueError as e:
        print(ascii(url), "ValueError:", ascii(str(e)))
for url in ["http:#frag", "//example.net#frag", "index.html#frag", ";a=b#frag", "?a=b#frag", "#frag",
            "abc#@frag", "//abc#@frag", "//abc:80#@frag", "//abc#@frag:80"]:
    print(url, urlsplit(url, allow_fragments=False), urlparse(url, "", False), urlsplit(url, "", True).fragment)
print(urlparse("http://example.net/", "ftp").scheme, urlsplit("path", "ftp").scheme, urlparse("path", scheme="ftp").scheme)
print(urlsplit("http://www.python.org/javascript:alert('msg')/?query=something#fragment", scheme="ht\ntp"))
print(urlsplit("//www.python.org/", scheme="\x00 https \x1f").geturl())
r = urlsplit("https://user@www.example.com:8080/a/b/c?q=1&r=2#frag")
scheme, netloc, path, query, fragment = r
print(r, r[1], r[-1], len(r), r.netloc, r.query, scheme, netloc, path, query, fragment)
print(r == ("https", "user@www.example.com:8080", "/a/b/c", "q=1&r=2", "frag"), r._replace(fragment=""), r._replace(path="/x").geturl())
pr = urlparse("http://h/p;x?y#z")
print(pr, pr.params, pr._replace(params="").geturl(), urlunparse(("http", "h", "/p", "x", "y", "z")))
print(urlunsplit(("http", "h", "p", "", "")), urlunsplit(("", "", "//p", "", "")), urlunsplit(("file", "", "", "", "")))

print(urllib.parse.__name__, urllib.parse.uses_relative[:4], len(urllib.parse.uses_netloc), urllib.parse.uses_params[-3:])
print(urllib.parse.scheme_chars, urllib.parse.unwrap("<URL:type://host/path>"), urllib.parse.unwrap(" <x> "))

print("-- urljoin and urldefrag")
joins = ["g:h", "g", "./g", "g/", "/g", "//g", "g?y", "g?y/./x", "#s", "g#s", "g#s/./x", "g?y#s", "g;x", "g;x?y#s",
         ".", "./", "..", "../", "../g", "../..", "../../", "../../g", "", "g.", ".g", "g..", "..g", "./../g", "./g/.",
         "g/./h", "g/../h", "g;x=1/./y", "g;x=1/../y", "g?y/../x", "g#s/../x", "?y", ";x", "../../../g",
         "../../../../g", "/./g", "/../g", "http:g", "http:", "http:?y", "http:g?y", "http:g?y/./x", "g/../../../h/./i"]
for base in ["http://a/b/c/d;p?q#f", "http://a/b/c/d;p?q", "http://a/b/c/d", "http://a/b/c/d/", "http://a/b/c/de"]:
    print(base)
    print(" ", " ".join([urljoin(base, rel) for rel in joins]))
for base, rel in [("http:///", ".."), ("", "http://a/b/c/g?y/./x"), ("", "http://a/./g"), ("svn://pathtorepo/dir1", "dir2"),
                  ("svn+ssh://pathtorepo/dir1", "dir2"), ("ws://a/b", "g"), ("wss://a/b", "g"),
                  ("http://a/b/c/d/e/", "../../f/g/"), ("http://a/b/c/d/e", "../../f/g/"), ("http://a/b/c/d/e/", "/../../f/g/"),
                  ("http://a/b/c/d/e", "/../../f/g/"), ("http://a/b/c/d/e/", "../../f/g"), ("http://a/b/", "../../f/g/"),
                  ("a", "b"), ("http://a/b/c", ""), ("http://a/b", "//c/d"), ("mailto:x@y", "z"), ("http://a//b//c", "../d"),
                  ("http://a/b/c/d;p?q", "g;x=1/./y"), ("https://a/b", "http://c/d"), ("http://a/b", "x/y/z/../../w")]:
    print(repr(base), repr(rel), urljoin(base, rel), urljoin(base, urlunsplit(urlsplit(rel))))
for url in ["http://python.org#frag", "http://python.org", "http://python.org/#frag", "http://python.org/",
            "http://python.org/?q#frag", "http://python.org/?q", "http://python.org/p#frag", "http://python.org/p?q",
            "http://a/b/c/d;p?q#f", "http://a/b/c/d;p?q", "#x", "a#b#c"]:
    df = urldefrag(url)
    print(url, df, df.url, df.fragment, df.geturl(), df == (df.url, df.fragment))
url2, frag = urldefrag("http://h/p#f")
print(url2, frag)

print("-- every percent-escape of one byte, and of two to four from each class of bytes CPython's decoder tells apart")
singles = [esc([b]) for b in range(256)]
for errors in ["replace", "surrogateescape", "strict"]:
    print(errors, digest([u(s, "utf-8", errors) for s in singles]), digest([u(s, "ascii", errors) for s in singles]))
print(digest([u(s, "latin-1", "strict") for s in singles]))
print(u(singles[0xE9], "utf-8", "strict"), u(singles[0xE9], "ascii", "strict"), u(singles[0x80], "utf-8", "strict"))
# ASCII, the continuation bytes below 0x90, 0xA0 and above, the bytes that begin no character, those
# that begin two bytes, three (E0 and ED take other second bytes) and four (F0 and F4 too); after
# the second byte, where no byte value is special, ASCII, continuation bytes and those that begin
classes = [0x41, 0x80, 0x8F, 0x90, 0x9F, 0xA0, 0xBF, 0xC0, 0xC2, 0xDF, 0xE0, 0xE1, 0xED, 0xEF, 0xF0, 0xF1,
           0xF4, 0xF5]
later = [0x41, 0x80, 0xBF, 0xC0, 0xC2, 0xE0, 0xED, 0xF0, 0xF5]
pairs: list[str] = []
for b1 in classes:
    for b2 in classes:
        pairs.append(esc([b1, b2]))
for errors in ["replace", "surrogateescape", "strict"]:
    print(len(pairs), errors, digest([u(s, "utf-8", errors) for s in pairs]))
triples: list[str] = []
for b1 in [0xE0, 0xE1, 0xED, 0xEF, 0xF0, 0xF1, 0xF4]:
    for b2 in classes:
        for b3 in later:
            triples.append(esc([b1, b2, b3]))
for errors in ["surrogateescape", "strict"]:
    print(len(triples), errors, digest([u(s, "utf-8", errors) for s in triples]))
print(digest([u(s, "utf-8", "surrogatepass") for s in triples if s.startswith("%ED") or s.startswith("%E0")]))
quads: list[str] = []
for b1 in [0xF0, 0xF1, 0xF4]:
    for b2 in classes:
        for b3 in [0x41, 0x80, 0xC2]:
            for b4 in [0x41, 0x80, 0xC2]:
                quads.append(esc([b1, b2, b3, b4]))
for errors in ["surrogateescape", "strict"]:
    print(len(quads), errors, digest([u(s, "utf-8", errors) for s in quads]))
print(u("%F0%9F%98%80%F4%8F%BF%BF%F4%90%80%80%ED%9F%BF%EE%80%80%EF%BF%BF%E0%A0%80%DF%BF%C2%80", "utf-8", "surrogateescape"))
print(u("a%C3%A9%E9%80%80%C3x%F0%9F%98%E2%82%AC%ED%A0%80%ED%B0%80%F8", "utf-8", "backslashreplace"))

print("-- code points at the ends of each length of UTF-8, and surrogates, quoted and unquoted")
cps = [0, 0x41, 0x7F, 0x80, 0xA0, 0xE9, 0xFF, 0x100, 0x7FF, 0x800, 0xFFF, 0x1000, 0xD7FF, 0xD800, 0xDB7F, 0xDB80,
       0xDBFF, 0xDC00, 0xDC7F, 0xDC80, 0xDCE9, 0xDCFF, 0xDD00, 0xDFFF, 0xE000, 0xFFFD, 0xFFFF, 0x10000, 0x1F600,
       0xFFFFF, 0x100000, 0x10FFFF]
for cp in range(0, 0x110000, 0x8009):
    cps.append(cp)
chars = ["%c" % cp for cp in cps]
for enc, errors in [("utf-8", "strict"), ("utf-8", "surrogatepass"), ("utf-8", "surrogateescape"), ("utf-8", "replace"),
                    ("latin-1", "strict"), ("latin-1", "backslashreplace"), ("latin-1", "xmlcharrefreplace"),
                    ("ascii", "surrogateescape"), ("ascii", "ignore")]:
    quoted = [q(c, "", enc, errors) for c in chars]
    print(len(quoted), enc, errors, digest(quoted), digest([u(x, enc, "surrogatepass") for x in quoted if not x.startswith("Unicode")]))
print(quote("".join(chars[2:7]) + "%c" % 0x7FF + "%c" % 0x800), quote("%c" % 0xFFFF + "%c" % 0x10000 + "%c" % 0x10FFFF))
mixed = "".join(chars)
print(len(quote(mixed, errors="surrogatepass")), unquote(quote(mixed, errors="surrogatepass"), errors="surrogatepass") == mixed)
print(q(mixed, "", "utf-8"), q(mixed, "", "latin-1", "surrogateescape"))
