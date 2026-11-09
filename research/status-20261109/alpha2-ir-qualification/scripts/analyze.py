#!/usr/bin/env python3
"""Scratch analysis for the alpha.2 IR qualification (run with python3 -I).

collect RUN_DIR CORPUS_LIST OUT.json
    Read every case directory the instrumented oracle (irsame-keep.sh) kept: case name, both
    exit statuses, sha256 of both IR files and both message files, and whether the oracle's
    report is empty. Fails unless the cases are exactly CORPUS_LIST, each exactly once, each with
    a report (a completed comparison).
summary RUN.json
    Counts and the differing cases (as the oracle judged them), with what differs.
cross A.json SIDE_A B.json SIDE_B
    Compare one compiler's outputs (old/new) of run A with one compiler's outputs of run B, case
    by case: exit status, raw message bytes and raw IR bytes (no normalization at all).
subst RUN_DIR RUN.json OLDHOME NEWHOME OUT.tsv LINES.txt
    For every case the oracle reported as differing: rewrite OLDHOME (followed by '/' or the end
    of the string) to NEWHOME in the OLD compiler's IR, only inside the compiler's string
    constants, updating each constant's byte length, array sizes and ASCII character count
    together (lower_module.lower_data's layout), and in its messages; then compare with the NEW
    compiler's raw IR and messages byte for byte. Lines holding OLDHOME anywhere else stay raw.
    LINES.txt lists every differing raw line (diff of old and new) per case.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

STR_RE = re.compile(
    r'^(@[A-Za-z0-9_.$-]+) = private unnamed_addr global \{i64, i64, i64, \[(\d+) x i8\]\} '
    r'\{i64 (\d+), i64 0, i64 (\d+), \[(\d+) x i8\] c"(.*)\\00"\}, align 8$')
ESC_RE = re.compile(r'\\[0-9A-F]{2}')


def sha(path):
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    with open(path, "rb") as f:
        return f.read()


def collect(run_dir, corpus_list, out):
    expected = [line for line in open(corpus_list).read().split("\n") if line]
    if len(set(expected)) != len(expected):
        raise SystemExit("corpus list has duplicates")
    rows = {}
    for d in sorted(os.listdir(run_dir), key=lambda x: int(x) if x.isdigit() else -1):
        p = os.path.join(run_dir, d)
        if not d.isdigit() or not os.path.isdir(p):
            raise SystemExit(f"unexpected entry in run directory: {d}")
        case = read(os.path.join(p, "case")).decode().rstrip("\n")
        if case in rows:
            raise SystemExit(f"case twice: {case}")
        if not os.path.isfile(os.path.join(p, "report")):
            raise SystemExit(f"no completed report: {case}")
        rows[case] = {
            "index": int(d),
            "old_status": int(read(os.path.join(p, "old.status"))),
            "new_status": int(read(os.path.join(p, "new.status"))),
            "old_ll": sha(os.path.join(p, "old.ll")),
            "new_ll": sha(os.path.join(p, "new.ll")),
            "old_msg": sha(os.path.join(p, "old.msg")),
            "new_msg": sha(os.path.join(p, "new.msg")),
            "report_bytes": os.path.getsize(os.path.join(p, "report")),
            "report_messages": b"  messages:\n" in read(os.path.join(p, "report")),
        }
    if sorted(rows) != sorted(expected):
        missing = sorted(set(expected) - set(rows))
        extra = sorted(set(rows) - set(expected))
        raise SystemExit(f"cases differ from the corpus list: missing {missing[:5]} extra {extra[:5]}")
    order = [c for c, _ in sorted(rows.items(), key=lambda kv: kv[1]["index"])]
    if order != expected:
        raise SystemExit("case order differs from the corpus list")
    with open(out, "w") as f:
        json.dump({"run_dir": os.path.realpath(run_dir), "cases": len(rows), "rows": rows}, f, sort_keys=True, indent=1)
        f.write("\n")
    print(f"collected {len(rows)} cases, all with completed reports, matching the corpus list in order")


def load(path):
    with open(path) as f:
        return json.load(f)


def summary(path):
    run = load(path)
    rows = run["rows"]
    differ = {c: r for c, r in rows.items() if r["report_bytes"] > 0}
    status = [c for c, r in differ.items() if r["old_status"] != r["new_status"]]
    msgs_raw = [c for c, r in rows.items() if r["old_msg"] != r["new_msg"]]
    msgs_norm = [c for c, r in differ.items() if r["report_messages"]]
    ir = [c for c, r in rows.items() if r["old_ll"] is not None and r["new_ll"] is not None and r["old_ll"] != r["new_ll"]]
    one = [c for c, r in rows.items() if (r["old_ll"] is None) != (r["new_ll"] is None)]
    nonzero = sum(1 for r in rows.values() if r["old_status"] != 0)
    print(f"cases {len(rows)}; oracle-differing {len(differ)}; exit-status differences {len(status)}; "
          f"raw message differences {len(msgs_raw)}; message differences after the oracle's normalization {len(msgs_norm)}; "
          f"IR differences {len(ir)}; IR from only one compiler {len(one)}; nonzero old exit statuses {nonzero}")
    for c in sorted(differ, key=lambda c: rows[c]["index"]):
        r = rows[c]
        what = []
        if r["old_status"] != r["new_status"]:
            what.append(f"status {r['old_status']}->{r['new_status']}")
        if r["report_messages"]:
            what.append("messages")
        if c in ir:
            what.append("IR")
        if c in one:
            what.append("IR-one-side")
        print(f"DIFF\t{c}\t{','.join(what)}")


def cross(a_path, side_a, b_path, side_b):
    a = load(a_path)["rows"]
    b = load(b_path)["rows"]
    if sorted(a) != sorted(b):
        raise SystemExit("runs hold different cases")
    same = 0
    bad = []
    for c in sorted(a, key=lambda c: a[c]["index"]):
        x, y = a[c], b[c]
        keys = [("status", f"{side_a}_status", f"{side_b}_status"), ("msg", f"{side_a}_msg", f"{side_b}_msg"),
                ("ll", f"{side_a}_ll", f"{side_b}_ll")]
        diffs = [k for k, ka, kb in keys if x[ka] != y[kb]]
        if diffs:
            bad.append((c, diffs))
        else:
            same += 1
    print(f"{side_a} of {a_path} vs {side_b} of {b_path}: {same} of {len(a)} cases byte-identical "
          f"(status, raw messages, raw IR); {len(bad)} differ")
    for c, diffs in bad:
        print(f"CROSSDIFF\t{c}\t{','.join(diffs)}")


def payload_bytes(p):
    return len(p) - 2 * len(ESC_RE.findall(p))


def subst_ir(text, old, new, stats):
    pat = re.compile(re.escape(old) + r"(?=/|$)")
    d = len(new) - len(old)
    out = []
    for line in text.split("\n"):
        if old not in line:
            out.append(line)
            continue
        m = STR_RE.match(line)
        if not m:
            stats["outside_constants"] += 1
            out.append(line)
            continue
        name, n1, length, chars1, n2, p = m.groups()
        n1, length, chars1, n2 = int(n1), int(length), int(chars1), int(n2)
        if not (n1 == n2 == length + 1 == payload_bytes(p) + 1 and chars1 in (0, n1)):
            stats["inconsistent_constants"] += 1
            out.append(line)
            continue
        q, k = pat.subn(new, p)
        if k == 0:
            stats["unmatched_in_constants"] += 1
            out.append(line)
            continue
        n = n1 + k * d
        c1 = chars1 + k * d if chars1 else 0
        if payload_bytes(q) + 1 != n:
            stats["inconsistent_constants"] += 1
            out.append(line)
            continue
        stats["rewritten_constants"] += 1
        stats["rewritten_paths"] += k
        out.append(f'{name} = private unnamed_addr global {{i64, i64, i64, [{n} x i8]}} '
                   f'{{i64 {n - 1}, i64 0, i64 {c1}, [{n} x i8] c"{q}\\00"}}, align 8')
    return "\n".join(out)


def subst(run_dir, run_json, old, new, out_tsv, lines_txt):
    run = load(run_json)
    rows = run["rows"]
    differ = sorted((c for c, r in rows.items() if r["report_bytes"] > 0), key=lambda c: rows[c]["index"])
    pat = re.compile(re.escape(old) + r"(?=/|$)")
    totals = {"identical_after": 0, "residual": 0}
    with open(out_tsv, "w") as tsv, open(lines_txt, "w") as lines:
        tsv.write("case\tstatus_equal\tmessages_raw_equal\tmessages_equal_after_subst\tmessages_equal_by_oracle\tir_equal_after_subst\t"
                  "rewritten_constants\trewritten_paths\tpath_lines_outside_constants\tdiff_lines_old\tdiff_lines_new\t"
                  "diff_lines_without_a_home_path\n")
        for c in differ:
            r = rows[c]
            p = os.path.join(run_dir, str(r["index"]))
            stats = {"outside_constants": 0, "inconsistent_constants": 0, "unmatched_in_constants": 0,
                     "rewritten_constants": 0, "rewritten_paths": 0}
            status_eq = r["old_status"] == r["new_status"]
            om, nm = read(os.path.join(p, "old.msg")), read(os.path.join(p, "new.msg"))
            msg_raw = om == nm
            msg_sub = pat.sub(new, om.decode("utf-8", "surrogateescape")).encode("utf-8", "surrogateescape") == nm
            ir_eq = None
            dl_old = dl_new = dl_other = 0
            ol, nl = os.path.join(p, "old.ll"), os.path.join(p, "new.ll")
            if os.path.isfile(ol) and os.path.isfile(nl):
                ot = read(ol).decode("utf-8", "surrogateescape")
                nt = read(nl).decode("utf-8", "surrogateescape")
                ir_eq = subst_ir(ot, old, new, stats) == nt
                diff = subprocess.run(["diff", ol, nl], capture_output=True).stdout.decode("utf-8", "surrogateescape")
                lines.write(f"=== {c}\n")
                for line in diff.split("\n"):
                    if line.startswith("< ") or line.startswith("> "):
                        lines.write(line + "\n")
                        if line.startswith("< "):
                            dl_old += 1
                        else:
                            dl_new += 1
                        if old not in line and new not in line:
                            dl_other += 1
            elif os.path.isfile(ol) or os.path.isfile(nl):
                ir_eq = False
            msg_oracle = not r["report_messages"]
            ok = status_eq and (msg_raw or msg_sub or msg_oracle) and ir_eq is not False
            totals["identical_after" if ok else "residual"] += 1
            tsv.write(f"{c}\t{status_eq}\t{msg_raw}\t{msg_sub}\t{msg_oracle}\t{ir_eq}\t{stats['rewritten_constants']}\t"
                      f"{stats['rewritten_paths']}\t{stats['outside_constants']}\t{dl_old}\t{dl_new}\t{dl_other}\n")
    print(f"{len(differ)} oracle-differing cases: {totals['identical_after']} byte-identical after rewriting "
          f"{old} -> {new} in string constants (with their lengths) and messages; {totals['residual']} residual")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "collect":
        collect(*sys.argv[2:5])
    elif cmd == "summary":
        summary(sys.argv[2])
    elif cmd == "cross":
        cross(*sys.argv[2:6])
    elif cmd == "subst":
        subst(*sys.argv[2:8])
    else:
        raise SystemExit(__doc__)
