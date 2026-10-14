# A native coding agent in typed Python

This small AskMe subset runs unchanged under CPython, Pystachy JIT, and Pystachy
AOT. The native executable manages the tools and loop; an external
OpenAI-compatible server supplies model responses. No compiler or runtime
feature changes are needed.

The canonical source is in
[AskMe's native-agent example](https://github.com/den-run-ai/askme/tree/codex/native-agent-prototype/examples/native_agent).
`UPSTREAM.json` pins the copied files and their SHA-256 hashes. AskMe retains
the complete harness and broader regression suite. This example is a separate
contract, not unchanged AskMe compatibility.
`make check-recordings` verifies the pinned hashes; `python3
tools/check_agent_source.py /path/to/askme` also compares a local source checkout.

## Recorded repair

From the Pystachy checkout root, on Linux with GNU coreutils:

```sh
./pystachy build examples/agent/agent.py -o build/askme-mini
workdir=$(mktemp -d)
cp examples/agent/fixtures/value.txt "$workdir/value.txt"
build/askme-mini "$workdir" 'Fix value.txt' 'grep -qx fixed value.txt' \
  examples/agent/fixtures/repair.json
cat "$workdir/value.txt"
rm -rf "$workdir"
```

Substitute `python3 examples/agent/agent.py` or
`./pystachy run examples/agent/agent.py` for `build/askme-mini` to compare the
same source in the other modes. The native executable needs no Python or LLVM
at execution time. Model inference is not compiled into the agent.

The recorded responses first ask to finish too early, then read, edit, run the
fixed check, and finish. Replay uses the same strict native-tool decoder as
HTTP. Receipts and the final status are JSONL; only `complete` exits 0.

## Tools and limits

| Tool | Fields | Behavior |
|---|---|---|
| `read` | `path` | UTF-8 text with explicit observation truncation |
| `write` | `path`, `content` | Atomic replacement, preserving existing permissions |
| `edit` | `path`, `old`, `new` | Exactly one nonempty literal occurrence |
| `run_test` | none | Operator-selected visible command |
| `done` | none | Requires a passing check after the latest edit/write |
| `fail` | `reason` | Failed termination |

The default is 12 response attempts (maximum 100), four recent receipts, 1 MiB
JSON/files, 32 JSON nesting levels, and 4,096-character observations. Malformed
or multiple calls, wrong fields/types, duplicate JSON keys, and content-only
responses cannot dispatch tools. Three identical consecutive actions exhaust
the run. Repetition is never completion. Existing file paths are resolved
inside the workspace; this is not a sandbox for the configured check command.

The typed JSON codec uses nodes plus integer child indices, preserves numeric
lexemes, validates UTF-8, and decodes surrogate pairs. It does not implement
CPython's `json` API or use `Any`. The initial process adapter uses external
`sh`, `timeout`, `mktemp`, `mv`, `chmod`, and `rm`; no `requests`, `subprocess`,
embedded CPython, scalar-union prototype, or pending compiler PR is required.

## HTTP mode

With `curl` and a running native-tool-capable model server:

```sh
export NATIVE_AGENT_ENDPOINT=http://127.0.0.1:8080/v1/chat/completions
export NATIVE_AGENT_MODEL=local
build/askme-mini /path/to/disposable/project 'Fix the failing parser test' \
  'make test' - 12
```

For hosted endpoints, set `NATIVE_AGENT_API_KEY`. It goes into a private
temporary header file, not shell arguments or receipts. HTTP has a 60-second
timeout and 1 MiB response cap; checks have 20 seconds plus a 2-second kill
grace and bounded output. No streaming, provider profiles, planner/replanner,
general shell tool, `.env` loader, or automatic transport retries.

## Evidence

`tests/example_agent.py` is in the ordinary CPython/JIT/AOT differential corpus.
The AskMe tests additionally compare exact transcripts and entire workspace
bytes across nine positive/negative scenarios in both native modes, including
raw/escaped Unicode and CRLF. HTTP smoke uses an actual loopback recorded-response
server in all three modes, with no model calls. To reproduce locally:

```sh
tests/run.sh ./pystachy 'jit aot' tests/example_agent.py
python3 examples/agent/http_smoke.py -- build/askme-mini
```

The smoke driver requires CPython; the compiled agent consists only of
`agent.py` and `wire_json.py`. Visible-check success supports this run's
completion, not independent patch acceptance or a model-quality result.
Live model/provider behavior has not been qualified, and no end-to-end agent
speedup is claimed. This is a portability and packaging showcase; model/tool
latency usually dominates. Native process/HTTP adapters and another typed tool
domain are useful follow-ups.
