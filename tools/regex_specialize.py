r"""Emit a bounded, guarded fixed-arity regex findall helper.

This offline experiment consumes Pystachy's existing regex parser and compiler.
It supports 2--5 captures in positive-width fixed patterns made of ASCII
literals, classes/categories and exact greedy repeats. It changes no compiler
or runtime machinery. Generated modules remain ordinary Python.
The API accepts plain re.compile() results with unmodified matching methods;
Pattern subclasses and method monkeypatching are outside this experiment.

Example:
    python3 tools/regex_specialize.py '(\d{4})-(\d{2})-(\d{2})' \
        --output bench/regex_date_generated.py
"""
import argparse
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MAX_WIDTH = 128
MAX_REPEAT = 32
MAX_SOURCE = 4096
MAX_WORK = 4096


def load_port():
    name = "_pystachy_regex_specializer_re"
    if name in sys.modules:
        return sys.modules[name]
    location = ROOT / "lib/re/__init__.py"
    spec = importlib.util.spec_from_file_location(name, location,
                                                submodule_search_locations=[str(location.parent)])
    port = importlib.util.module_from_spec(spec)
    sys.modules[name] = port
    spec.loader.exec_module(port)
    return port


def _members(port, item, flags: int) -> frozenset[int]:
    """The port's parser constants and category semantics are authoritative."""
    if item.op == port.LITERAL:
        if not 0 <= item.arg < 128:
            raise ValueError("non-ASCII literals are not residualized")
        return frozenset([item.arg])
    if item.op == port.NOT_LITERAL:
        if not 0 <= item.arg < 128:
            raise ValueError("non-ASCII literals are not residualized")
        return frozenset(set(range(128)) - {item.arg})
    if item.op == port.CATEGORY:
        categories = [port.CATEGORY_DIGIT, port.CATEGORY_NOT_DIGIT,
                      port.CATEGORY_SPACE, port.CATEGORY_NOT_SPACE,
                      port.CATEGORY_WORD, port.CATEGORY_NOT_WORD]
        if item.arg not in categories:
            raise ValueError("unsupported category")
        # Unicode \s includes ASCII separators U+001C--U+001F. Map parser
        # categories exactly as the existing compiler does before evaluating.
        category = port._category(item.arg, flags)
        return frozenset(c for c in range(128) if port._sre.category(category, c))
    if item.op != port.IN:
        raise ValueError(f"unsupported consuming opcode {item.op}")
    members: set[int] = set()
    negate = False
    for part in item.items:
        if part.op == port.NEGATE:
            negate = not negate
        elif part.op == port.RANGE:
            if not 0 <= part.arg <= part.arg2 < 128:
                raise ValueError("non-ASCII ranges are not residualized")
            members.update(range(part.arg, part.arg2 + 1))
        else:
            members.update(_members(port, part, flags))
    if negate:
        members = set(range(128)) - members
    return frozenset(members)


def plan(pattern: str, flags: int = 0):
    if len(pattern) > MAX_SOURCE:
        raise ValueError("pattern source exceeds 4096 characters")
    port = load_port()
    if flags & ~(port.ASCII | port.UNICODE):
        raise ValueError("only default, ASCII and UNICODE flags are supported")
    try:
        parsed = port.parse(pattern, flags)
    except RecursionError as exc:
        raise ValueError("pattern nesting exceeds the parser budget") from exc
    effective_flags = parsed.state.flags | flags
    if effective_flags & ~(port.ASCII | port.UNICODE):
        raise ValueError("scoped flags and mode flags are not residualized")
    groups = parsed.state.groups() - 1
    if not 2 <= groups <= 5:
        raise ValueError("the fixed tuple ABI requires 2--5 capturing groups")
    atoms: list[frozenset[int]] = []
    captures: dict[int, tuple[int, int]] = {}
    work = 0

    def walk(items, repeated=False):
        nonlocal work
        work += 1
        if work > MAX_WORK:
            raise ValueError("pattern expansion exceeds 4096 steps")
        for item in items:
            work += 1
            if work > MAX_WORK:
                raise ValueError("pattern expansion exceeds 4096 steps")
            if item.op == port.SUBPATTERN:
                if item.arg2 or item.arg3:
                    raise ValueError("scoped flags are not residualized")
                if repeated and item.arg > 0:
                    raise ValueError("capturing groups inside repeats are not residualized")
                start = len(atoms)
                walk(item.sub.data, repeated)
                if item.arg > 0:
                    if item.arg in captures:
                        raise ValueError("repeated capture")
                    captures[item.arg] = (start, len(atoms))
            elif item.op == port.MAX_REPEAT:
                if item.arg != item.arg2 or not 1 <= item.arg <= MAX_REPEAT:
                    raise ValueError("only positive exact greedy repeats up to 32 are supported")
                if item.sub.getwidth()[0] == 0:
                    raise ValueError("zero-width repeat bodies are not residualized")
                for _ in range(item.arg):
                    walk(item.sub.data, True)
            else:
                atoms.append(_members(port, item, effective_flags))
            if len(atoms) > MAX_WIDTH:
                raise ValueError("residual width exceeds 128 characters")

    walk(parsed.data)
    if not atoms:
        raise ValueError("empty matches are not residualized")
    if set(captures) != set(range(1, groups + 1)):
        raise ValueError("each capturing group must have one fixed span")
    return atoms, captures, effective_flags, port._code(parsed, flags)


def _predicate(members: frozenset[int], value: str) -> str:
    runs: list[tuple[int, int]] = []
    for c in sorted(members):
        if runs and c == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], c)
        else:
            runs.append((c, c))
    checks = [f"{value} == {lo}" if lo == hi else f"({lo} <= {value} and {value} <= {hi})"
              for lo, hi in runs]
    return "(" + " or ".join(checks) + ")" if checks else "False"


def generate(pattern: str, flags: int = 0) -> str:
    atoms, captures, effective_flags, code = plan(pattern, flags)
    count = len(captures)
    result_type = "list[tuple[" + ", ".join(["str"] * count) + "]]"
    signature = f"rx: re.Pattern, string: str, pos: int = 0, endpos: int = 9223372036854775807) -> {result_type}:"
    lines = [
        '# Generated by tools/regex_specialize.py; regenerate rather than edit.',
        '# Fixed tuple arity is an explicit API contract, not general dynamic tuple support.',
        '# Requires plain re.compile() results with unmodified matching methods.',
        'import re', '',
        f'SOURCE = {pattern!r}', f'EFFECTIVE_FLAGS = {effective_flags}', f'GROUPS = {count}',
        f'WIDTH = {len(atoms)}', f'EXPECTED_CODE: list[int] = {code!r}', '', '',
        'def _arity(rx: re.Pattern) -> None:',
        '    if rx.groups != GROUPS:',
        '        raise ValueError("regex capture count does not match the generated tuple ABI")', '', '',
        'def compatible(rx: re.Pattern) -> bool:',
        '    # Metadata/bytecode eligibility within the plain-Pattern API contract.',
        '    if rx.pattern != SOURCE or rx.flags != EFFECTIVE_FLAGS or rx.groups != GROUPS:',
        '        return False',
        '    if hasattr(rx, "_code"):',
        '        return rx._code == EXPECTED_CODE',
        '    return True', '', '',
        'def findall_generic(' + signature,
        '    _arity(rx)', f'    out: {result_type} = []',
        '    for match in rx.finditer(string, pos, endpos):',
    ]
    for group in range(1, count + 1):
        lines.extend([f'        g{group}: str | None = match.group({group})',
                      f'        if g{group} is None:', f'            g{group} = ""'])
    lines.extend(['        out.append((' + ', '.join(f'g{i}' for i in range(1, count + 1)) + '))',
                  '    return out', '', '', 'def findall_vm(' + signature,
                  '    _arity(rx)', '    if not hasattr(rx, "_code"):',
                  '        return findall_generic(rx, string, pos, endpos)',
                  '    st = rx._state(string, pos, endpos)', '    offs = st.offs',
                  f'    out: {result_type} = []', '    while st.start <= st.end:',
                  '        st.reset()', '        st.ptr = st.start',
                  '        if re._sre.sre_search(st, rx._code) == 0:', '            break'])
    for group in range(1, count + 1):
        mark = (group - 1) * 2
        lines.extend([f'        g{group} = ""',
                      f'        if st.lastmark >= {mark + 1} and st.mark[{mark}] >= 0 and st.mark[{mark + 1}] >= 0:',
                      f'            g{group} = string[re._to_index(offs, st.mark[{mark}]) : re._to_index(offs, st.mark[{mark + 1}])]'])
    lines.extend(['        out.append((' + ', '.join(f'g{i}' for i in range(1, count + 1)) + '))',
                  '        st.must_advance = st.ptr == st.start', '        st.start = st.ptr',
                  '    return out', '', '',
                  'def _scan(codes: list[int], string: str, start: int, end: int) -> ' + result_type + ':',
                  f'    out: {result_type} = []', '    i = start', '    while i + WIDTH <= end:'])
    predicates = [_predicate(members, f'codes[i + {offset}]') for offset, members in enumerate(atoms)]
    lines.append('        if ' + ' and '.join(predicates) + ':')
    slices = [f'string[i + {captures[group][0]} : i + {captures[group][1]}]' for group in range(1, count + 1)]
    lines.extend(['            out.append((' + ', '.join(slices) + '))', '            i += WIDTH',
                  '        else:', '            i += 1', '    return out', '', '',
                  'def findall_concrete(' + signature,
                  '    # The caller guarantees SOURCE/effective flags; Unicode retains the VM.',
                  '    _arity(rx)',
                  '    if pos < -9223372036854775808 or pos > 9223372036854775807 or endpos < -9223372036854775808 or endpos > 9223372036854775807:',
                  '        return findall_vm(rx, string, pos, endpos)',
                  '    if not string.isascii():',
                  '        return findall_vm(rx, string, pos, endpos)',
                  '    n = len(string)', '    start = min(max(pos, 0), n)',
                  '    end = min(max(endpos, 0), n)',
                  '    if hasattr(rx, "_code"):', '        codes = re._codes(string)',
                  '    else:', '        codes = [ord(c) for c in string]',
                  '    return _scan(codes, string, start, end)', '', '',
                  'def findall_specialized(' + signature,
                  '    _arity(rx)', '    if not compatible(rx):',
                  '        return findall_vm(rx, string, pos, endpos)',
                  '    return findall_concrete(rx, string, pos, endpos)', ''])
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pattern')
    parser.add_argument('--flags', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        source = generate(args.pattern, args.flags)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source)
    print(f'{args.output}: {len(source)} bytes')


if __name__ == '__main__':
    main()
