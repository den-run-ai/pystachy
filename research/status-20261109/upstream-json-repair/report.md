# Upstream json_repair report (draft, not filed)

Form: `.github/ISSUE_TEMPLATE/bug_report.yml` at upstream `dc6d02b` (2026-11-09). Checked for duplicates with an issue search for slash-related reports; only #123, an unrelated and closed infinite loop, matched. The link in [new-issue-url.txt](new-issue-url.txt) prefills every field.

## Title

[Bug]: A stray "/" before a value drops that value

## Version of the library

0.64.8 (also 0.64.1)

## Describe the bug

A `/` that does not start a comment, placed before an array item or object value, makes `repair_json` drop the item or replace the value with `""`. The rest of the document is kept, so the loss is silent. `//` and `/* */` comments in the same place are handled correctly. LLM output can contain such slashes, for example an unquoted path.

`skip_comment` steps over a lone `/`, and `parse_comment` then returns `""` inside a container instead of resuming the value.

Found while porting json_repair to Pystachy (https://github.com/den-run-ai/pystachy); reduced with AI assistance (Claude Code).

## How to reproduce

```python
from json_repair import repair_json

repair_json('[1, /2, 3]', return_objects=True)                 # [1, 3]
repair_json('{"a": 1, "b": /2, "c": 3}', return_objects=True)  # {'a': 1, 'b': '', 'c': 3}
repair_json('{"path": /usr/local/bin}', return_objects=True)   # {'path': ''}
repair_json('[1, /* note */ 2]', return_objects=True)          # [1, 2], comments are fine
```

Same results with 0.64.1 and 0.64.8 on CPython 3.13.

## Expected behavior

Treat a stray `/` like whitespace and keep the value after it: `[1, 2, 3]` and `{'a': 1, 'b': 2, 'c': 3}`. Unquoted text such as `/usr/local/bin` should come back as a string rather than `''`.
