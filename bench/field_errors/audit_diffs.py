"""Narrow post-comparison audit; never changes the strict corpus comparator."""
import collections
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('validation_directory', type=Path, help='report.json and retained corpus capture')
OUT = parser.parse_args().validation_directory.resolve()
report = json.loads((OUT / 'report.json').read_text())
rows = []


def strings(text):
    return dict(re.findall(r'^(@s\.\d+) = (.*)$', text, re.M))


def abstract_strings(text, pool):
    # Dynamic boxed-string constant IDs are derived directly from the string ID.
    return re.sub(r'@(s|dbs)\.(\d+)\b', lambda m: '@' + m[1] + '.' + hashlib.sha256(pool['@s.'+m[2]].encode()).hexdigest(), text)


def canonical_locals(text):
    # SSA temporaries and generated spill slots share counters. Rename defined
    # values by definition order, retaining every operand/definition relation;
    # do not rename named LLVM types or undefined symbols.
    values = re.findall(r'^  (%[^\s,]+) = ', text, re.M)
    assert len(values) == len(set(values))
    names = {name: '%v'+str(i) for i, name in enumerate(values)}
    text = re.sub(r'%[-\w.$]+', lambda m: names.get(m[0], m[0]), text)
    labels = re.findall(r'^(L\d+):', text, re.M)
    names = {name: 'BB'+str(i) for i, name in enumerate(labels)}
    text = re.sub(r'%L(\d+)\b', r'L\1', text)
    return re.sub(r'(?<![\w.$])L\d+\b', lambda m: names.get(m[0], m[0]), text)


def audit(old, new):
    pools = strings(old), strings(new)
    table = re.findall(r'^@pys\.field\.names = private constant \[(\d+) x ptr\] \[(.*)\], align 8$', new, re.M)
    assert len(table) == 1
    refs = table[0][1].split(', ')
    assert len(refs) == int(table[0][0]) and refs[0] == 'ptr null'
    entries = [None if ref == 'ptr null' else pools[1][ref.removeprefix('ptr ')] for ref in refs]
    before_values, after_values = set(pools[0].values()), set(pools[1].values())
    assert before_values <= after_values, 'pre-existing string value disappeared'
    assert after_values - before_values <= set(entries), 'new string value outside the name table'
    # Outside-function text is compared separately; only string symbol spelling,
    # string definition order, and the new field-name table are handled specially.
    functions = []
    outside = []
    for text, pool in zip((old, new), pools):
        fs = re.findall(r'^define .*?^}\n', text, re.M | re.S)
        rest = re.sub(r'^define .*?^}\n', '', text, flags=re.M | re.S)
        rest = re.sub(r'^@s\.\d+ = .*\n', '', rest, flags=re.M)
        rest = re.sub(r'^@pys\.field\.names = .*\n', '', rest, flags=re.M)
        outside.append(abstract_strings(rest, pool))
        functions.append(fs)
    assert outside[0] == outside[1], 'non-function declarations changed'
    assert len(functions[0]) == len(functions[1]), 'function count changed'
    lookups = checks = changed_functions = 0
    tails = collections.Counter()
    for fno, (a, b) in enumerate(zip(*functions)):
        ab = re.split(r'(?m)^(?=[A-Za-z][A-Za-z0-9_.]*:\n)', a)
        bb = re.split(r'(?m)^(?=[A-Za-z][A-Za-z0-9_.]*:\n)', b)
        assert len(ab) == len(bb), 'basic-block count changed'
        changed = False
        for i, block in enumerate(bb):
            if 'getelementptr ptr, ptr @pys.field.names' not in block:
                continue
            oldlines, newlines = ab[i].splitlines(), block.splitlines()
            # Every measured lookup is a missing-field block: class-tag address,
            # tag load, name lookup, exactly two string adds, then raise/exception.
            assert len(newlines) in (9, 10), newlines
            gep = re.fullmatch(r'  (%t\d+) = getelementptr ptr, ptr @pys\.field\.names, i64 (%t\d+)', newlines[3])
            assert gep, newlines
            load = re.fullmatch(r'  (%t\d+) = load ptr, ptr ' + re.escape(gep[1]), newlines[4])
            assert load
            assert all('@pys_str_add(' in newlines[j] for j in (5, 6))
            if '@pys_raise(' in newlines[7]:
                assert newlines[8] == '  unreachable'
                tails['raise'] += 1
            else:
                assert '@pys_exc_new(' in newlines[7] and newlines[8].lstrip().startswith('store ') and newlines[9].lstrip().startswith('br ')
                tails['handled_exception'] += 1
            tag_load = re.fullmatch(r'  (%t\d+) = load i64, ptr %t\d+(?:, !tbaa !\d+)?', oldlines[2])
            assert tag_load
            j, previous = 3, None
            while j + 1 < len(oldlines):
                check = re.fullmatch(r'  (%t\d+) = icmp eq i64 ' + re.escape(tag_load[1]) + r', (\d+)', oldlines[j])
                if not check:
                    break
                select = re.fullmatch(r'  (%t\d+) = select i1 ' + re.escape(check[1]) + r', ptr (@s\.\d+), ptr (@s\.\d+|%t\d+)', oldlines[j + 1])
                assert select
                if previous is None:
                    assert select[3] in pools[0] and pools[0][select[3]] in entries, 'fallback name missing from table'
                else:
                    assert select[3] == previous, 'select chain changed'
                assert entries[int(check[2])] == pools[0][select[2]], 'tag/name mapping changed'
                previous = select[1]
                j += 2
                checks += 1
            assert previous is not None, 'no baseline subclass select chain'
            assert oldlines[j].endswith('ptr ' + previous + ')') and '@pys_str_add(' in oldlines[j]
            oldlines[3:j] = ['  ' + previous + ' = FIELD_NAME i64 ' + tag_load[1]]
            newlines[3:5] = ['  ' + load[1] + ' = FIELD_NAME i64 ' + gep[2]]
            ab[i], bb[i] = '\n'.join(oldlines) + '\n', '\n'.join(newlines) + '\n'
            lookups += 1
            changed = True
        a = canonical_locals(abstract_strings(''.join(ab), pools[0]))
        b = canonical_locals(abstract_strings(''.join(bb), pools[1]))
        if a != b:
            (OUT / 'unexpected-audit.diff').write_text(''.join(difflib.unified_diff(a.splitlines(True), b.splitlines(True))))
            raise AssertionError('residual function difference ' + str(fno))
        changed_functions += changed
    return dict(table_entries=len(entries), additional_name_strings=len(after_values-before_values),
                functions=len(functions[0]), lookup_functions=changed_functions, name_lookups=lookups,
                replaced_tag_comparisons=checks, tails=dict(tails), remaining_ir_equal=True,
                names_by_tag=[re.search(r'c"(.*)"', entry)[1] if entry else None for entry in entries])


for row in report['corpus']['intentional_ir_differences']:
    directory = Path(row['directory'])
    try:
        result = audit((directory/'old.ll').read_text(), (directory/'new.ll').read_text())
    except BaseException:
        print('FAILED', row['case'], flush=True)
        raise
    rows.append(dict(case=row['case'], old_sha256=row['old_sha256'], new_sha256=row['new_sha256'], **result))

output = dict(complete=True, cases=len(rows), rows=rows,
              total_lookups=sum(row['name_lookups'] for row in rows),
              total_replaced_tag_comparisons=sum(row['replaced_tag_comparisons'] for row in rows),
              note='Post-comparison structural audit only. Strict corpus comparator still exits 1 for all 143 raw IR changes. Every compared tag/name mapping and all other IR match after explicit string-symbol/SSA/label renumbering; no executable correctness is inferred from normalization.')
(OUT/'diff-audit.json').write_text(json.dumps(output, indent=2, sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in output.items() if k != 'rows'}, indent=2))
