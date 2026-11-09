import json, sys
a = json.load(open(sys.argv[1]))['files']; b = json.load(open(sys.argv[2]))['files']
mods = sys.argv[3:]
for m in mods:
    fa = a.get(m, {'functions': {}})['functions']; fb = b.get(m, {'functions': {}})['functions']
    rows = []
    for name in set(fa) | set(fb):
        sa = fa.get(name, {}).get('summary', {}); sb = fb.get(name, {}).get('summary', {})
        ml = sb.get('missing_lines', 0) - sa.get('missing_lines', 0)
        mb = sb.get('missing_branches', 0) - sa.get('missing_branches', 0)
        if ml > 0 or mb > 0:
            rows.append((ml + mb, name, sa, sb, fb.get(name, {}).get('missing_lines', [])))
    rows.sort(reverse=True)
    print('==', m)
    for s, name, sa, sb, missing in rows[:40]:
        new = 'NEW ' if not sa else '    '
        print(f"{new}{name:45s} stmts {sa.get('num_statements',0)}/{sa.get('missing_lines',0)} -> {sb.get('num_statements',0)}/{sb.get('missing_lines',0)}  br {sa.get('num_branches',0)}/{sa.get('missing_branches',0)} -> {sb.get('num_branches',0)}/{sb.get('missing_branches',0)}  missing {missing[:25]}")
