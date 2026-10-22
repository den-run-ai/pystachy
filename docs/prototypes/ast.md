# `_ast` is not shipped

The former typed expression-node prototype has been removed. It supplied constructors
and fields, but no source parser, AST compilation or shipped application consumer.
Pystachy's own parser does not depend on this adapter.

`import _ast` and the upstream `ast` package are unsupported in native programs.
This is an intentional compatibility reduction. See [library scope](../stdlib.md#library-scope).

The [former contract and evidence](https://github.com/den-run-ai/pystachy/blob/d2e57abab51080ecf4f1e2dae0a2c5a2613ee589/docs/prototypes/ast.md)
are preserved in Git history.
