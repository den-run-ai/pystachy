# `_imp` is not shipped

The former one-thread import-lock and capability prototype has been removed.
It did not load modules, provide a builtin registry or enable a working `importlib`
workflow. Pystachy's compiler resolves imports without using this adapter.

`import _imp` is unsupported. This is an intentional compatibility reduction;
use ordinary static imports for native programs. See [library scope](../stdlib.md#library-scope).

The [former contract and evidence](https://github.com/den-run-ai/pystachy/blob/d2e57abab51080ecf4f1e2dae0a2c5a2613ee589/docs/prototypes/imp.md)
are preserved in Git history.
