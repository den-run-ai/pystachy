"""Finite union-tag facts, equalities and boolean implications for the IR proof.

Domains are sorted, distinct lists of type names. They are immutable once shared: states
copy their maps, never a domain's items. This keeps the domain independent of machine-int
width, including when the program has more union members than one word can represent.
"""
from __future__ import annotations

# (each key's value, and each name's tag as a join's representative, made once: the same keys
# recur in every state of a proof and the same names in every function)
KEY_VALUES: dict[str, str] = {}
CONSTANT_REPS: dict[str, str] = {}
VALUE_REPS: dict[str, str] = {}


def key_value(k: str) -> str:
    # the value that key k's facts are about: what follows its kind's ":"
    if k not in KEY_VALUES:
        KEY_VALUES[k] = k[k.find(":") + 1:]
    return KEY_VALUES[k]


def join_rep(domain: list[str], name: str) -> str:
    # a join's representative of a key whose domain is domain and whose own representative is
    # name: equal constants prove equality even when each edge used different variable names,
    # and the prefixes keep constant representatives distinct from arbitrary variable names
    if len(domain) == 1:
        if domain[0] not in CONSTANT_REPS:
            CONSTANT_REPS[domain[0]] = "c:" + domain[0]
        return CONSTANT_REPS[domain[0]]
    if name not in VALUE_REPS:
        VALUE_REPS[name] = "v:" + name
    return VALUE_REPS[name]


def union_tags(a: list[str], b: list[str]) -> list[str]:
    if a == b:
        return a
    out: list[str] = []
    i = 0
    j = 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            out.append(a[i])
            i += 1
        elif b[j] < a[i]:
            out.append(b[j])
            j += 1
        else:
            out.append(a[i])
            i += 1
            j += 1
    return out + a[i:] + b[j:]


def intersect_tags(a: list[str], b: list[str]) -> list[str]:
    if a == b:
        return a
    out: list[str] = []
    i = 0
    j = 0
    while i < len(a) and j < len(b):
        if a[i] < b[j]:
            i += 1
        elif b[j] < a[i]:
            j += 1
        else:
            out.append(a[i])
            i += 1
            j += 1
    return out


class UnionState:
    def __init__(self, base: dict[str, list[str]], full: list[str], source: UnionState | None = None) -> None:
        self.base = base
        self.full = full
        self.d: dict[str, list[str]] = {} if source is None else dict(source.d)
        self.eq: dict[str, str] = {} if source is None else dict(source.eq)
        # Object loads that still name the value in a private slot or global.
        # Equal tag domains do not establish identity between two objects.
        self.loaded: dict[str, str] = {} if source is None else dict(source.loaded)
        # Domains and implication maps are immutable once shared.
        self.bt: dict[str, dict[str, list[str]]] = {} if source is None else dict(source.bt)
        self.bf: dict[str, dict[str, list[str]]] = {} if source is None else dict(source.bf)
        self.truth: dict[str, int] = {} if source is None else dict(source.truth)
        self.live: bool = True if source is None else source.live

    def clone(self) -> UnionState:
        return UnionState(self.base, self.full, self)

    def dom(self, k: str) -> list[str]:
        return self.d.get(k, self.base.get(k, self.full))

    def forget(self, k: str) -> None:
        rep = self.eq.get(k, k)
        if k in self.eq:
            del self.eq[k]
        # (rebase what is left of k's group on its least member; the search for one allocates
        # nothing, as most keys forgotten are in no group)
        grouped = False
        for x in self.eq:
            if self.eq[x] == rep:
                grouped = True
                break
        if grouped:
            group = sorted([x for x in self.eq if self.eq[x] == rep])
            for x in group:
                self.eq[x] = group[0]
        if k in self.d:
            del self.d[k]
        for b in self.bt:
            if k in self.bt[b]:
                self.bt[b] = {x: self.bt[b][x] for x in self.bt[b] if x != k}
        for b in self.bf:
            if k in self.bf[b]:
                self.bf[b] = {x: self.bf[b][x] for x in self.bf[b] if x != k}

    def set(self, k: str, domain: list[str]) -> None:
        self.forget(k)
        self.d[k] = domain
        self.eq[k] = k

    def copy(self, k: str, v: str) -> None:
        if k == v:
            return
        domain = self.dom(v)
        yes: dict[str, list[str]] = {}
        no: dict[str, list[str]] = {}
        for b in self.bt:
            if v in self.bt[b]:
                yes[b] = self.bt[b][v]
        for b in self.bf:
            if v in self.bf[b]:
                no[b] = self.bf[b][v]
        self.forget(k)
        self.d[k] = domain
        if v not in self.eq:
            self.eq[v] = v
            self.d[v] = domain
        self.eq[k] = self.eq[v]
        for b in yes:
            facts = dict(self.bt[b])
            facts[k] = yes[b]
            self.bt[b] = facts
        for b in no:
            facts = dict(self.bf[b])
            facts[k] = no[b]
            self.bf[b] = facts

    def narrow(self, k: str, domain: list[str]) -> None:
        rep = self.eq.get(k, k)
        want = intersect_tags(self.dom(k), domain)
        if len(want) == 0:
            self.live = False
        for x in self.eq:
            if self.eq[x] == rep:
                self.d[x] = intersect_tags(self.dom(x), want)
        self.d[k] = want

    def cond(self, b: str, yes: bool) -> None:
        mask = self.truth.get(b, 2 if b == "true" else 1 if b == "false" else 3)
        if mask & (2 if yes else 1) == 0:
            self.live = False
            return
        self.truth[b] = 2 if yes else 1
        facts = (self.bt if yes else self.bf).get(b, {})
        groups: dict[str, list[str]] = {}
        for k in facts:
            rep = self.eq.get(k, k)
            want = intersect_tags(self.dom(k), facts[k])
            groups[rep] = intersect_tags(groups[rep], want) if rep in groups else want
        for k in self.eq:
            rep = self.eq[k]
            if rep in groups:
                self.d[k] = intersect_tags(self.dom(k), groups[rep])
                if len(self.d[k]) == 0:
                    self.live = False
        for k in facts:
            if k not in self.eq:
                self.d[k] = groups[k]
                if len(self.d[k]) == 0:
                    self.live = False

    def conditional(self, b: str, yes: bool) -> UnionState:
        other = self.clone()
        other.cond(b, yes)
        return other

    def boolean(self, b: str, yes: UnionState, no: UnionState) -> None:
        self.truth[b] = (2 if yes.live else 0) | (1 if no.live else 0)
        self.bt[b] = {k: yes.dom(k) for k in yes.d if yes.dom(k) != self.dom(k)} if yes.live else {}
        self.bf[b] = {k: no.dom(k) for k in no.d if no.dom(k) != self.dom(k)} if no.live else {}

    def test(self, b: str, k: str, yes: list[str], no: list[str]) -> None:
        # boolean b holds where key k's object has a class of domain yes and fails where it has
        # one of no: boolean() of the states that narrow(k, yes) and narrow(k, no) would leave,
        # without copying this one for them
        holds = intersect_tags(self.dom(k), yes)
        fails = intersect_tags(self.dom(k), no)
        live_yes = self.live and len(holds) > 0
        live_no = self.live and len(fails) > 0
        self.truth[b] = (2 if live_yes else 0) | (1 if live_no else 0)
        self.bt[b] = self.narrowed(k, holds) if live_yes else {}
        self.bf[b] = self.narrowed(k, fails) if live_no else {}

    def narrowed(self, k: str, want: list[str]) -> dict[str, list[str]]:
        # the domains that narrowing k to want, a part of its domain, changes: of k and of each
        # key equal to it (narrow)
        rep = self.eq.get(k, k)
        facts: dict[str, list[str]] = {}
        for x in self.eq:
            if self.eq[x] == rep and x != k:
                domain = intersect_tags(self.dom(x), want)
                if domain != self.dom(x):
                    facts[x] = domain
        if want != self.dom(k):
            facts[k] = want
        return facts

    def boolcopy(self, b: str, v: str) -> None:
        yes = self.conditional(v, True)
        no = self.conditional(v, False)
        # Keep incoming-edge facts too, so a join preserves a boolean phi's implication.
        self.truth[b] = (2 if yes.live else 0) | (1 if no.live else 0)
        self.bt[b] = dict(yes.d) if yes.live else {}
        self.bf[b] = dict(no.d) if no.live else {}

    def same(self, other: UnionState) -> bool:
        # States in one proof share the immutable base and full domain.
        return self.d == other.d and self.eq == other.eq and self.loaded == other.loaded and self.bt == other.bt and self.bf == other.bf and self.truth == other.truth and self.live == other.live

    def needed(self, k: str, values: dict[str, bool]) -> bool:
        v = key_value(k)
        return not v.startswith("%") or v in values

    def retain(self, values: dict[str, bool]) -> None:
        # (a map is made again only where it holds something no longer needed: most edges drop
        # little of it)
        drop = False
        for v in self.loaded:
            if v not in values:
                drop = True
                break
        if drop:
            self.loaded = {v: self.loaded[v] for v in self.loaded if v in values}
        drop = False
        for k in self.d:
            if not self.needed(k, values):
                drop = True
                break
        if drop:
            self.d = {k: self.d[k] for k in self.d if self.needed(k, values)}
        # Representatives can name dead values. Rebase each surviving equivalence
        # class instead of dropping its relation when that representative dies;
        # a class whose members all live and whose representative is its least
        # member is as the rebasing would leave it.
        rebase = False
        for k in self.eq:
            rep = self.eq[k]
            if not self.needed(k, values) or k < rep or rep not in self.eq or self.eq[rep] != rep:
                rebase = True
                break
        if rebase:
            representatives: dict[str, str] = {}
            equal: dict[str, str] = {}
            for k in sorted(self.eq):
                if self.needed(k, values):
                    old = self.eq[k]
                    if old not in representatives:
                        representatives[old] = k
                    equal[k] = representatives[old]
            self.eq = equal
        drop = False
        for k in self.truth:
            if k not in values:
                drop = True
                break
        if drop:
            self.truth = {k: self.truth[k] for k in self.truth if k in values}
        if self.stale(self.bt, values):
            self.bt = {b: {k: self.bt[b][k] for k in self.bt[b] if self.needed(k, values)} for b in self.bt if b in values}
        if self.stale(self.bf, values):
            self.bf = {b: {k: self.bf[b][k] for k in self.bf[b] if self.needed(k, values)} for b in self.bf if b in values}

    def stale(self, implications: dict[str, dict[str, list[str]]], values: dict[str, bool]) -> bool:
        # does retain drop something of implications: a boolean or a key no longer needed
        for b in implications:
            if b not in values:
                return True
            for k in implications[b]:
                if not self.needed(k, values):
                    return True
        return False


def union_join(a: UnionState, b: UnionState) -> UnionState:
    if not a.live:
        return b.clone()
    if not b.live:
        return a.clone()
    state = UnionState(a.base, a.full)
    state.loaded = {v: a.loaded[v] for v in a.loaded if b.loaded.get(v, "") == a.loaded[v]}
    keys = list(a.d)
    for k in b.d:
        if k not in a.d:
            keys.append(k)
    present = {k: True for k in keys}
    # A parameter-backed comparison can have no unconditional override at all.
    # Its domain still has to participate in a join of the saved condition.
    for implications in [a.bt, a.bf, b.bt, b.bf]:
        for condition in implications:
            for k in implications[condition]:
                if k not in present:
                    present[k] = True
                    keys.append(k)
    keys.sort()
    groups: dict[str, dict[str, str]] = {}
    for k in keys:
        left = a.dom(k)
        right = b.dom(k)
        state.d[k] = union_tags(left, right)
        lr = join_rep(left, a.eq.get(k, k))
        rr = join_rep(right, b.eq.get(k, k))
        if lr not in groups:
            groups[lr] = {}
        if rr not in groups[lr]:
            groups[lr][rr] = k
        state.eq[k] = groups[lr][rr]
    booleans: dict[str, bool] = {}
    for v in a.truth:
        booleans[v] = True
    for v in b.truth:
        booleans[v] = True
    for v in a.bt:
        booleans[v] = True
    for v in b.bt:
        booleans[v] = True
    for v in booleans:
        yes = union_join_domains(a.conditional(v, True), b.conditional(v, True), keys)
        no = union_join_domains(a.conditional(v, False), b.conditional(v, False), keys)
        state.boolean(v, yes, no)
    return state


def union_join_domains(a: UnionState, b: UnionState, keys: list[str]) -> UnionState:
    # Only domains and reachability feed boolean(); an unreachable edge adds no facts.
    if not a.live:
        return b
    if not b.live:
        return a
    state = UnionState(a.base, a.full)
    state.d = {k: union_tags(a.dom(k), b.dom(k)) for k in keys}
    return state
