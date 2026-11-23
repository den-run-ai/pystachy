"""The structure of a typed-IR function's control flow, which structured backends rely on.

Control flow goes where dataflow.flow_targets says: a block's terminator labels, the landing
block of the try statement that covers it and its check's cold block. A function's flow is
reducible: an edge that closes a cycle goes to a block that dominates the edge's source, so each
cycle has one entry, its head, and the cycles nest, as WebAssembly's loop and block constructs
do; a backend for such a target can give every block its place without a dispatch loop. The
verifier (ircheck.check_structure) holds every function to that, and holds IFn.loops, which loop
passes and structured backends read, to the loops of the flow. Dominators are Cooper, Harvey
and Kennedy's iteration ("A Simple, Fast Dominance Algorithm", 2001).
"""
from __future__ import annotations

from src.pystachy_compiler.dataflow import flow_targets
from src.pystachy_compiler.ir import IFn


class Structure:
    # The flow of fn, by each block's position in fn.blocks: its successors and predecessors
    # (each once; a label of no block of fn is left out), the blocks that entry reaches in reverse
    # postorder of a depth-first search, each block's immediate dominator (entry's is entry, an
    # unreached block's -1) and the search's retreating edges [source, target], whose target was
    # still on the search's stack: each closes a cycle
    def __init__(self, fn: IFn):
        n = len(fn.blocks)
        at: dict[str, int] = {}
        for j in range(n):
            at[fn.blocks[j].label] = j
        self.succ: list[list[int]] = []
        self.preds: list[list[int]] = []
        for j in range(n):
            out: list[int] = []
            for label in flow_targets(fn, fn.blocks[j]):
                if label in at and at[label] not in out:
                    out.append(at[label])
            self.succ.append(out)
            self.preds.append([])
        for j in range(n):
            for k in self.succ[j]:
                self.preds[k].append(j)
        # (an iterative depth-first search from entry: 0 unseen, 1 on its stack, 2 done)
        post: list[int] = []
        self.retreating: list[list[int]] = []
        state = [0] * n
        stack: list[int] = []
        nexts: list[int] = []
        if n > 0:
            state[0] = 1
            stack.append(0)
            nexts.append(0)
        while len(stack) > 0:
            j = stack[len(stack) - 1]
            k = nexts[len(nexts) - 1]
            if k < len(self.succ[j]):
                nexts[len(nexts) - 1] = k + 1
                t = self.succ[j][k]
                if state[t] == 0:
                    state[t] = 1
                    stack.append(t)
                    nexts.append(0)
                elif state[t] == 1:
                    self.retreating.append([j, t])
            else:
                state[j] = 2
                post.append(j)
                stack.pop()
                nexts.pop()
        self.rpo: list[int] = []
        for k in range(len(post) - 1, -1, -1):
            self.rpo.append(post[k])
        order = [-1] * n
        for k in range(len(self.rpo)):
            order[self.rpo[k]] = k
        self.idom: list[int] = [-1] * n
        if n > 0:
            self.idom[0] = 0
        changed = True
        while changed:
            changed = False
            for k in range(1, len(self.rpo)):
                j = self.rpo[k]
                new = -1
                for p in self.preds[j]:
                    if self.idom[p] == -1:
                        continue
                    if new == -1:
                        new = p
                        continue
                    a = p
                    b = new
                    while a != b:
                        while order[a] > order[b]:
                            a = self.idom[a]
                        while order[b] > order[a]:
                            b = self.idom[b]
                    new = a
                if new != self.idom[j]:
                    self.idom[j] = new
                    changed = True

    def reached(self, j: int) -> bool:
        return self.idom[j] != -1

    def dominates(self, a: int, b: int) -> bool:
        # does block a dominate block b (each dominates itself); nothing dominates an unreached b
        if self.idom[b] == -1:
            return False
        while a != b:
            if b == 0:
                return False
            b = self.idom[b]
        return True

    def irreducible(self) -> list[list[int]]:
        # the retreating edges whose target does not dominate their source: each closes a cycle
        # that has a second entry, which no nesting of loops and blocks can express
        found: list[list[int]] = []
        for e in self.retreating:
            if not self.dominates(e[1], e[0]):
                found.append(e)
        return found

    def loop(self, head: int) -> dict[int, bool]:
        # the natural loop of block head: head and the blocks that reach a back edge into it (an
        # edge from a block that head dominates) without passing head; {} where no back edge
        # goes to head, which is then no loop's head
        body: dict[int, bool] = {}
        work: list[int] = []
        for p in self.preds[head]:
            if self.dominates(head, p):
                work.append(p)
        if len(work) == 0:
            return body
        body[head] = True
        while len(work) > 0:
            j = work.pop()
            if j in body:
                continue
            body[j] = True
            for p in self.preds[j]:
                if self.idom[p] != -1:
                    work.append(p)
        return body
