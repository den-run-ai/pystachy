# the imports pylev's users write: clikit 0.6 and cleo 1.0.0a (the command-line layers of
# Poetry 1.1 and 1.2) take `from pylev import levenshtein` to suggest the commands closest to a
# mistyped name; then the misspelled aliases, `import *` (pylev's __all__) and its submodules
from pylev import levenshtein
from pylev import classic_levenschtein, levenschtein
from pylev import *
import pylev.wf
from pylev.recursive import recursive_levenshtein as rl

COMMANDS = ["about", "add", "build", "cache clear", "check", "config", "debug info", "export",
            "init", "install", "lock", "new", "publish", "remove", "run", "search", "self update",
            "shell", "show", "update", "version"]


def suggest(name: str) -> list[str]:
    # the commands within a third of the name's length of it, or that contain it, closest first
    found: list[tuple[int, int, str]] = []
    for cmd in COMMANDS:
        d = levenshtein(name, cmd)
        at = cmd.find(name)
        if d <= len(name) / 3 or at != -1:
            found.append((d, at if at != -1 else len(cmd), cmd))
    return [c for _, _, c in sorted(found)]


for typo in ["instal", "updtae", "sell", "confg", "ad", "lokc", "xyz", "self", "pubish", ""]:
    print(repr(typo), suggest(typo))
print(levenschtein("kitten", "sitting"), classic_levenschtein("flaw", "lawn"), rl("ab", "ba"))
print(wfi_levenshtein("ab", "abc"), wf_levenshtein("a", ""), recursive_levenshtein("", "q"),
      damerau_levenshtein("ab", "ba"), classic_levenshtein("ab", "a"))
print(pylev.wf.PY2, pylev.wf.wfi_levenshtein("gumbo", "gambol"), pylev.levenshtein("a", "b"))
