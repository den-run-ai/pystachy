# Compiler source

The self-hosting compiler lives in `pystachy_compiler/`. The root
[`pystachy.py`](../pystachy.py) is its compatibility entry point. These modules
remain valid Python and compile together through Pystachy's existing loader.

## Component map

| Area | Modules and responsibility |
|---|---|
| Syntax | [lexer](pystachy_compiler/lexer.py), [parser](pystachy_compiler/parser.py), [syntax](pystachy_compiler/syntax.py): tokens, parsing and AST nodes. |
| Imports | [loader](pystachy_compiler/loader.py), [module](pystachy_compiler/module.py): source discovery, qualification and module records. |
| Analysis | [analysis](pystachy_compiler/analysis.py), [scope](pystachy_compiler/scope.py), [flow](pystachy_compiler/flow.py): AST queries, lexical checks and definite assignment. |
| Compilation | [gen](pystachy_compiler/gen.py), [program](pystachy_compiler/program.py), [functions](pystachy_compiler/functions.py): compiler state, program orchestration and function compilation. |
| Types | [declarations](pystachy_compiler/declarations.py), [templates](pystachy_compiler/templates.py): annotations, fields and specialization. |
| Values | [variables](pystachy_compiler/variables.py), [expressions](pystachy_compiler/expressions.py): binding, closures and expression typing. |
| Calls | [calls](pystachy_compiler/calls.py), [builtins](pystachy_compiler/builtins.py): function dispatch and builtin operations. |
| Containers | [containers](pystachy_compiler/containers.py), [conversions](pystachy_compiler/conversions.py): collection operations, coercion and runtime slots. |
| Control flow | [statements](pystachy_compiler/statements.py), [exceptions](pystachy_compiler/exceptions.py): statements, loops and exceptional cleanup. |
| Typed IR | [ir](pystachy_compiler/ir.py), [emission](pystachy_compiler/emission.py): records, instruction building and function-state save/restore. |
| Backend | [ircheck](pystachy_compiler/ircheck.py), [optimizations](pystachy_compiler/optimizations.py), [lowering](pystachy_compiler/lowering.py): verification, effects, IR passes and LLVM lowering. |
| Shared support | [specs](pystachy_compiler/specs.py), [diagnostics](pystachy_compiler/diagnostics.py), [names](pystachy_compiler/names.py), [utils](pystachy_compiler/utils.py): operation tables, source locations, names and type helpers. |
| CLI | [driver](pystachy_compiler/driver.py): JIT, AOT, extensions, LLVM tools and runtime caching. |

## How components fit

The driver loads source through the loader. The lexer, parser and scope checks
produce ASTs; import qualification supplies module records. `Gen.program` gathers
declarations and runs flow analysis. Its AST walk resolves and types operations
while building function IR. Verification, effect analysis and optimization feed
LLVM lowering; the driver then selects JIT execution, AOT linking or extension
output. Typing and emission still share this walk; splitting files does not add a
separate type-checking pass.

`Gen` owns shared compilation state and exposes forwarding methods. Their bodies
live in the operation modules as generic `gen_*` functions taking an explicit
`self`, specialized to `Gen` by the self-hosted compiler. This keeps dependencies
one-way: operation modules import shared records and helpers, while `gen.py`
imports the operations. They do not import `Gen`. Explicit forwarding keeps this
module boundary visible and requires neither mixins nor dynamic method installation.

## Entry points and bootstrap

Run the same commands from the repository root: `python3 pystachy.py`,
`python3 -m pystachy`, or the native `./pystachy`, followed by a subcommand.
`make` follows imports from the root entry point, builds the native stages and
checks their compiler and runtime IR fixed points.

The Makefile tracks compiler modules as build inputs. The hosted driver's
`COMPILER_SOURCES` list also contributes their contents to runtime-cache identity
and checks that they remain unchanged while publishing a cache entry. Add new
source files there when extending the layout.
