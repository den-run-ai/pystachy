import re, subprocess, sys
def table(rev, f):
    out = subprocess.run(['git','-C','/home/user/pystachy','show',f'{rev}:{f}'],capture_output=True,text=True).stdout
    rows = {}
    for line in out.splitlines():
        m = re.match(r'\| `([^`]+)` \|(.*)', line)
        if m:
            cells = [c.strip() for c in m.group(2).split('|')]
            rows[m.group(1)] = cells
    return rows
a, b, f = sys.argv[1], sys.argv[2], sys.argv[3]
ta, tb = table(a,f), table(b,f)
tot = [0,0,0,0]
for k in sorted(set(ta)|set(tb)):
    ra = ta.get(k); rb = tb.get(k)
    def ints(r):
        if r is None: return [0,0,0,0]
        # hosted: Statements Missed % Branches Missed % ...
        return [int(r[0]), int(r[1]), int(r[3]), int(r[4])]
    ia, ib = ints(ra), ints(rb)
    d = [ib[i]-ia[i] for i in range(4)]
    for i in range(4): tot[i]+=d[i]
    if any(d):
        print(f'{k:50s} stmts {ia[0]:5d}->{ib[0]:5d} ({d[0]:+5d}) missed {ia[1]:4d}->{ib[1]:4d} ({d[1]:+4d}) | br {ia[2]:5d}->{ib[2]:5d} ({d[2]:+5d}) missed {ia[3]:4d}->{ib[3]:4d} ({d[3]:+4d})')
print('TOTAL', tot)
