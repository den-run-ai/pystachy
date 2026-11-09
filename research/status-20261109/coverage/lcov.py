import sys, re, collections
def parse(path):
    files = {}
    cur = None
    for line in open(path):
        line = line.rstrip('\n')
        if line.startswith('SF:'):
            cur = files.setdefault(line[3:], {'fn': {}, 'fnda': {}, 'da': {}, 'br': collections.defaultdict(list)})
        elif line.startswith('FN:'):
            n, name = line[3:].split(',', 1)
            cur['fn'][name] = int(n)
        elif line.startswith('FNDA:'):
            c, name = line[5:].split(',', 1)
            cur['fnda'][name] = int(c)
        elif line.startswith('DA:'):
            parts = line[3:].split(',')
            cur['da'][int(parts[0])] = int(parts[1])
        elif line.startswith('BRDA:'):
            ln, blk, br, taken = line[5:].split(',')
            cur['br'][int(ln)].append(0 if taken == '-' else int(taken))
    return files
def functions(f):
    # map each line to the function whose FN start is the greatest <= line
    starts = sorted((n, name) for name, n in f['fn'].items())
    return starts
def per_function(f):
    starts = functions(f)
    import bisect
    keys = [s[0] for s in starts]
    res = collections.defaultdict(lambda: [0,0,0,0, []])  # lines, missed lines, branches, missed branches, missed line numbers
    for ln, c in f['da'].items():
        i = bisect.bisect_right(keys, ln) - 1
        name = starts[i][1] if i >= 0 else '(top)'
        r = res[name]; r[0] += 1
        if c == 0: r[1] += 1; r[4].append(ln)
    for ln, takens in f['br'].items():
        i = bisect.bisect_right(keys, ln) - 1
        name = starts[i][1] if i >= 0 else '(top)'
        r = res[name]; r[2] += len(takens); r[3] += sum(1 for t in takens if t == 0)
    return res
if __name__ == '__main__':
    a = parse(sys.argv[1]); b = parse(sys.argv[2]); sf = sys.argv[3]
    pa = per_function(a[sf]); pb = per_function(b[sf])
    rows = []
    for name in set(pa) | set(pb):
        ra = pa.get(name, [0,0,0,0,[]]); rb = pb.get(name, [0,0,0,0,[]])
        dl = rb[1]-ra[1]; db = rb[3]-ra[3]
        if dl or db:
            rows.append((db+dl, name, ra, rb))
    rows.sort(reverse=True)
    tl = tb = 0
    for s, name, ra, rb in rows:
        tl += rb[1]-ra[1]; tb += rb[3]-ra[3]
        new = 'NEW ' if name not in pa else '    '
        print(f"{new}{name:50s} lines {ra[0]:4d}/{ra[1]:3d} -> {rb[0]:4d}/{rb[1]:3d} ({rb[1]-ra[1]:+d}) br {ra[2]:4d}/{ra[3]:3d} -> {rb[2]:4d}/{rb[3]:3d} ({rb[3]-ra[3]:+d})  start {b[sf]['fn'].get(name,'-')}")
    print('total delta missed lines', tl, 'missed branches', tb)
