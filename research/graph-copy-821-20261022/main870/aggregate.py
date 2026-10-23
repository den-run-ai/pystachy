#!/usr/bin/env python3
"""Aggregate normalized paired benchmark JSONL without pooling environments.

One row is one independent base/head process pair. See REQUIRED and validate().
Run: python3 aggregate.py pairs.jsonl --output report
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import html
import io
import json
import math
from pathlib import Path
import random
import re
import statistics
from collections import defaultdict

REQUIRED = (
    'comparison_id', 'environment_id', 'workload_sha256', 'base_sha', 'head_sha',
    'workload', 'mode', 'phase', 'metric', 'unit', 'direction', 'batch', 'pair',
    'base', 'head', 'correct', 'evidence',
)
GROUP = ('comparison_id', 'environment_id', 'workload_sha256', 'base_sha',
         'head_sha', 'workload', 'mode', 'phase', 'metric', 'unit', 'direction')
SHA = re.compile(r'^[0-9a-f]{40}$')
HASH = re.compile(r'^[0-9a-f]{64}$')


def validate(row: dict, where: str = 'row') -> dict:
    if not isinstance(row, dict):
        raise ValueError(f'{where}: expected an object')
    if row.get('schema') != 1:
        raise ValueError(f'{where}: schema must be 1')
    missing = [key for key in REQUIRED if key not in row]
    if missing:
        raise ValueError(f'{where}: missing {", ".join(missing)}')
    for key in GROUP + ('evidence',):
        if not isinstance(row[key], str) or not row[key].strip():
            raise ValueError(f'{where}: {key} must be a nonempty string')
    for key in ('base_sha', 'head_sha'):
        if not SHA.fullmatch(row[key]):
            raise ValueError(f'{where}: {key} must be a full lowercase git SHA')
    if not HASH.fullmatch(row['workload_sha256']):
        raise ValueError(f'{where}: workload_sha256 must be a full SHA256')
    if row['direction'] not in ('lower', 'higher'):
        raise ValueError(f'{where}: direction must be lower or higher')
    if row['batch'] not in ('initial', 'confirmation'):
        raise ValueError(f'{where}: batch must be initial or confirmation')
    if type(row['pair']) is not int or row['pair'] < 0:
        raise ValueError(f'{where}: pair must be a nonnegative integer')
    if type(row['correct']) is not bool:
        raise ValueError(f'{where}: correct must be boolean')
    for key in ('base', 'head'):
        value = row[key]
        # Failed checks may carry null timings; they remain visible as failures.
        if value is None and not row['correct']:
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{where}: {key} must be positive and finite')
    for key in ('base_binary_sha256', 'head_binary_sha256'):
        if key in row and (not isinstance(row[key], str) or not HASH.fullmatch(row[key])):
            raise ValueError(f'{where}: {key} must be SHA256')
    return row


def read_rows(paths: list[Path]) -> list[dict]:
    rows = []
    seen = set()
    for path in paths:
        with path.open(encoding='utf-8') as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                where = f'{path}:{number}'
                try:
                    row = validate(json.loads(line), where)
                except json.JSONDecodeError as exc:
                    raise ValueError(f'{where}: invalid JSON: {exc.msg}') from exc
                key = tuple(row[k] for k in GROUP) + (row['batch'], row['pair'])
                if key in seen:
                    raise ValueError(f'{where}: duplicate paired observation')
                seen.add(key)
                rows.append(row)
    return rows


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def batch_summary(rows: list[dict], seed: str) -> dict:
    valid = [r for r in rows if r['correct']]
    summary = {'n': len(valid), 'failed': len(rows) - len(valid)}
    if not valid:
        return summary
    base = [r['base'] for r in valid]
    head = [r['head'] for r in valid]
    mb, mh = statistics.median(base), statistics.median(head)
    summary.update(base_median=mb, head_median=mh, ratio=mh / mb,
                   percent=100 * (mh / mb - 1),
                   base_min=min(base), base_max=max(base),
                   head_min=min(head), head_max=max(head))
    # Resample matched process pairs together. This is a descriptive uncertainty
    # interval, not a correction for host drift or unmeasured confounders.
    if len(valid) >= 5:
        rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16))
        ratios = []
        for _ in range(4000):
            indices = [rng.randrange(len(valid)) for _ in valid]
            ratios.append(statistics.median(head[i] for i in indices) /
                          statistics.median(base[i] for i in indices))
        summary['ratio_ci_low'] = percentile(ratios, .025)
        summary['ratio_ci_high'] = percentile(ratios, .975)
    return summary


def threshold(batch: dict, direction: str) -> bool:
    if 'ratio' not in batch:
        return False
    return batch['ratio'] >= 1.20 if direction == 'lower' else batch['ratio'] <= .80


def repeatable(batch: dict, direction: str) -> bool:
    if batch['n'] < 5 or not threshold(batch, direction):
        return False
    return (batch['ratio_ci_low'] > 1 if direction == 'lower'
            else batch['ratio_ci_high'] < 1)


def summarize(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    seen = set()
    for row in rows:
        validate(row)
        key = tuple(row[k] for k in GROUP)
        unique = key + (row['batch'], row['pair'])
        if unique in seen:
            raise ValueError('duplicate paired observation')
        seen.add(unique)
        groups[key].append(row)
    output = []
    for key, group in sorted(groups.items()):
        item = dict(zip(GROUP, key))
        identity = json.dumps(key)
        batches = {name: batch_summary([r for r in group if r['batch'] == name], identity + name)
                   for name in ('initial', 'confirmation')}
        item['batches'] = batches
        initial, confirmation = batches.values()
        failures = sum(b['failed'] for b in batches.values())
        if failures:
            status = 'correctness/setup failure; no speed conclusion'
        elif repeatable(initial, item['direction']) and repeatable(confirmation, item['direction']):
            status = 'repeated_signal'
        elif threshold(initial, item['direction']) or threshold(confirmation, item['direction']):
            status = 'candidate / not confirmed'
        else:
            status = 'no confirmed threshold crossing'
        same_binary = all(r.get('base_binary_sha256') and
                          r.get('base_binary_sha256') == r.get('head_binary_sha256')
                          for r in group)
        item['attribution'] = ('identical executable; source attribution unresolved'
                               if same_binary and item['mode'].lower() == 'aot'
                               and not any(x in item['phase'].lower() for x in ('compile', 'build', 'frontend', 'backend', 'ir_emit'))
                               else 'requires change review; timing alone is not causation')
        if same_binary and status == 'repeated_signal' and \
                item['attribution'].startswith('identical'):
            status = 'identical_binary_signal'
        item['status'] = status
        item['correctness_failures'] = failures
        item['evidence'] = sorted({r['evidence'] for r in group})
        item['notes'] = sorted({str(r['note']) for r in group if r.get('note')})
        item['prs'] = sorted({str(r['pr']) for r in group if r.get('pr')})
        output.append(item)
    return output


COLUMNS = list(GROUP) + ['status', 'attribution', 'correctness_failures', 'batch', 'n', 'failed',
                         'base_median', 'head_median', 'ratio', 'percent', 'base_min', 'base_max',
                         'head_min', 'head_max', 'ratio_ci_low', 'ratio_ci_high', 'evidence', 'notes', 'prs']


def flat_rows(summary: list[dict]):
    for item in summary:
        for name, batch in item['batches'].items():
            if not batch['n'] and not batch['failed']:
                continue
            row = {key: item[key] for key in GROUP}
            row.update({key: item[key] for key in ('status', 'attribution', 'correctness_failures')})
            row.update(batch, batch=name)
            for key in ('evidence', 'notes', 'prs'):
                row[key] = '; '.join(item[key])
            yield row


def format_number(value):
    return '—' if value is None else f'{value:.6g}'


def make_html(summary: list[dict]) -> str:
    repeated = [item for item in summary if item['status'] in ('repeated_signal', 'identical_binary_signal')]
    pairs = {(item['base_sha'], item['head_sha']) for item in summary}
    historical_only = bool(summary) and all(any('Imported raw per-process samples; no new execution.' in note for note in item['notes']) for item in summary)
    executive = f"<p><strong>Report scope:</strong> {len(summary)} metric/mode/phase/comparison groups across {len(pairs)} distinct base/head revision pairs. Counts include correlated views of the same process measurements and must not be read as counts of separate regressions.</p>"
    if repeated and all(item['prs'] and all(re.match(r'^864(?:\D|$)', pr) for pr in item['prs']) for item in repeated):
        executive += '<p><strong>Existing alert:</strong> These metric/mode/anchor views belong to the already reported PR #864 branch regression; they are not separate newly discovered regressions.</p>'
    if historical_only:
        executive += '<p><strong>Replay status:</strong> The new historical queue is pending; imported evidence is not a fresh replay.</p>'
    cells = []
    for item in summary:
        for batch, value in item['batches'].items():
            if not value['n'] and not value['failed']:
                continue
            lineage = '; '.join(item['prs']) or ('Main-to-main / control' if any('main-to-main' in note for note in item['notes']) else 'See raw provenance')
            row = [item['workload'], item['mode'] + ' / ' + item['phase'],
                   item['metric'] + ' (' + item['unit'] + ')',
                   item['base_sha'][:12] + ' → ' + item['head_sha'][:12], lineage, batch,
                   str(value['n']), format_number(value.get('base_median')),
                   format_number(value.get('head_median')),
                   format_number(value.get('percent')) + ('%' if 'percent' in value else ''),
                   (f"[{value['ratio_ci_low']:.3f}, {value['ratio_ci_high']:.3f}]"
                    if 'ratio_ci_low' in value else 'not estimated'),
                   item['status'], item['attribution'], item['environment_id'],
                   '; '.join(item['evidence'])]
            css = 'bad' if item['status'] == 'repeated_signal' else 'warn' if ('candidate' in item['status'] or 'failure' in item['status'] or 'signal' in item['status']) else ''
            rendered = ['<td>' + html.escape(x) + '</td>' for x in row]
            rendered[3] = '<td>' + ' → '.join('<a target="_blank" rel="noopener noreferrer" title="' + item[k] + '" href="https://github.com/den-run-ai/pystachy/commit/' + item[k] + '">' + item[k][:12] + '</a>' for k in ('base_sha', 'head_sha')) + '</td>'
            cells.append('<tr class="' + css + '">' + ''.join(rendered) + '</tr>')
    headings = ['Workload', 'Mode / phase', 'Metric', 'Base → head', 'PR / lineage', 'Batch', 'Pairs',
                'Base median', 'Head median', 'Change', 'Ratio 95% interval', 'Classification',
                'Attribution', 'Environment', 'Raw evidence']
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pystachy historical performance</title><style>body{font:15px system-ui;margin:28px;color:#172532;background:#fafbfc}h1{font-size:26px}p{max-width:1000px;line-height:1.5}input{padding:9px;width:min(600px,90%);margin:12px 0}.table{overflow:auto}table{border-collapse:collapse;background:white;font-size:13px}th,td{padding:10px;text-align:left;border-bottom:1px solid #dde2e6;vertical-align:top}th{position:sticky;top:0;background:#e9eff5;cursor:pointer;white-space:nowrap}.bad{background:#fff0ef}.warn{background:#fff9e9}td:nth-child(15){max-width:440px;overflow-wrap:anywhere}</style>
<h1>Pystachy historical performance</h1>
<p><strong>Evidence status:</strong> imported prior measurements are labeled in the PR / lineage and raw provenance fields. Importing or aggregating them is not new benchmark execution. Unmerged PR observations are separate from main history; pending revisions have no timing claim.</p>
<p>Each row is a separately measured batch. Positive change means a larger metric: slower for elapsed/CPU time or greater resource use; for throughput a negative change is worse. Change = 100 × (head median / base median − 1). Environments, workloads, revisions and execution phases are never pooled.</p>
<p>A repeated_signal requires at least five correct paired processes in both initial and confirmation batches; each batch must cross +20% for time/resources or −20% for throughput, and each paired bootstrap ratio interval must exclude 1 in the adverse direction. A repeated_signal is not automatically a source-attributed regression. The 95% intervals are descriptive percentile bootstrap estimates (4,000 paired resamples), not proof against host contention or causal attribution. A result below threshold is not a claim that the revision is regression-free. Identical AOT executables require further attribution controls.</p>
''' + executive + '''
<input id="filter" type="search" placeholder="Filter workload, SHA, phase, status or environment" aria-label="Filter results"><div class="table"><table><thead><tr>''' + ''.join('<th scope="col">' + html.escape(x) + '</th>' for x in headings) + '</tr></thead><tbody>' + ''.join(cells) + '''</tbody></table></div>
<script>const input=document.getElementById('filter');input.addEventListener('input',()=>{const q=input.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});document.querySelectorAll('th').forEach((h,i)=>h.addEventListener('click',()=>{const body=document.querySelector('tbody');const rows=[...body.rows];const sign=h.dataset.order==='asc'?-1:1;h.dataset.order=sign===1?'asc':'desc';rows.sort((a,b)=>sign*a.cells[i].textContent.localeCompare(b.cells[i].textContent,undefined,{numeric:true}));rows.forEach(r=>body.appendChild(r));}));</script></html>'''


def write_report(summary: list[dict], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / 'summary.json').write_text(json.dumps({'schema': 1, 'comparisons': summary}, indent=2) + '\n')
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, extrasaction='raise')
    writer.writeheader()
    writer.writerows(flat_rows(summary))
    (output / 'summary.csv').write_text(buffer.getvalue(), encoding='utf-8')
    (output / 'index.html').write_text(make_html(summary), encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, default=Path('report'))
    args = parser.parse_args()
    try:
        summary = summarize(read_rows(args.inputs))
        write_report(summary, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'error: {exc}\n')
    print(json.dumps({'comparisons': len(summary), 'output': str(args.output),
                      'repeated_signals': sum(r['status'] == 'repeated_signal' for r in summary)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
