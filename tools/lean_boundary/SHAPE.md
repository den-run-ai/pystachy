# Typed-IR shape and def-before-use checks

`PystachyShape.lean` proves what an accepted typed-IR function's shape is, against the
compiler's [operation table](../../docs/typed-ir.md#operation-reference).
`check_lean_shape.py` projects the functions of an inspection snapshot, or of
[typed-IR text](../../docs/typed-ir.md#text-form), into that model and runs the checker.

From the repository root, with the pinned Lean toolchain on `PATH`:

```sh
make check-lean-boundary PY=python3.13
python3.13 tools/inspect_compiler.py tools/inspection_examples/score_samples.py \
  --output /tmp/pystachy-shape-example
python3.13 tools/check_lean_shape.py /tmp/pystachy-shape-example/typed-after.json
python3.13 tools/check_lean_shape.py tools/fixtures/typed_ir/score_samples.listget.after.tir
```

The output directory must be new. Each path prints one JSON line with the functions and
instructions checked and, for each rejected function, the first obligation it fails. Exit 0
means Lean accepted every function, 1 means it rejected one, and 2 means malformed input, a
missing checker or an operational error.

## Proven properties

`accepted_wellFormed` proves that a function the checker accepts is `WellFormed`:

| Field | Property |
|---|---|
| `shaped` | Each instruction names a row of the table and has its operand, result and label counts, sets no field outside the row's, and holds only operands of the closed kinds. Entry storage is among the slots and nowhere else. A parameter operand is below the parameter count, and no branch names the entry block. |
| `terminated` | Each block is instructions that do not end a block, followed by one that does: a terminator, or a call with an exception edge. |
| `labelled`, `resolved` | Block labels are distinct, and every label an instruction holds, a `check`'s error block included, is a block's. |
| `singleDefinition` | No value number is among the results of two block instructions, or twice among one's. |
| `defined`, `stored` | Each value an operand reads is some block instruction's result, and each slot an operand names is a slot the function holds. |

`accepted_single_definition` and `accepted_terminator_last` restate two of these for a
reader of the theorem list. `distinct_sound` and `covers_sound` prove the two decision
procedures that are not linear scans: sorting before comparing neighbours, and a hash set
of the definitions.

## Def-before-use

`PystachyDominance.lean` proves that each value an accepted function reads is defined on
every path to the read. A path is a `Walk` from the entry block along the control-flow graph:
each instruction's labels and a `check`'s error block, but not a phi's labels, which name
its predecessors.

The adapter claims each reachable block's immediate dominator, computed by Cooper, Harvey and
Kennedy's iteration. Lean does not trust the claim. It checks that the entry block has no
parent and that every edge out of a block of the tree goes to a block whose parent is an
ancestor of the edge's source. `walk_dominated` proves that every block on a path is in the
tree and that each ancestor of a block lies on every path to it.

| Theorem | Property |
|---|---|
| `accepted_defined_before_use` | On every path to an instruction that is no phi, each value it reads is defined earlier in its block, or in a block the path went through before. An invoke's results are first defined at the start of its normal successor, every edge into which comes from the invoke's block. |
| `accepted_phi_defined` | Each value a phi of a reachable block reads from a predecessor is defined on every path to the end of that predecessor. |

The check finds each definition through a hash map whose entries are only claims:
`lookup_sound` proves that a found definition is an instruction of a block of the function
that has the value among its results. Code no path reaches is not checked. Single definition
comes from the shape check, so the definition found is the value's only one. The corpus row
of the [Lean report](REPORT.md) runs both checks on every function of every program.

## Trust boundary

Lean checks the candidate, not the compiler. The adapter is trusted to read `OPS`, to number
operations and labels, to classify each operand with `ir.operand_kind`, and to match a slot
operand to a slot's own register. A snapshot or text is an observation of the IR, not the
IR that lowering consumed.

The dominator tree is not trusted, but the control-flow graph is the adapter's: it draws
each edge from an instruction's labels and a `check`'s error block, as the compiler's own
verifier does. Operand and result types, effects, the result count of a call (the table says
none or one; the signature decides), what an exception edge carries and LLVM lowering are
outside the model. The
compiler's own verifier (`PYSTACHY_IRCHECK=1`) checks the table's counts and fields too;
this checker shares the table with it and nothing else.
