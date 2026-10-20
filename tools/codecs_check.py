"""Check lib/_pystachy_codecs.py on CPython against CPython's C _codecs module.

This checks the port's source, not compiled Pystachy (tests/programs/library/lib_codecs.py compares that): for
random arguments of the functions the port implements (the UTF-8, Latin-1, ASCII and charmap
codecs, encode(), decode(), lookup_error() and readbuffer_encode()), with every error handler, the
port must return what the C module returns, or raise the same exception with the same message.
The charmap codec runs on the decoding tables of the standard library's encodings.cp* modules and
on random tables. The other functions must raise NotImplementedError, and every function must have
the C module's signature.
Usage: python3 -I tools/codecs_check.py [--rounds N]
"""
import _codecs
import argparse
import importlib
import importlib.util
import inspect
from pathlib import Path
import random
import sys

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.dont_write_bytecode = True  # (no __pycache__ in lib/)
HANDLERS = [None, "strict", "replace", "ignore", "backslashreplace", "xmlcharrefreplace", "surrogateescape",
            "surrogatepass", "nope"]
DONE = {"utf_8_encode", "utf_8_decode", "latin_1_encode", "latin_1_decode", "ascii_encode", "ascii_decode",
        "charmap_build", "charmap_encode", "charmap_decode", "encode", "decode", "lookup_error", "register_error",
        "readbuffer_encode", "register", "unregister", "_unregister_error", "_forget_codec"}
# the C module's functions the port has as NotImplementedError (lookup(): no codec registry)
LATER = {"lookup", "utf_7_encode", "utf_7_decode", "utf_16_encode", "utf_16_le_encode", "utf_16_be_encode",
         "utf_16_decode", "utf_16_le_decode", "utf_16_be_decode", "utf_16_ex_decode", "utf_32_encode",
         "utf_32_le_encode", "utf_32_be_encode", "utf_32_decode", "utf_32_le_decode", "utf_32_be_decode",
         "utf_32_ex_decode", "unicode_escape_encode", "unicode_escape_decode", "raw_unicode_escape_encode",
         "raw_unicode_escape_decode", "escape_encode", "escape_decode"}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def outcome(f, args):
    try:
        return repr(f(*args))
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def tables():
    # the decoding tables (str) of the standard library's table codecs
    out = []
    for name in ("cp1252", "cp1250", "cp1251", "cp437", "cp850", "cp866", "cp037", "iso8859_15", "koi8_r",
                 "mac_roman", "cp874", "cp1255", "hp_roman8", "iso8859_7"):
        try:
            m = importlib.import_module("encodings." + name)
        except ImportError:
            continue
        if isinstance(getattr(m, "decoding_table", None), str):
            out.append(m.decoding_table)
    return out


def text(gen, n):
    # a str of n characters from ASCII, Latin-1, the BMP, astral planes and lone surrogates
    pools = [range(0x20, 0x7F), range(0x80, 0x100), range(0x100, 0x3000), range(0x1F600, 0x1F650),
             range(0xDC80, 0xDD00), range(0xD800, 0xD810), range(0, 0x20)]
    return "".join(chr(gen.choice(gen.choice(pools))) for i in range(n))


def utf8ish(gen, n):
    # bytes of n pieces: ASCII, valid UTF-8 sequences, their prefixes, stray bytes
    out = bytearray()
    for i in range(n):
        k = gen.randrange(6)
        if k == 0:
            out.append(gen.randrange(0x80))
        elif k <= 2:
            c = chr(gen.choice([gen.randrange(0x80, 0x800), gen.randrange(0x800, 0xD800), gen.randrange(0xE000, 0x10000),
                                gen.randrange(0x10000, 0x110000)]))
            b = c.encode("utf-8")
            out += b if k == 1 else b[:gen.randrange(1, len(b) + 1)]
        elif k == 3:
            out += bytes([gen.choice([0xE0, 0xED, 0xF0, 0xF4, 0xC0, 0xC1, 0xF5, 0xFF, 0x80, 0xBF]), gen.randrange(0x80, 0xC0)])
        else:
            out.append(gen.randrange(256))
    return bytes(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=6000)
    options = parser.parse_args()
    port = load("_codecs_port", LIB / "_pystachy_codecs.py")
    gen = random.Random(20261016)
    tabs = tables()
    count = failures = 0

    def check(name, args):
        nonlocal count, failures
        count += 1
        want = outcome(getattr(_codecs, name), args)
        got = outcome(getattr(port, name), args)
        if got != want:
            failures += 1
            if failures <= 20:
                print(f"{name}{args!r}: {got}, where CPython's is {want}")

    for r in range(options.rounds):
        s = text(gen, gen.randrange(0, 12))
        b = utf8ish(gen, gen.randrange(0, 8))
        e = gen.choice(HANDLERS)
        for name in ("utf_8_encode", "latin_1_encode", "ascii_encode"):
            check(name, (s, e))
        check("utf_8_decode", (b, e, gen.random() < 0.5))
        check("latin_1_decode", (b, e))
        check("ascii_decode", (b, e))
        check("readbuffer_encode", (b, e))
        enc = gen.choice(["utf-8", "UTF8", "latin-1", "iso-8859-1", "ascii", "us-ascii", "nope"])
        check("encode", (s, enc, e or "strict"))
        check("encode", (b, enc))
        check("decode", (b, enc, e or "strict"))
        check("decode", (s, enc))
        # charmap: a table of the standard library or a random one, with undefined entries
        if gen.random() < 0.6 and tabs:
            t = gen.choice(tabs)
        else:
            t = "".join(chr(gen.choice([gen.randrange(0x20, 0x7F), gen.randrange(0x80, 0x2000), 0xFFFE]))
                        for i in range(gen.choice([256, 256, 128, 10])))
        check("charmap_decode", (bytes(gen.randrange(256) for i in range(gen.randrange(0, 10))), e, t))
        check("charmap_decode", (b, e, None))
        m = _codecs.charmap_build(t)
        mine = port.charmap_build(t)
        pm = {}
        for cp in range(0x2100):
            v = m.get(cp) if isinstance(m, dict) else None
            if v is None and not isinstance(m, dict):
                try:
                    v = _codecs.charmap_encode(chr(cp), "strict", m)[0][0]
                except UnicodeEncodeError:
                    v = None
            if v is not None:
                pm[cp] = v
        count += 1
        if {k: v for k, v in mine.items() if k < 0x2100} != pm:
            failures += 1
            print("charmap_build differs for a table")
        chars = "".join(gen.choice([gen.choice(t), chr(gen.randrange(0x20, 0x3000)), "?", "&", "#", ";", "\\", "x",
                                    chr(gen.randrange(0xDC80, 0xDD00))]) for i in range(gen.randrange(0, 8)))
        count += 1
        want = outcome(_codecs.charmap_encode, (chars, e, m))
        got = outcome(port.charmap_encode, (chars, e, mine))
        if got != want:
            failures += 1
            if failures <= 20:
                print(f"charmap_encode({chars!r}, {e!r}, map of {t[:8]!r}...): {got}, where CPython's is {want}")
        check("charmap_encode", (s, e, None))
    for name in ("strict", "replace", "ignore", "backslashreplace", "xmlcharrefreplace", "namereplace", "surrogateescape",
                 "surrogatepass", "nope"):
        count += 1
        want = outcome(lambda n: _codecs.lookup_error(n).__name__, (name,))
        got = outcome(lambda n: port.lookup_error(n).__name__, (name,))
        if want.startswith("LookupError") != got.startswith("LookupError") or (want.startswith("LookupError") and got != want):
            failures += 1
            print(f"lookup_error({name!r}): {got}, where CPython's is {want}")
    print(f"{count} calls, {failures} differ")
    names = sorted(n for n in dir(_codecs) if not n.startswith("__"))
    differ = []
    for n in names:
        f = getattr(port, n, None)
        want = getattr(_codecs, n).__text_signature__.replace("$module, /, ", "").replace("$module, ", "")
        got = "missing" if f is None else str(inspect.signature(f)).split(" -> ")[0]
        for t in (": bytes", ": bool", ": int", ": str | None", ": str", ": dict[int, int] | None",
                  ": Callable[[UnicodeError], tuple[str, int]]"):
            got = got.replace(t, "")
        got = got.replace("(s, ", "(str, ").replace("(s)", "(str)")  # (a positional-only parameter's name)
        if got.replace(" = ", "=") != want.replace("\n", "").replace("                 ", " "):
            differ.append(n)
            print(f"{n}: signature {got}, where CPython's is {want}")
    unsupported = [n for n in LATER if "NotImplementedError" not in outcome(
        getattr(port, n), ("utf-8",) if n == "lookup" else (b"", None) if "decode" in n else ("", None))]
    for n in unsupported:
        print(f"{n}: does not raise NotImplementedError")
    missing = [n for n in names if n not in DONE and n not in LATER]
    print(f"{len(names)} functions ({len(DONE)} implemented), {len(differ)} signatures differ"
          + (f"; neither implemented nor listed: {' '.join(missing)}" if missing else ""))
    return 1 if failures or differ or unsupported or missing else 0


if __name__ == "__main__":
    sys.exit(main())
