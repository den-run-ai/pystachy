"""Finite union-tag facts, equalities and boolean implications for the IR proof.

Domains are sorted, distinct lists of type names. They are immutable once shared: states
copy their maps, never a domain's items. This keeps the domain independent of machine-int
width, including when the program has more union members than one word can represent.
"""
from __future__ import annotations


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
    def __init__(self, base: dict[str, list[str]], full: list[str]) -> None:
        self.base = base
        self.full = full
        self.d: dict[str, list[str]] = {}
        self.eq: dict[str, str] = {}
        self.bt: dict[str, dict[str, list[str]]] = {}
        self.bf: dict[str, dict[str, list[str]]] = {}
        self.truth: dict[str, int] = {}
        self.live = True

    def clone(self) -> UnionState:
        other = UnionState(self.base, self.full)
        other.d = dict(self.d)
        other.eq = dict(self.eq)
        # Implication maps, like domains, are immutable once shared.
        other.bt = dict(self.bt)
        other.bf = dict(self.bf)
        other.truth = dict(self.truth)
        other.live = self.live
        return other

    def dom(self, k: str) -> list[str]:
        return self.d.get(k, self.base.get(k, self.full))

    def forget(self, k: str) -> None:
        rep = self.eq.get(k, k)
        if k in self.eq:
            del self.eq[k]
        group = sorted([x for x in self.eq if self.eq[x] == rep])
        if len(group) > 0:
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

    def boolcopy(self, b: str, v: str) -> None:
        yes = self.conditional(v, True)
        no = self.conditional(v, False)
        # Keep incoming-edge facts too, so a join preserves a boolean phi's implication.
        self.truth[b] = (2 if yes.live else 0) | (1 if no.live else 0)
        self.bt[b] = dict(yes.d) if yes.live else {}
        self.bf[b] = dict(no.d) if no.live else {}

    def same(self, other: UnionState) -> bool:
        # States in one proof share the immutable base and full domain.
        return self.d == other.d and self.eq == other.eq and self.bt == other.bt and self.bf == other.bf and self.truth == other.truth and self.live == other.live


def union_join(a: UnionState, b: UnionState) -> UnionState:
    if not a.live:
        return b.clone()
    if not b.live:
        return a.clone()
    state = UnionState(a.base, a.full)
    keys = list(a.d)
    for k in b.d:
        if k not in a.d:
            keys.append(k)
    keys.sort()
    groups: dict[str, dict[str, str]] = {}
    for k in keys:
        left = a.dom(k)
        right = b.dom(k)
        state.d[k] = union_tags(left, right)
        # Equal constants prove equality even when each edge used different variable names.
        # Prefixes keep constant representatives distinct from arbitrary variable names.
        lr = "c:" + left[0] if len(left) == 1 else "v:" + a.eq.get(k, k)
        rr = "c:" + right[0] if len(right) == 1 else "v:" + b.eq.get(k, k)
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
