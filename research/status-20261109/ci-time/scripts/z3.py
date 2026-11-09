"""Per-run split of x86 jobs into EPYC 7763 (znver3) and other runners by bootstrap-restore time."""
import collections


def restore(r):
    v = [s for n, _, s in r['stages'] if n == 'bootstrap' and s < 5]
    return v[0] if v else None


def split_points(recs):
    """run -> threshold: the largest gap between sorted restore times, upper side >= 0.55 s."""
    by = collections.defaultdict(list)
    for r in recs:
        if 'aarch64' in r['job'] or 'ARM64' in r['job']:
            continue
        t = restore(r)
        if t is not None:
            by[r['run']].append(t)
    out = {}
    for run, v in by.items():
        v.sort()
        best = None
        for i in range(3, len(v) - 2):
            if v[i] < 0.55:
                continue
            gap = v[i] - v[i - 1]
            if best is None or gap > best[0]:
                best = (gap, (v[i] + v[i - 1]) / 2)
        out[run] = best[1] if best and best[0] >= 0.03 else 0.65
    return out
