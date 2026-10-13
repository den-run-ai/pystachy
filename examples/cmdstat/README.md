# cmdstat: what a shell history holds, split by shlex

`cmdstat.py` reads a shell history, a command line per line, and splits each line as a POSIX
shell splits it, with the standard library's `shlex` ([`lib/shlex`](../../lib/README.md#shlex-a-port-of-cpythons)):
quotes and backslashes undone, and the operators `|`, `||`, `&&`, `;`, `<`, `>`, `>>` and the like
tokens of their own (`punctuation_chars=True`). It cuts each line into its commands at the operators
that join them, and counts the commands by name, the options of each, the redirections and the
pipelines by length; `--quote` prints each command instead, its words rejoined by `shlex.join()`
with the quoting a shell needs and no more. It is ordinary Python, which CPython runs as it is and
Pystachy compiles as it is:

```
$ python3 gencmds.py 200000 > history.txt     # a synthetic history: quoting, pipes, redirections
$ head -2 history.txt
cat '2026-10-13 12:00' src/main.py && mv | sed -i
git log; curl --fail -s \*.log \*.log
$ python3 cmdstat.py history.txt               # CPython
$ pystachy build cmdstat.py -o cmdstat && ./cmdstat --top 8 history.txt
200000 lines, 299151 commands, 49643 redirections, 400 lines with an open quote
the longest pipeline of a line: 1 command on 165007 lines, 2 commands on 29331 lines, 3 commands on 5262 lines
the 8 commonest of 24 commands, with their commonest options:
    12718  mkdir
    12715  docker     -v 2837, --rm 2650, -it 2380, -t 2154
    12664  grep       -i 2827, -E 2760, -v 2739, -n 2433
    ...
line 500: No closing quotation
...
$ ./cmdstat --quote history.txt
cat '2026-10-13 12:00' src/main.py
mv
sed -i
git log
curl --fail -s '*.log' '*.log'
...
```

- A line is tokenized by `shlex.shlex(line, posix=True, punctuation_chars=True)` with
  `whitespace_split`; a line whose quote is not closed raises shlex's `ValueError` (`No closing
  quotation`), which cmdstat reports with the line's number.
- The operators `|`, `||`, `&`, `&&` and `;` end a command, a pipeline is the commands that `|`
  joins, a redirection takes the word after it, and parentheses are dropped. shlex's tokens do not
  say which were quoted, so a quoted operator (`echo '|'`) is an operator here.
- `--quote` rejoins the words that shlex reads, each quoted as `shlex.quote()` quotes it: `\*.log`
  becomes `'*.log'`. shlex expands nothing, so `"$HOME"` becomes `'$HOME'`, which a shell would not
  expand.

CPython and the executable print the same report and the same commands.

## Speed

`bench.py`, on a 4-core x86-64 VM: median wall time of 5 runs with process start-up, peak RSS of
one, on a history of 200,000 lines (6.3 MB); two other jobs shared the machine. The executable is
Pystachy's AOT build of `cmdstat.py`.

| mode | CPython 3.13.16 | Pystachy AOT | speedup | CPython RSS | AOT RSS |
|---|---:|---:|---:|---:|---:|
| report | 4.746 s | 1.070 s | 4.4x | 10.9 MB | 37.3 MB |
| `--quote` | 5.153 s | 1.491 s | 3.5x | 10.9 MB | 37.3 MB |

- **The lexer is most of the time, and compiled it is about 5 times as fast:** shlex's
  `read_token()` reads a line a character at a time through its state machine, a call of
  `StringIO.read(1)` and a few string tests per character, which CPython interprets and the
  executable runs compiled (`split()` of a 100-character line: 29 µs under CPython, 5.5 µs
  compiled).
- **`--quote` gains less**: `shlex.quote()` searches each word with `lib/re`, which is slower
  than CPython's C `_sre`.
- **Memory stays bounded** in both, as cmdstat reads a line at a time; the executable's peak is
  higher, Pystachy's collector running when its heap has grown.
- Building the executable takes about 4 s, most of it `lib/re`.

## Tests

`tests/example_cmdstat.py` runs `split_line()`, `kind()` and `commands()` on their edge cases
(operators with and without spaces, redirections, parentheses, quoted operators, unclosed quotes),
on 1,000 generated lines, and `main()` with each mode and its errors, and compares what it prints
with CPython's (`tests/example_cmdstat.path` puts this directory on the module path). `bench.py`
runs the table above: `python3 -I bench.py ../../pystachy 5`, from anywhere; it writes its history
and executable to `build/cmdstat/`.
