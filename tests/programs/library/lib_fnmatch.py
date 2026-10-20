# lib/fnmatch: CPython 3.13's fnmatch, ported over lib/re. translate() of each pattern must be
# CPython's regular expression, character for character, and fnmatch(), fnmatchcase() and
# filter() must give CPython's answers. _compile_pattern() caches the compiled patterns, as
# CPython's does, so its statistics show which calls compiled a pattern.
import fnmatch

PATTERNS = [
    "", "*", "**", "***", "?", "??*", "a", "abc", "*.py", "*.py?", "test_*.py", "a*b*c", "*a*",
    "a**b", "*x*y*", ".*", "[abc]", "[!abc]", "[a-z]", "[a-z0-9_]", "[z-a]", "[]]", "[!]]", "[^x]",
    "[[]", "[", "[abc", "[a-]", "[-a]", "[a--b]", "[!]", "[\\]", "[a-c-e]", "[a&&b]", "[~x]",
    "[|x]", "a.b+c(d)|e^f$g\\h{i}", "src/**/*.c", "*/build/*", "[!.]*", "?.[ch]", "[*?[]",
    "caf?.txt", "中*", "*é*",
]
for p in PATTERNS:
    print(repr(p), fnmatch.translate(p))

NAMES = ["", "a", "b", "abc", "abd", "a.py", "test_x.py", "test_.py", "tests/test_x.py",
         "src/a/b/x.c", "src/x.c", "x/build/y", "build/y", ".hidden", "x.c", "x.h", "x.ch",
         "]", "[", "-", "^", "!", "\\", "a-b", "&", "~", "|", "a.b+c(d)|e^f$g\\h{i}", "*", "?",
         "café.txt", "cafe.txt", "中文", "été", "aXbYc", "abc\nd"]
for p in PATTERNS:
    hits = [n for n in NAMES if fnmatch.fnmatchcase(n, p)]
    print(repr(p), hits)

nothing: list[str] = []
print(fnmatch.filter(NAMES, "*.py"), fnmatch.filter(NAMES, "[a-c]*"), fnmatch.filter(nothing, "*"))
print(fnmatch.fnmatch("README.MD", "*.md"), fnmatch.fnmatch("readme.md", "*.md"),
      fnmatch.fnmatchcase("README.MD", "*.MD"))
info = fnmatch._compile_pattern.cache_info()
print(info.hits, info.misses, info.maxsize, info.currsize)

# a pattern compiled once serves each later call: the cache keeps CPython's counts
for i in range(1000):
    fnmatch.fnmatchcase(f"file{i}.py", "file*.py")
print(fnmatch._compile_pattern.cache_info())
fnmatch._compile_pattern.cache_clear()
print(fnmatch.filter(["x.py", "y.c"], "*.c"), fnmatch._compile_pattern.cache_info())
