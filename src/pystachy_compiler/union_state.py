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
# (the proofs' keys of values, "U:" + name and the like, by prefix and then name: made once, as
# the verifier makes the same keys in every state, function and pass, #1644)
PREFIXED: dict[str, dict[str, str]] = {}


def pkey(prefix: str, name: str) -> str:
    # prefix + name, a proof's key of a value (U: a box's tag, MU: what an address holds, B: a
    # word's bits, T: a tag value, D: a dynamic value's type, phi: a phi's incoming fact)
    if prefix not in PREFIXED:
        PREFIXED[prefix] = {}
    known = PREFIXED[prefix]
    if name not in known:
        known[name] = prefix + name
    return known[name]


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


def within(a: list[str], b: list[str]) -> bool:
    # is every tag of domain a one of domain b's (both sorted): a is their intersection, which
    # need not be made again (domains are immutable once shared, #1644)
    if len(a) > len(b):
        return False
    j = 0
    for t in a:
        while j < len(b) and b[j] < t:
            j += 1
        if j == len(b) or b[j] != t:
            return False
        j += 1
    return True


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
    if a == b or within(a, b):
        return a
    if within(b, a):
        return b
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


# UnionState's tables, each by its bit in UnionState.mine, and the empty tables that a new state
# shares until it writes one (none ever writes them: every write copies a table it does not own)
NO_DOMAINS: dict[str, list[str]] = {}
NO_NAMES: dict[str, str] = {}
NO_IMPLICATIONS: dict[str, dict[str, list[str]]] = {}
NO_TRUTHS: dict[str, int] = {}
# (and the facts of a boolean that has none, which are only read, and a join's table of the keys
# that share a first representative with others: union_join makes its own where it has any)
NO_FACTS: dict[str, list[str]] = {}
NO_GROUPS: dict[str, dict[str, str]] = {}
# (a domain that union_join gives each key until it gives it its own)
NO_TAGS: list[str] = []
OWN_D = 1
OWN_EQ = 2
OWN_LOADED = 4
OWN_BT = 8
OWN_BF = 16
OWN_TRUTH = 32
OWN_ALL = 63


class UnionState:
    def __init__(self, base: dict[str, list[str]], full: list[str], source: UnionState | None = None) -> None:
        self.base = base
        self.full = full
        # A copy shares its source's tables until either writes one, which it copies first: mine
        # has the bits (OWN_*) of the tables a state may write in place, and every write goes
        # through wd, weq, wloaded, wbt, wbf or wtruth. The proofs copy states at each block and
        # edge, after each pass that changes a function (PYSTACHY_IRCHECK), and most copies
        # write a table or two, if any: copying all six cost most of their allocations (#1644)
        # (a new state starts with the shared empty tables, NO_*, which it copies as it would a
        # source's)
        self.d: dict[str, list[str]] = NO_DOMAINS if source is None else source.d
        self.eq: dict[str, str] = NO_NAMES if source is None else source.eq
        # Object loads that still name the value in a private slot or global.
        # Equal tag domains do not establish identity between two objects.
        self.loaded: dict[str, str] = NO_NAMES if source is None else source.loaded
        # Domains and implication maps are immutable once shared.
        self.bt: dict[str, dict[str, list[str]]] = NO_IMPLICATIONS if source is None else source.bt
        self.bf: dict[str, dict[str, list[str]]] = NO_IMPLICATIONS if source is None else source.bf
        self.truth: dict[str, int] = NO_TRUTHS if source is None else source.truth
        self.live: bool = True if source is None else source.live
        self.mine = 0
        if source is not None:
            source.mine = 0

    def clone(self) -> UnionState:
        return UnionState(self.base, self.full, self)

    def wd(self) -> dict[str, list[str]]:
        # d, to write: this state's own (mine)
        if self.mine & OWN_D == 0:
            self.d = dict(self.d)
            self.mine |= OWN_D
        return self.d

    def weq(self) -> dict[str, str]:
        if self.mine & OWN_EQ == 0:
            self.eq = dict(self.eq)
            self.mine |= OWN_EQ
        return self.eq

    def wloaded(self) -> dict[str, str]:
        if self.mine & OWN_LOADED == 0:
            self.loaded = dict(self.loaded)
            self.mine |= OWN_LOADED
        return self.loaded

    def wbt(self) -> dict[str, dict[str, list[str]]]:
        if self.mine & OWN_BT == 0:
            self.bt = dict(self.bt)
            self.mine |= OWN_BT
        return self.bt

    def wbf(self) -> dict[str, dict[str, list[str]]]:
        if self.mine & OWN_BF == 0:
            self.bf = dict(self.bf)
            self.mine |= OWN_BF
        return self.bf

    def wtruth(self) -> dict[str, int]:
        if self.mine & OWN_TRUTH == 0:
            self.truth = dict(self.truth)
            self.mine |= OWN_TRUTH
        return self.truth

    def adopt(self, other: UnionState) -> None:
        # take other's domains, equalities, implications and truths (not its loads), and its
        # claim to them: other copies them before it writes them again
        self.d = other.d
        self.eq = other.eq
        self.bt = other.bt
        self.bf = other.bf
        self.truth = other.truth
        kept = OWN_D | OWN_EQ | OWN_BT | OWN_BF | OWN_TRUTH
        self.mine = (self.mine & OWN_LOADED) | (other.mine & kept)
        other.mine = other.mine & OWN_LOADED

    def dom(self, k: str) -> list[str]:
        return self.d.get(k, self.base.get(k, self.full))

    def forget(self, k: str) -> None:
        rep = self.eq.get(k, k)
        if k in self.eq:
            del self.weq()[k]
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
                self.weq()[x] = group[0]
        if k in self.d:
            del self.wd()[k]
        for b in self.bt:
            if k in self.bt[b]:
                self.wbt()[b] = {x: self.bt[b][x] for x in self.bt[b] if x != k}
        for b in self.bf:
            if k in self.bf[b]:
                self.wbf()[b] = {x: self.bf[b][x] for x in self.bf[b] if x != k}

    def set(self, k: str, domain: list[str]) -> None:
        self.forget(k)
        self.wd()[k] = domain
        self.weq()[k] = k

    def copy(self, k: str, v: str) -> None:
        if k == v:
            return
        domain = self.dom(v)
        implied = False
        for b in self.bt:
            implied = implied or v in self.bt[b]
        for b in self.bf:
            implied = implied or v in self.bf[b]
        yes: dict[str, list[str]] = NO_FACTS
        no: dict[str, list[str]] = NO_FACTS
        if implied:
            yes = {}
            no = {}
            for b in self.bt:
                if v in self.bt[b]:
                    yes[b] = self.bt[b][v]
            for b in self.bf:
                if v in self.bf[b]:
                    no[b] = self.bf[b][v]
        self.forget(k)
        self.wd()[k] = domain
        if v not in self.eq:
            self.weq()[v] = v
            self.wd()[v] = domain
        self.weq()[k] = self.eq[v]
        for b in yes:
            facts = dict(self.bt[b])
            facts[k] = yes[b]
            self.wbt()[b] = facts
        for b in no:
            facts = dict(self.bf[b])
            facts[k] = no[b]
            self.wbf()[b] = facts

    def narrow(self, k: str, domain: list[str]) -> None:
        rep = self.eq.get(k, k)
        want = intersect_tags(self.dom(k), domain)
        if len(want) == 0:
            self.live = False
        for x in self.eq:
            if self.eq[x] == rep:
                self.wd()[x] = intersect_tags(self.dom(x), want)
        self.wd()[k] = want

    def cond(self, b: str, yes: bool) -> None:
        mask = self.truth.get(b, 2 if b == "true" else 1 if b == "false" else 3)
        if mask & (2 if yes else 1) == 0:
            self.live = False
            return
        if b not in self.truth or self.truth[b] != (2 if yes else 1):
            self.wtruth()[b] = 2 if yes else 1
        self.assume(self.facts(b, yes))

    def facts(self, b: str, yes: bool) -> dict[str, list[str]]:
        # what boolean b implies of keys' domains where it holds (yes) or fails: only read
        table = self.bt if yes else self.bf
        return table[b] if b in table else NO_FACTS

    def assume(self, facts: dict[str, list[str]]) -> None:
        # narrow the domains of facts' keys, and of the keys equal to them, to theirs (cond)
        if len(facts) == 0:
            return
        groups: dict[str, list[str]] = {}
        for k in facts:
            rep = self.eq.get(k, k)
            want = intersect_tags(self.dom(k), facts[k])
            groups[rep] = intersect_tags(groups[rep], want) if rep in groups else want
        for k in self.eq:
            rep = self.eq[k]
            if rep in groups:
                self.wd()[k] = intersect_tags(self.dom(k), groups[rep])
                if len(self.d[k]) == 0:
                    self.live = False
        for k in facts:
            if k not in self.eq:
                self.wd()[k] = groups[k]
                if len(self.d[k]) == 0:
                    self.live = False

    def conditional(self, b: str, yes: bool) -> UnionState:
        other = self.clone()
        other.cond(b, yes)
        return other

    def conditional_domains(self, b: str, yes: bool) -> UnionState:
        # conditional(b, yes) for its domains and whether it is live, all that a join's
        # implications read (union_join_domains, boolean): without its truth of b, and this
        # state itself where b's facts narrow nothing (#1644)
        mask = self.truth.get(b, 2 if b == "true" else 1 if b == "false" else 3)
        facts = self.facts(b, yes)
        if mask & (2 if yes else 1) != 0 and len(facts) == 0:
            return self
        other = self.clone()
        if mask & (2 if yes else 1) == 0:
            other.live = False
        else:
            other.assume(facts)
        return other

    def boolean(self, b: str, yes: UnionState, no: UnionState) -> None:
        self.wtruth()[b] = (2 if yes.live else 0) | (1 if no.live else 0)
        self.wbt()[b] = self.changed(yes) if yes.live else NO_FACTS
        self.wbf()[b] = self.changed(no) if no.live else NO_FACTS

    def changed(self, other: UnionState) -> dict[str, list[str]]:
        # the domains of other's keys that differ from this state's, as a boolean implies them
        # (boolean): NO_FACTS where none does, as an implication map is never written once kept
        for k in other.d:
            if other.dom(k) != self.dom(k):
                return {k: other.dom(k) for k in other.d if other.dom(k) != self.dom(k)}
        return NO_FACTS

    def test(self, b: str, k: str, yes: list[str], no: list[str]) -> None:
        # boolean b holds where key k's object has a class of domain yes and fails where it has
        # one of no: boolean() of the states that narrow(k, yes) and narrow(k, no) would leave,
        # without copying this one for them
        holds = intersect_tags(self.dom(k), yes)
        fails = intersect_tags(self.dom(k), no)
        live_yes = self.live and len(holds) > 0
        live_no = self.live and len(fails) > 0
        self.wtruth()[b] = (2 if live_yes else 0) | (1 if live_no else 0)
        self.wbt()[b] = self.narrowed(k, holds) if live_yes else {}
        self.wbf()[b] = self.narrowed(k, fails) if live_no else {}

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
        self.wtruth()[b] = (2 if yes.live else 0) | (1 if no.live else 0)
        self.wbt()[b] = dict(yes.d) if yes.live else {}
        self.wbf()[b] = dict(no.d) if no.live else {}

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
        # (what is dropped goes from a table this state owns, in place, and from one it shares
        # into a table of its own made without it, #1644)
        if drop and self.mine & OWN_LOADED != 0:
            for v in [v for v in self.loaded if v not in values]:
                del self.loaded[v]
        elif drop:
            self.loaded = {v: self.loaded[v] for v in self.loaded if v in values}
            self.mine |= OWN_LOADED
        drop = False
        for k in self.d:
            if not self.needed(k, values):
                drop = True
                break
        if drop and self.mine & OWN_D != 0:
            for k in [k for k in self.d if not self.needed(k, values)]:
                del self.d[k]
        elif drop:
            self.d = {k: self.d[k] for k in self.d if self.needed(k, values)}
            self.mine |= OWN_D
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
            self.mine |= OWN_EQ
        drop = False
        for k in self.truth:
            if k not in values:
                drop = True
                break
        if drop and self.mine & OWN_TRUTH != 0:
            for k in [k for k in self.truth if k not in values]:
                del self.truth[k]
        elif drop:
            self.truth = {k: self.truth[k] for k in self.truth if k in values}
            self.mine |= OWN_TRUTH
        if self.stale(self.bt, values):
            if self.mine & OWN_BT != 0:
                self.drop_implications(self.bt, values)
            else:
                self.bt = self.kept_implications(self.bt, values)
                self.mine |= OWN_BT
        if self.stale(self.bf, values):
            if self.mine & OWN_BF != 0:
                self.drop_implications(self.bf, values)
            else:
                self.bf = self.kept_implications(self.bf, values)
                self.mine |= OWN_BF

    def drop_implications(self, table: dict[str, dict[str, list[str]]], values: dict[str, bool]) -> None:
        # retain's of a table of implications this state owns: the booleans no longer needed go,
        # and an implication map that names a key no longer needed is made again without it (a
        # map is immutable once shared)
        for b in [b for b in table]:
            if b not in values:
                del table[b]
            elif self.stale_facts(table[b], values):
                table[b] = {k: table[b][k] for k in table[b] if self.needed(k, values)}

    def kept_implications(self, table: dict[str, dict[str, list[str]]], values: dict[str, bool]) -> dict[str, dict[str, list[str]]]:
        # a table of implications made of one this state shares, as drop_implications leaves it
        kept: dict[str, dict[str, list[str]]] = {}
        for b in table:
            if b in values:
                facts = table[b]
                kept[b] = {k: facts[k] for k in facts if self.needed(k, values)} if self.stale_facts(facts, values) else facts
        return kept

    def stale_facts(self, facts: dict[str, list[str]], values: dict[str, bool]) -> bool:
        # does an implication map name a key no longer needed
        for k in facts:
            if not self.needed(k, values):
                return True
        return False

    def stale(self, implications: dict[str, dict[str, list[str]]], values: dict[str, bool]) -> bool:
        # does retain drop something of implications: a boolean or a key no longer needed
        for b in implications:
            if b not in values:
                return True
            for k in implications[b]:
                if not self.needed(k, values):
                    return True
        return False


def implied_keys(implications: dict[str, dict[str, list[str]]], d: dict[str, list[str]]) -> None:
    # add to a join's domains each key that an implication of the table names and they lack
    for condition in implications:
        for k in implications[condition]:
            if k not in d:
                d[k] = NO_TAGS


def union_join(a: UnionState, b: UnionState) -> UnionState:
    if not a.live:
        return b.clone()
    if not b.live:
        return a.clone()
    state = UnionState(a.base, a.full)
    # (the tables a join leaves empty are the new state's shared empty ones, #1644)
    if len(a.loaded) > 0 and len(b.loaded) > 0:
        state.loaded = {v: a.loaded[v] for v in a.loaded if b.loaded.get(v, "") == a.loaded[v]}
        state.mine |= OWN_LOADED
    # (the keys: a's, b's and those their implications name, which the new state's domains
    # hold as they are found, and then in sorted order each its domain, #1644)
    d = state.wd()
    for k in a.d:
        d[k] = NO_TAGS
    for k in b.d:
        if k not in d:
            d[k] = NO_TAGS
    # A parameter-backed comparison can have no unconditional override at all.
    # Its domain still has to participate in a join of the saved condition.
    implied_keys(a.bt, d)
    implied_keys(a.bf, d)
    implied_keys(b.bt, d)
    implied_keys(b.bf, d)
    keys = sorted(d)
    # (each key's representative is the first key whose pair of representatives (lr, rr) it
    # shares; most lr meet one rr alone, so a table of the others is made only where a second
    # rr meets it, and the first key's rr is found again rather than kept, #1644)
    first_key: dict[str, str] = {}
    others: dict[str, dict[str, str]] = NO_GROUPS
    eq = state.weq()
    for k in keys:
        left = a.dom(k)
        right = b.dom(k)
        d[k] = union_tags(left, right)
        lr = join_rep(left, a.eq.get(k, k))
        rr = join_rep(right, b.eq.get(k, k))
        if lr not in first_key:
            first_key[lr] = k
            eq[k] = k
        elif join_rep(b.dom(first_key[lr]), b.eq.get(first_key[lr], first_key[lr])) == rr:
            eq[k] = first_key[lr]
        else:
            if len(others) == 0:
                others = {}
            if lr not in others:
                others[lr] = {}
            if rr not in others[lr]:
                others[lr][rr] = k
            eq[k] = others[lr][rr]
    if len(a.truth) + len(b.truth) + len(a.bt) + len(b.bt) == 0:
        return state
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
        yes = union_join_domains(a.conditional_domains(v, True), b.conditional_domains(v, True), keys)
        no = union_join_domains(a.conditional_domains(v, False), b.conditional_domains(v, False), keys)
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
    state.mine |= OWN_D
    return state
