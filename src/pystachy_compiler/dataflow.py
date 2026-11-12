"""Shared control flow, liveness and worklist for forward analyses of typed IR.

The closed-union and dynamic-payload proofs (union_proof.py, dynamic_proof.py) walk one
control-flow graph: a block's terminator labels, the landing block of the try statement that
covers it (Blk.handler, until eh_ir makes invokes) and a check's cold block. They drop the
facts of values nothing can read any more, and they join facts over a worklist until stable.
Those three parts are here once. An analysis keeps what is its own: how a block changes its
facts and which edges leave it (flow), how an edge carries facts into a block's phis (edge)
and what it reports once the facts are stable (transfer, checking).
"""
from __future__ import annotations

from src.pystachy_compiler.ir import Blk, IFn
from src.pystachy_compiler.union_state import UnionState, union_join


def flow_targets(fn: IFn, b: Blk) -> list[str]:
    # the labels control may go to from b: its terminator's, the landing block of the try
    # statement that covers it (an op of it that raises goes there) and its check's cold block.
    # A label that names no block of fn is the caller's to skip
    last = b.code[-1]
    targets = [v for v in last.b]
    if b.handler != "":
        targets.append(b.handler)
    if last.op == "check":
        key = last.x if last.x != "" else last.s
        if key in fn.cold:
            targets.append(fn.cold[key])
    return targets


def live_values(fn: IFn, blocks: dict[str, int]) -> dict[str, dict[str, bool]]:
    # the values (%tN, parameters, slot addresses) that some path may still read from each
    # block's first op that is no phi, by label: blocks gives each label's position in
    # fn.blocks. A block's phis have their values by then, so a phi that is read counts there
    # as any value does; on an edge into the block it is that edge's operand that is read
    live_at: dict[str, dict[str, bool]] = {}
    uses: dict[str, dict[str, bool]] = {}
    defined: dict[str, dict[str, bool]] = {}
    for b in fn.blocks:
        uses[b.label] = {}
        defined[b.label] = {}
        live_at[b.label] = {}
        for i in b.code:
            if i.op == "phi":
                continue
            for a in i.a:
                if a.v.startswith("%") and a.v not in defined[b.label]:
                    uses[b.label][a.v] = True
            for n in i.r:
                defined[b.label]["%t" + str(n)] = True
    changed = True
    while changed:
        changed = False
        for bn in range(len(fn.blocks) - 1, -1, -1):
            b = fn.blocks[bn]
            live = dict(uses[b.label])
            for target in flow_targets(fn, b):
                if target not in blocks:
                    continue
                incoming = dict(live_at[target])
                for i in fn.blocks[blocks[target]].code:
                    if i.op != "phi":
                        break
                    r = "%t" + str(i.r[0])
                    if r in incoming:
                        del incoming[r]
                        if b.label in i.b:
                            v = i.a[i.b.index(b.label)].v
                            if v.startswith("%"):
                                incoming[v] = True
                for v in incoming:
                    if v not in defined[b.label]:
                        live[v] = True
            if live != live_at[b.label]:
                live_at[b.label] = live
                changed = True
    return live_at


def forward_fixpoint(self) -> None:
    # Run the analysis self over its function (self.fn, with self.blocks its labels' positions)
    # from the entry block until no block's starting facts change, then let it report. Its facts
    # are UnionStates over self.base and self.full. For each block taken from the worklist,
    # self.flow(block, facts, targets, edges) changes a copy of the block's starting facts as
    # its ops do and appends each edge that leaves it: a target label and the facts on that
    # edge. An edge whose facts are dead (not live), or whose target is no block, is dropped;
    # self.edge(facts, source, target) gives the others' facts at the target's start, which
    # join what other edges brought there. A block whose starting facts changed is queued
    # again, once. Blocks are taken first in, first out, so the visits and their order depend
    # on the function alone. Only then does self.transfer(facts, op, label, True) see each
    # reached block's ops with its final facts: reporting on a first visit would miss a later
    # unsafe join or loop back edge
    starts: dict[str, UnionState] = {"entry": UnionState(self.base, self.full)}
    pending: list[str] = ["entry"]
    queued: dict[str, bool] = {"entry": True}
    head = 0
    while head < len(pending):
        label = pending[head]
        head += 1
        queued[label] = False
        s = starts[label].clone()
        self.visits += 1
        targets: list[str] = []
        edges: list[UnionState] = []
        self.flow(self.fn.blocks[self.blocks[label]], s, targets, edges)
        for j in range(len(targets)):
            target = targets[j]
            if not edges[j].live or target not in self.blocks:
                continue
            state = self.edge(edges[j], label, target)
            merged = union_join(starts[target], state) if target in starts else state
            if target not in starts or not merged.same(starts[target]):
                starts[target] = merged
                if target not in queued or not queued[target]:
                    pending.append(target)
                    queued[target] = True
    for label in starts:
        s = starts[label].clone()
        for i in self.fn.blocks[self.blocks[label]].code:
            if i.op != "phi":
                self.transfer(s, i, label, True)
