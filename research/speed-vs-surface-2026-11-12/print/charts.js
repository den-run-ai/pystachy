// Print charts for the A4 report: fixed sizes in CSS px (96 per inch), drawn once, no interaction.
(() => {
  const D = window.__DATA;
  const W = 656;
  const FONT = '"Inter TT", "Liberation Sans", Arial, sans-serif';
  const C = {
    fg: '#1d1c1a', muted: '#5f5e59', grid: '#ecebe6', axis: '#c3c2b7', ref: '#898781', line: '#e2e0da',
    s1: '#2a78d6', s2: '#eb6834', s3: '#1baf7a', s7: '#6250d6', crit: '#d03b3b', other: '#b9b8b1',
  };
  const parse = (s) => new Date(s);
  const day = d3.utcFormat('%b %-d');
  const rows = D.samples.slice().sort((a, b) => parse(a.date) - parse(b.date));
  const main = rows[rows.length - 1];

  function svg(id, h) {
    return d3.select('#' + id).append('svg').attr('width', W).attr('height', h).attr('viewBox', `0 0 ${W} ${h}`)
      .attr('font-family', FONT).attr('font-size', 11).attr('fill', C.fg);
  }
  function yAxis(g, y, x0, x1, ticks, fmt) {
    const t = g.append('g');
    for (const v of ticks) {
      t.append('line').attr('x1', x0).attr('x2', x1).attr('y1', y(v)).attr('y2', y(v))
        .attr('stroke', v === ticks[0] ? C.axis : C.grid).attr('stroke-width', v === ticks[0] ? 1 : 0.8);
      t.append('text').attr('x', x0 - 6).attr('y', y(v) + 4).attr('text-anchor', 'end').attr('fill', C.muted).text(fmt(v));
    }
  }
  function xDates(g, x, y0, dates) {
    for (const d of dates) {
      g.append('line').attr('x1', x(d)).attr('x2', x(d)).attr('y1', y0).attr('y2', y0 + 4).attr('stroke', C.axis);
      g.append('text').attr('x', x(d)).attr('y', y0 + 16).attr('text-anchor', 'middle').attr('fill', C.muted).text(day(d));
    }
  }
  function series(g, pts, x, y, color, opts = {}) {
    const line = d3.line().x((p) => x(p.x)).y((p) => y(p.y)).curve(opts.curve || d3.curveLinear);
    g.append('path').attr('d', line(pts)).attr('fill', 'none').attr('stroke', color)
      .attr('stroke-width', opts.width || 2).attr('stroke-opacity', opts.opacity ?? 1).attr('stroke-linejoin', 'round');
    const hollow = (p) => opts.hollow !== false && p.r && p.r.derived;
    g.append('g').selectAll('circle').data(pts).join('circle').attr('cx', (p) => x(p.x)).attr('cy', (p) => y(p.y))
      .attr('r', opts.r || 3.5).attr('fill', (p) => (hollow(p) ? '#fff' : color))
      .attr('stroke', (p) => (hollow(p) ? color : '#fff')).attr('stroke-width', (p) => (hollow(p) ? 1.8 : 1.5));
  }
  function label(g, x, y, text, opts = {}) {
    return g.append('text').attr('x', x).attr('y', y).attr('text-anchor', opts.anchor || 'start')
      .attr('fill', opts.color || C.fg).attr('font-weight', opts.weight || 400).attr('font-size', opts.size || 11).text(text);
  }
  const DOM = [new Date('2026-10-06T00:00:00Z'), new Date('2026-11-13T12:00:00Z')];
  const DATE_TICKS = ['2026-10-08', '2026-10-15', '2026-10-22', '2026-10-29', '2026-11-05', '2026-11-12'].map((s) => new Date(s + 'T00:00:00Z'));

  // Speed index against methods passing, one point per sampled commit.
  (() => {
    const h = 430, m = { l: 44, r: 170, t: 22, b: 40 };
    const s = svg('fig-trajectory', h);
    const x = d3.scaleLinear().domain([0, 520]).range([m.l, W - m.r]);
    const y = d3.scaleLinear().domain([0, 20]).range([h - m.b, m.t]);
    yAxis(s, y, m.l, W - m.r, [0, 5, 10, 15, 20], (v) => v + '×');
    for (const v of [0, 100, 200, 300, 400, 500]) {
      s.append('line').attr('x1', x(v)).attr('x2', x(v)).attr('y1', h - m.b).attr('y2', h - m.b + 4).attr('stroke', C.axis);
      label(s, x(v), h - m.b + 16, v, { anchor: 'middle', color: C.muted });
    }
    label(s, (m.l + W - m.r) / 2, h - 6, 'CPython test methods passing (of 5,905)', { anchor: 'middle', color: C.muted });
    label(s, m.l - 40, 12, 'AOT speed index (× CPython 3.13)', { color: C.muted });
    const micro = rows.filter((r) => r.micro != null).map((r) => ({ x: r.methods, y: r.micro, r }));
    const core = rows.filter((r) => r.core != null).map((r) => ({ x: r.methods, y: r.core, r }));
    series(s, micro, x, y, C.s1, { width: 1.5, opacity: 0.55 });
    series(s, core, x, y, C.s2, { width: 1.5, opacity: 0.55 });
    const lm = micro[micro.length - 1], lc = core[core.length - 1];
    label(s, x(lm.x) + 10, y(lm.y) + 4, `Six microbenchmarks: ${lm.y.toFixed(1)}×`, { color: C.fg, weight: 600 });
    label(s, x(lc.x) + 10, y(lc.y) + 4, `16 pyperformance ports: ${lc.y.toFixed(1)}×`, { color: C.fg, weight: 600 });
    const at = (pts, lab) => pts.find((p) => p.r.label.startsWith(lab));
    const ann = [
      [at(micro, '1007'), 'Oct 8: 15 methods', 6, -10, 'start'],
      [at(core, '1015'), 'Oct 15: first core point', 8, 16, 'start'],
      [at(core, '1019'), 'Oct 19: lib/re work', -8, -10, 'end'],
      [lc, 'main', 0, 18, 'middle'],
    ];
    for (const [p, t, dx, dy, anchor] of ann) if (p) label(s, x(p.x) + dx, y(p.y) + dy, t, { anchor, color: C.muted, size: 10.5 });
  })();

  // Methods passing over time.
  (() => {
    const h = 226, m = { l: 44, r: 150, t: 22, b: 30 };
    const s = svg('fig-surface', h);
    const x = d3.scaleUtc().domain(DOM).range([m.l, W - m.r]);
    const y = d3.scaleLinear().domain([0, 500]).range([h - m.b, m.t]);
    yAxis(s, y, m.l, W - m.r, [0, 100, 200, 300, 400, 500], (v) => v);
    xDates(s, x, h - m.b, DATE_TICKS);
    label(s, m.l - 40, 12, 'Methods passing', { color: C.muted });
    const all = rows.map((r) => ({ x: parse(r.date), y: r.methods, r }));
    const lang = rows.map((r) => ({ x: parse(r.date), y: r.language, r }));
    series(s, all, x, y, C.s1, { r: 3, hollow: false });
    series(s, lang, x, y, C.s2, { r: 3, hollow: false });
    label(s, x(all[all.length - 1].x) + 10, y(all[all.length - 1].y) + 4, `All methods: ${main.methods}`, { weight: 600 });
    label(s, x(lang[lang.length - 1].x) + 10, y(lang[lang.length - 1].y) + 4, `Language and builtins: ${main.language}`, { weight: 600 });
    const a2 = all.find((p) => p.r.release === 'v0.1.0-alpha.2'), a5 = all.find((p) => p.r.release === 'v0.4.0-alpha.5');
    label(s, x(a2.x), y(a2.y) - 10, `alpha.2: ${a2.y}`, { anchor: 'middle', color: C.muted, size: 10.5 });
    label(s, x(a5.x) - 4, y(a5.y) - 10, `alpha.5: ${a5.y}`, { anchor: 'end', color: C.muted, size: 10.5 });
  })();

  // Speed index over time.
  (() => {
    const h = 230, m = { l: 44, r: 150, t: 22, b: 30 };
    const s = svg('fig-speed', h);
    const x = d3.scaleUtc().domain(DOM).range([m.l, W - m.r]);
    const y = d3.scaleLinear().domain([0, 20]).range([h - m.b, m.t]);
    yAxis(s, y, m.l, W - m.r, [0, 5, 10, 15, 20], (v) => v + '×');
    xDates(s, x, h - m.b, DATE_TICKS);
    label(s, m.l - 40, 12, 'AOT speed index (× CPython 3.13)', { color: C.muted });
    const micro = rows.filter((r) => r.micro != null).map((r) => ({ x: parse(r.date), y: r.micro, r }));
    const core = rows.filter((r) => r.core != null).map((r) => ({ x: parse(r.date), y: r.core, r }));
    series(s, micro, x, y, C.s1, { r: 3 });
    series(s, core, x, y, C.s2, { r: 3 });
    const lm = micro[micro.length - 1], lc = core[core.length - 1];
    label(s, x(lm.x) + 10, y(lm.y) + 4, `Microbenchmarks: ${lm.y.toFixed(1)}×`, { weight: 600 });
    label(s, x(lc.x) + 10, y(lc.y) + 4, `Core ports: ${lc.y.toFixed(1)}×`, { weight: 600 });
    const o19 = core.find((p) => p.r.label.startsWith('1019'));
    label(s, x(o19.x) - 6, y(o19.y) - 10, 'Oct 19: lib/re work', { anchor: 'end', color: C.muted, size: 10.5 });
  })();

  // Speed by benchmark and commit.
  (() => {
    const sp = new Map(D.speedups.map((r) => [r.benchmark + '|' + r.label, r.speedup]));
    const lastLabel = rows.filter((r) => !r.derived).slice(-1)[0].label;
    const last = new Map(D.speedups.filter((r) => r.label === lastLabel).map((r) => [r.benchmark, r.speedup]));
    const benches = Array.from(new Set(D.speedups.map((r) => r.benchmark)));
    benches.sort((a, b) => (b.startsWith('micro_') - a.startsWith('micro_')) || ((last.get(b) || 0) - (last.get(a) || 0)));
    const name = (b) => (b.startsWith('micro_') ? b.slice(6) + ' (micro)' : b);
    const rowH = 10.6, top = 4, left = 112, bottom = 22;
    const h = Math.ceil(top + benches.length * rowH + bottom);
    const s = svg('fig-heatmap', h);
    const cols = rows.filter((r) => !r.derived);
    const x = d3.scaleBand().domain(cols.map((r) => r.label)).range([left, W - 2]).paddingInner(0.1);
    const y = d3.scaleBand().domain(benches).range([top, top + benches.length * rowH]).paddingInner(0.14);
    const op = (v) => (v >= 1 ? 0.1 + 0.9 * Math.min(1, Math.log2(v) / 6) : 0.1 + 0.9 * Math.min(1, -Math.log2(v) / 2));
    for (const b of benches) {
      label(s, left - 6, y(b) + y.bandwidth() / 2 + 3.5, name(b), { anchor: 'end', size: 9.5, color: C.fg });
      for (const r of cols) {
        const v = sp.get(b + '|' + r.label);
        const rect = s.append('rect').attr('x', x(r.label)).attr('y', y(b)).attr('width', x.bandwidth()).attr('height', y.bandwidth()).attr('rx', 1.5);
        if (v == null) rect.attr('fill', '#fff').attr('stroke', C.line).attr('stroke-width', 0.7);
        else rect.attr('fill', v >= 1 ? C.s1 : C.crit).attr('fill-opacity', op(v));
      }
    }
    const sepY = y(benches.find((b) => !b.startsWith('micro_'))) - 1.5;
    s.append('line').attr('x1', 4).attr('x2', W - 2).attr('y1', sepY).attr('y2', sepY).attr('stroke', C.axis).attr('stroke-dasharray', '2 2');
    for (const k of ['1007', '1015', '1020', '1027', '1102', '1107', '1111-1528']) {
      const r = cols.find((q) => q.label.startsWith(k));
      const lastCol = r === cols[cols.length - 1];
      label(s, lastCol ? W - 2 : x(r.label) + x.bandwidth() / 2, h - 8, day(parse(r.date)),
        { anchor: lastCol ? 'end' : 'middle', size: 9.5, color: C.muted });
    }
  })();

  // Compile cost: AOT builds of fixed programs, and the compiler's bootstrap.
  (() => {
    const h = 236, pw = (W - 28) / 2, m = { l: 40, r: 70, t: 24, b: 30 };
    const s = svg('fig-cost', h);
    const panel = (ox, title, list, ymax, fmt, ticks) => {
      const g = s.append('g').attr('transform', `translate(${ox},0)`);
      const x = d3.scaleUtc().domain(DOM).range([m.l, pw - m.r]);
      const y = d3.scaleLinear().domain([0, ymax]).range([h - m.b, m.t]);
      yAxis(g, y, m.l, pw - m.r, ticks, fmt);
      xDates(g, x, h - m.b, DATE_TICKS.filter((d, i) => i % 2 === 0));
      label(g, m.l - 36, 12, title, { color: C.muted });
      for (const [key, color, name] of list) {
        const pts = rows.filter((r) => r[key] != null).map((r) => ({ x: parse(r.date), y: r[key], r }));
        series(g, pts, x, y, color, { r: 2.6, width: 1.8 });
        const p = pts[pts.length - 1];
        label(g, x(p.x) + 7, y(p.y) + 4, name, { size: 10.5, weight: 600 });
      }
      return { x, y, g };
    };
    const a = panel(0, 'AOT build time (s)', [['richards_build', C.s2, 'richards'], ['raytrace_build', C.s3, 'raytrace'], ['nbody_build', C.s1, 'nbody']],
      1.6, (v) => v.toFixed(1), [0, 0.4, 0.8, 1.2, 1.6]);
    // Separate the end labels of the three build series when they collide.
    const ends = a.g.selectAll('text').filter(function () { return ['richards', 'raytrace', 'nbody'].includes(this.textContent); }).nodes();
    ends.sort((p, q) => +p.getAttribute('y') - +q.getAttribute('y'));
    for (let i = 1; i < ends.length; i++) {
      const prev = +ends[i - 1].getAttribute('y'), cur = +ends[i].getAttribute('y');
      if (cur - prev < 12) ends[i].setAttribute('y', prev + 12);
    }
    panel(pw + 28, 'Compiler bootstrap (s)', [['bootstrap', C.s7, 'bootstrap']], 300, (v) => v, [0, 100, 200, 300]);
  })();

  // First errors of the rejected methods on main, by what removing them needs.
  (() => {
    const short = {
      'other missing modules (configparser, decimal, _pyio, locale, ...)': 'Other missing stdlib modules',
      'enum.member / enum.verify / STRICT': 'enum.member, verify, STRICT (test_enum)',
      'field / class-attribute types not inferred': 'Field and class-attribute types',
      'local classes (class inside a function)': 'Classes defined inside functions',
      'pickle / copyreg / marshal': 'pickle, copyreg, marshal',
      'builtin base classes (set/frozenset/bytes...)': 'Builtin base classes (set, bytes, …)',
      'class-body statements (nested class, augassign...)': 'Statements in class bodies',
      'gc module (collect, is_tracked, thresholds)': 'gc module',
      'empty containers not inferred': 'Empty containers not inferred',
      'inheritance from generic class templates': 'Generic class templates as bases',
      'match patterns (mapping, starred, class, non-tuple subjects, complex)': 'match patterns',
      'modules or classes as values': 'Modules or classes as values',
      'eval / exec / compile, ast, dis': 'eval, exec, compile, ast, dis',
      'inspect module (mostly cleandoc)': 'inspect module',
      'str.format of a computed format string': 'str.format of a computed format',
      'exception attributes (__context__, __traceback__, args)': 'Exception attributes',
      'multiple inheritance': 'Multiple inheritance',
    };
    const color = { library: C.s1, compile: C.s2, reflect: C.s3, other: C.other };
    const list = D.groups.map((g) => ({ ...g, label: short[g.name] || g.name }));
    const assigned = list.reduce((a, g) => a + g.methods, 0);
    list.push({ need: 'other', methods: D.rejected - assigned, label: 'Other first errors' });
    list.sort((a, b) => (a.need === 'other') - (b.need === 'other') || b.methods - a.methods);
    const rowH = 17, top = 4, left = 236;
    const h = top + list.length * rowH + 6;
    const s = svg('fig-groups', h);
    const x = d3.scaleLinear().domain([0, 1200]).range([left, W - 60]);
    list.forEach((g, i) => {
      const yy = top + i * rowH;
      label(s, left - 8, yy + 12, g.label, { anchor: 'end', size: 10.5 });
      const w = Math.max(1, x(Math.min(g.methods, 1200)) - left);
      s.append('rect').attr('x', left).attr('y', yy + 2).attr('width', w).attr('height', rowH - 6).attr('rx', 2).attr('fill', color[g.need]);
      const t = g.methods > 1200 ? `${g.methods.toLocaleString('en-US')} (bar cut at 1,200)` : g.methods.toLocaleString('en-US');
      label(s, left + w + 6, yy + 12, t, { size: 10.5, color: C.fg });
    });
  })();
  document.body.dataset.charts = 'done';
})();
