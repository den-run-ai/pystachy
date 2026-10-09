# iniconfig's IniConfig and SectionWrapper: the API cases of its own test suite
# (testing/test_iniconfig.py of iniconfig 2.3.1), run as a program instead of under pytest
import os
import tempfile

from iniconfig import COMMENTCHARS
from iniconfig import IniConfig
from iniconfig import ParseError
from iniconfig import __all__ as ALL


def dedent(text: str) -> str:
    # textwrap.dedent for the indented examples below (spaces only)
    lines = text.split("\n")
    margin = -1
    for line in lines:
        if line.strip():
            n = len(line) - len(line.lstrip(" "))
            if margin < 0 or n < margin:
                margin = n
    return "\n".join([line[margin:] if line.strip() else "" for line in lines])


print("__all__:", ALL, repr(COMMENTCHARS))

# test_parse_empty
ini = IniConfig("sample", "")
print("empty:", not ini.sections)

# test_iniconfig_from_file (pytest's tmp_path made by hand)
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "test.txt")
with open(path, "w") as f:
    f.write("[metadata]\nname=1")
config = IniConfig(path=path)
print("from file:", list(config.sections))
config = IniConfig(path, "[diff]")
print("data wins:", list(config.sections))

# test_iniconfig_section_first, _section_duplicate_fails, _duplicate_key_fails
for data in ["name=1", "[section]\n[section]", "[section]\nname = Alice\nname = bob"]:
    try:
        IniConfig("x", data=data)
        print("no error")
    except ParseError as e:
        print(f"ParseError {e.msg!r}: {e}")

# test_iniconfig_lineof
config = IniConfig("x.ini", data=("[section]\nvalue = 1\n[section2]\n# comment\nvalue =2"))
print("lineof:", config.lineof("missing"), config.lineof("section"), config.lineof("section2"))
print("lineof:", config.lineof("section", "value"), config.lineof("section2", "value"))
print("lineof:", config["section"].lineof("value"), config["section2"].lineof("value"))

# test_iniconfig_get_convert and test_iniconfig_get_missing (str defaults: see PORT.md)
config = IniConfig("x", data="[section]\nint = 1\nfloat = 1.1")
print("get:", config.get("section", "int"), config.get("section", "missing", default="1"))
print("get missing:", config.get("section", "missing"), config.get("other", "int"))

# test_section_get
config = IniConfig("x", data="[section]\nvalue=1")
section = config["section"]
print("section get:", section.get("value"), section.get("value", "2"), section.get("missing", "2"))

# test_missing_section
try:
    config["other"]
except KeyError as e:
    print("KeyError", e)

# test_section_getitem, test_section_iter
print("getitem:", config["section"]["value"])
print("section iter:", list(config["section"]), list(config["section"].items()))

# test_config_iter, test_config_contains
config = IniConfig(
    "x.ini",
    data=dedent(
        """
      [section1]
      value=1
      [section2]
      value=2
"""
    ),
)
sections = list(config)
print("config iter:", len(sections), [(s.name, s["value"]) for s in sections])
print("contains:", "xyz" in config, "section1" in config, "section2" in config)

# test_iter_file_order
config = IniConfig(
    "x.ini",
    data="""
[section2] #cpython dict ordered before section
value = 1
value2 = 2 # dict ordered before value
[section]
a = 1
b = 2
""",
)
print("order:", [x.name for x in list(config)], list(config["section2"]), list(config["section"]))

# test_example_pypirc
config = IniConfig(
    "pypirc",
    data=dedent(
        """
    [distutils]
    index-servers =
        pypi
        other

    [pypi]
    repository: <repository-url>
    username: <username>
    password: <password>

    [other]
    repository: http://example.com/pypi
    username: <username>
    password: <password>
"""
    ),
)
distutils, pypi, other = list(config)
print("pypirc:", repr(distutils["index-servers"]), pypi["repository"], pypi["username"], pypi["password"])
print("pypirc:", list(other), other["repository"])

# test_parse_strips_inline_comments (and from continuations), and IniConfig() keeping them
text = dedent(
    """
    [section1]
    name1 = value1 # this is a comment
    name2 = value2 ; this is also a comment
    name3 = value3# no space before comment
    list = a, b, c # some items
    [section]
    names =
        Alice # first person
        Bob ; second person
        Charlie
    """
)
for config in [IniConfig.parse("test.ini", data=text), IniConfig.parse("test.ini", data=text, strip_inline_comments=False), IniConfig("test.ini", data=text)]:
    print("comments:", [config["section1"][n] for n in ["name1", "name2", "name3", "list"]], repr(config["section"]["names"]))

# test_unicode_whitespace_stripped, _in_section_names_with_opt_in, _in_key_names
config = IniConfig(
    "test.ini",
    data="[section]\n" + "name1 =  value1 \n" + "name2 =  value2 \n" + "name3 = 　value3　\n",
)
print("unicode:", [config["section"][n] for n in ["name1", "name2", "name3"]])
config = IniConfig.parse("test.ini", data="[section ]\n" + "key = value\n", strip_section_whitespace=True)
print("unicode section:", "section" in config, config["section"]["key"])
config = IniConfig("test.ini", data="[section]\n" + "key  = value\n")
print("unicode key:", "key" in config["section"], config["section"]["key"])

# test_utf8_bom_file, test_utf8_bom_in_data_string, test_parse_utf8_bom_file
path = os.path.join(tmp, "bom.ini")
with open(path, "w", encoding="utf-8") as f:
    f.write("﻿[section]\nkey = value\n")
print("bom:", IniConfig(path)["section"]["key"], IniConfig.parse(path)["section"]["key"])
print("bom data:", IniConfig("x.ini", data="﻿[section]\nkey = value\n")["section"]["key"])
os.remove(os.path.join(tmp, "test.txt"))
os.remove(path)
os.rmdir(tmp)
