"""Inventory static call sites in emitted LLVM text; never infer execution cost.

Accepts canonical .ll from Pystachy/LLVM (single-line function headers and
call instructions). Unknown call targets remain visible as <unresolved>.
This is a diagnostic inventory, not an LLVM parser, verifier or profiler.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


NAME = r'(?:"(?:[^"\\]|\\.)*"|[-a-zA-Z$._0-9]+)'
HEADER = re.compile(r'^(define|declare)\b.*?@(' + NAME + r')\(')
CALL = re.compile(r'^\s*(?:%' + NAME + r'\s*=\s*)?(?:(?:tail|musttail|notail)\s+)?(call|invoke|callbr)\b(.*)')
TARGET = re.compile(r'([@%])(' + NAME + r')\s*\(')
GROUP = re.compile(r'^attributes #(\d+) = (.*)$')
STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
PARENS = re.compile(STRING.pattern + r'|[()]')
CONSTANT_CALLEE = re.compile(r'(?:asm|null|undef|poison|inttoptr|bitcast|addrspacecast|'
                             r'getelementptr|blockaddress|dso_local_equivalent|no_cfi)\b')
LIMITS = [
    'Counts are static call sites, not execution counts, allocation counts or timings.',
    'Inlining can replace a helper call with work in the caller; fewer calls do not prove less work.',
    'Function filtering does not compute reachability; definitions do not prove they execute.',
    'Attributes describe IR contracts, not proof that adding them to a GC allocator is safe.',
    'Single-line canonical LLVM headers/calls only; unresolved targets are counted explicitly.',
]


def strip_comment(line):
    # A semicolon inside a quoted identifier or string is not a comment.
    return re.split(r';(?=(?:[^"\\]|\\.|"(?:[^"\\]|\\.)*")*$)', line, maxsplit=1)[0]


def name_text(name):
    # Retain LLVM escapes verbatim rather than accidentally decoding symbol bytes.
    return name[1:-1] if name.startswith('"') else name


def call_target(body):
    # Keep quoted identifiers, but do not count call-like assembly text.
    masked = STRING.sub(lambda m: m[0] if m.start() > 0 and body[m.start() - 1] in '@%' else '""', body)
    target = TARGET.search(masked)
    if target is None or target[1] == '@':
        return target
    # In `call %Result (i32, ...) @callee(...)`, %Result begins an explicit
    # function type. Skip its balanced signature when another callee follows;
    # parentheses inside quoted type names must not affect the nesting.
    depth = 0
    for token in PARENS.finditer(masked, target.end() - 1):
        if token[0] == '(':
            depth += 1
        elif token[0] == ')':
            depth -= 1
            if depth == 0:
                following = masked[token.end():].lstrip()
                callee = TARGET.match(following)
                if callee is not None or CONSTANT_CALLEE.match(following):
                    return callee
                break
    return target


def inventory(data, function_pattern='.*'):
    text = data.decode('utf-8')
    select = re.compile(function_pattern)
    symbols = {}
    functions = {}
    groups = {}
    current = None
    for number, original in enumerate(text.splitlines(), 1):
        line = strip_comment(original).strip()
        group = GROUP.match(line)
        if group:
            groups[group[1]] = group[2]
        header = HEADER.match(line)
        if header:
            if current is not None:
                raise ValueError(f'nested function header at line {number}')
            kind, name = header[1], name_text(header[2])
            symbols[name] = {'kind': kind, 'line': number, 'header': line}
            if kind == 'define':
                if not line.endswith('{'):
                    raise ValueError(f'expected a single-line function header at line {number}')
                current = name
                functions[name] = {'calls': Counter(), 'call_kinds': Counter(), 'unresolved_lines': []}
            continue
        if line == '}':
            current = None
            continue
        call = CALL.match(line) if current is not None else None
        if call:
            target = call_target(call[2])
            name = ('@' + name_text(target[2]) if target[1] == '@' else '<indirect>') if target else '<unresolved>'
            functions[current]['calls'][name] += 1
            functions[current]['call_kinds'][call[1]] += 1
            if target is None:
                functions[current]['unresolved_lines'].append(number)
    if current is not None:
        raise ValueError('unterminated function')
    if not symbols:
        raise ValueError('no single-line LLVM function definitions/declarations found')
    for symbol in symbols.values():
        refs = re.findall(r'#(\d+)\b', STRING.sub('""', symbol['header']))
        if any(ref not in groups for ref in refs):
            raise ValueError(f"missing attribute group at line {symbol['line']}")
        symbol['attribute_groups'] = [groups[ref] for ref in refs]
    chosen = {name: functions[name] for name in sorted(functions) if select.search(name)}
    totals = Counter()
    kinds = Counter()
    for function in chosen.values():
        totals.update(function['calls'])
        kinds.update(function['call_kinds'])
        function['calls'] = dict(sorted(function['calls'].items()))
        function['call_kinds'] = dict(sorted(function['call_kinds'].items()))
    runtime = {name: symbols[name] for name in sorted(symbols) if name.startswith('pys_')}
    return {
        'sha256': hashlib.sha256(data).hexdigest(),
        'bytes': len(data),
        'lines': len(text.splitlines()),
        'function_pattern': function_pattern,
        'defined_functions': len(functions),
        'selected_functions': len(chosen),
        'calls': dict(sorted(totals.items())),
        'call_kinds': dict(sorted(kinds.items())),
        'functions': chosen,
        'runtime_symbols': runtime,
        'runtime_definitions': sum(symbol['kind'] == 'define' for symbol in runtime.values()),
        'runtime_declarations': sum(symbol['kind'] == 'declare' for symbol in runtime.values()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ir', action='append', required=True, metavar='LABEL=FILE',
                        help='repeat for raw, JIT, linked, or optimized IR; labels are caller supplied')
    parser.add_argument('--function', default='.*', help='regex selecting function names for call counts')
    parser.add_argument('-o', '--output', type=Path, help='JSON output; default is stdout')
    args = parser.parse_args(argv)
    report = {'schema_version': 1, 'limitations': LIMITS, 'modules': {}}
    try:
        for item in args.ir:
            label, separator, filename = item.partition('=')
            if not separator or not label or not filename:
                raise ValueError('--ir requires a nonempty LABEL=FILE')
            if label in report['modules']:
                raise ValueError(f'duplicate label: {label}')
            path = Path(filename)
            if args.output is not None and path.resolve() == args.output.resolve():
                raise ValueError('output must not overwrite an input')
            result = inventory(path.read_bytes(), args.function)
            result['path'] = str(path)
            report['modules'][label] = result
    except (OSError, UnicodeError, ValueError, re.error) as error:
        parser.error(str(error))
    output = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.output is None:
        print(output, end='')
    else:
        args.output.write_text(output, encoding='utf-8')


if __name__ == '__main__':
    main()
