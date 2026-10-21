# ini2toml: two ports in one program. iniconfig (ports/iniconfig) reads INI text and tomli_w
# (ports/tomli_w) writes it as TOML: a section becomes a table, and a value continued on more
# lines a multiline string.
from iniconfig import IniConfig
import tomli_w


def ini2toml(path: str, text: str) -> str:
    cfg = IniConfig(path, text)
    doc: dict[str, dict[str, str]] = {}
    for sec in cfg.sections:
        table: dict[str, str] = {}
        for key in cfg.sections[sec]:
            table[key] = cfg[sec][key]
        doc[sec] = table
    return tomli_w.dumps(doc, multiline_strings=True)


SETUP_CFG = """[metadata]
name = demo
version = 1.0
[options]
packages = find:
install_requires =
    requests
    tomli; python_version < "3.11"
[tool:pytest]
addopts = -ra
"""
print(ini2toml("setup.cfg", SETUP_CFG), end="")
print("---")

# a byte order mark, comments, an empty section, a dotted section name, non-ASCII text,
# quotes and backslashes in a continued value, an empty value, a colon, and a tab
EDGES = """\ufeff# comment
[empty]
[a.b]
k = v
; another comment
[s\u00e9ction]
name = Zo\u00eb \u20ac
multi =
    l1 "q"
    l2\\\\x
empty =
url: https://example.org/a=b
tab = a\tb
[tool:pytest]
addopts = -ra
"""
print(ini2toml("edges.ini", EDGES), end="")
