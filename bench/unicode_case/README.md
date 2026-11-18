# Unicode case, classification and repr costs

`str`'s case methods, its classification predicates and `repr()` read a character's
Unicode properties from generated tables, without a search, in loops that keep ASCII
text on a path of its own (see
[Unicode classification](../../docs/runtime-in-subset.md#unicode-classification) and
[Unicode case](../../docs/runtime-in-subset.md#unicode-case)). These two programs
measure what that costs ASCII text against main, and how text that is not ASCII
compares with CPython. Both run unchanged under CPython, whose output is the expected
one.

- `opbench.py METHOD REPS COPIES TEXT` calls one method `REPS` times on `TEXT` repeated
  `COPIES` times: a case method, `isalpha`, `isalnum`, `isdecimal`, `isdigit`,
  `isnumeric`, `isspace` or `repr`. It tests each result without counting its
  characters.
- `casebench.py long REPS TEXT` calls the nine case methods on `TEXT` and a space,
  repeated 2,000 times. `casebench.py short REPS TEXT` calls `lower`, `upper`,
  `islower` and `title` on each word of `TEXT`.

```sh
text="Съешь же ещё этих мягких французских булок да выпей чаю "
python3.13 bench/unicode_case/opbench.py lower 2000 2000 "$text"
./pystachy build bench/unicode_case/opbench.py -o /tmp/opbench
/tmp/opbench lower 2000 2000 "$text"
valgrind --tool=callgrind --callgrind-out-file=/dev/null /tmp/opbench lower 100 2000 "$text"
```

Compare each output with CPython's before counting or timing. Callgrind's instruction
count (`Ir`) repeats exactly, so it can compare two compilers on a shared host. Wall
times need several samples, alternating between the programs on one core.

## Results

On 2026-11-18, parent `3cf23d20` (main) and candidate `03c32d8c` built the programs as
AOT executables at the default optimization, each with its own CPython-hosted compiler
and a private runtime cache, on x86-64 Linux with LLVM 18.1.3 and CPython 3.13.16.
Every output matched CPython's.
[The results file](results/2026-11-18-linux-x86_64.json) has the arguments, every
sample and the hashes of the sources.

### ASCII text

The counts are instructions of the whole process, which include startup and building
the text. The mixed-case text is
`The Quick Brown Fox Jumps Over The Lazy Dog and KEEPS running` and a space, 2,000
times: 124,000 characters. The tests read its lower-case, upper-case and titled forms,
`isalpha` and `isalnum` the text without its spaces.

| Program and arguments | Text | Parent | Candidate | Change |
|---|---|---:|---:|---:|
| `bench/words.py` | its own | 484,646,987 | 480,055,524 | −0.9% |
| `casebench.py short 20000` | mixed case | 140,753,068 | 140,578,643 | −0.1% |
| `casebench.py long 20` | mixed case | 139,718,914 | 74,718,896 | −46.5% |
| `opbench.py lower 100 2000` | mixed case | 88,664,653 | 22,812,332 | −74.3% |
| `opbench.py upper 100 2000` | mixed case | 88,669,153 | 22,816,432 | −74.3% |
| `opbench.py swapcase 100 2000` | mixed case | 89,703,917 | 23,846,832 | −73.4% |
| `opbench.py casefold 100 2000` | mixed case | 88,930,017 | 23,072,932 | −74.1% |
| `opbench.py capitalize 100 2000` | mixed case | 88,928,817 | 23,069,884 | −74.1% |
| `opbench.py title 100 2000` | mixed case | 222,836,153 | 227,101,900 | +1.9% |
| `opbench.py islower 100 2000` | lower case | 137,115,088 | 128,976,071 | −5.9% |
| `opbench.py isupper 100 2000` | upper case | 137,110,888 | 141,371,171 | +3.1% |
| `opbench.py istitle 100 2000` | titled | 189,520,788 | 177,118,171 | −6.5% |
| `opbench.py isalpha 100 2000` | no spaces | 170,706,830 | 170,702,713 | 0.0% |
| `opbench.py isalnum 100 2000` | no spaces | 200,711,930 | 200,707,813 | 0.0% |
| `opbench.py repr 100 2000` | mixed case | 175,979,542 | 175,975,273 | 0.0% |
| `opbench.py isupper 100 2000` | lower case | 711,237 | 707,420 | −0.5% |

The five methods that map a long string's ASCII letters sixteen bytes at a time take
about a quarter of main's instructions. In the last row the first letter decides.

A string of fewer than 16 bytes takes a path of its own. The next counts are
instructions for one call on a word of five letters: the difference between
`opbench.py METHOD 200000 1 WORD` and `opbench.py METHOD 0 1 WORD`, by 200,000. They
include the benchmark's own loop, which is the same on both sides.

| Method | Word | Parent | Candidate | Change |
|---|---|---:|---:|---:|
| `lower` | `Hello` | 176.5 | 166.5 | −10 |
| `upper` | `Hello` | 221.5 | 208.5 | −13 |
| `swapcase` | `Hello` | 197.5 | 187.5 | −10 |
| `casefold` | `Hello` | 229.5 | 219.5 | −10 |
| `capitalize` | `hello` | 204.2 | 204.3 | 0 |
| `title` | `hello` | 283.5 | 299.5 | +16 |
| `islower` | `hello` | 191.3 | 203.2 | +12 |
| `isupper` | `HELLO` | 149.3 | 159.2 | +10 |
| `istitle` | `Hello` | 269.3 | 281.2 | +12 |
| `isalpha` | `hello` | 346.3 | 347.2 | +1 |
| `isalnum` | `hello` | 412.3 | 413.2 | +1 |
| `repr` | `hello` | 686.2 | 685.2 | −1 |

`title` and the three case tests pay 10 to 16 instructions a call to learn whether a
byte is not ASCII, which main does not ask.

Hello world's executable is 184 bytes larger, at 94,160. The executable of
`bench/words.py`, which calls `lower()`, grows by 21,320 bytes, of `opbench.py` by
30,032 and of `casebench.py` by 29,840.

### Text that is not ASCII

Each cell is `opbench.py METHOD 2000 2000 TEXT` as the candidate's executable, then
under CPython, then the first by the second: seconds of the whole process, the median
of five samples that alternate on one core. The Russian text above is 112,000
characters of two bytes and spaces. The other two are:

```text
天地玄黃宇宙洪荒日月盈昃辰宿列張寒來暑往秋收冬藏
Élan vital à l'école élémentaire où ça coûte très cher déjà
```

Each is followed by a space, as the Russian one is. The Chinese text is 50,000
characters of three bytes and spaces, and the French one 120,000 characters, 11 of
each 60 not ASCII. The three case
tests read the lower-case, upper-case and titled form of each text, and `isalpha` and
`isalnum` the text without its spaces and apostrophe, so that both implementations
test every character.

| Method | Russian | Chinese | French |
|---|---:|---:|---:|
| `lower` | 0.80 / 0.72 = 1.11 | 0.37 / 0.33 = 1.11 | 0.32 / 0.62 = 0.52 |
| `upper` | 0.98 / 0.76 = 1.29 | 0.38 / 0.33 = 1.13 | 0.37 / 0.61 = 0.61 |
| `swapcase` | 1.13 / 1.39 = 0.81 | 0.41 / 0.41 = 1.00 | 0.40 / 1.41 = 0.28 |
| `casefold` | 0.82 / 0.80 = 1.02 | 0.39 / 0.36 = 1.06 | 0.35 / 0.70 = 0.49 |
| `title` | 1.19 / 1.60 = 0.74 | 0.63 / 0.50 = 1.26 | 0.76 / 1.09 = 0.69 |
| `capitalize` | 0.84 / 0.65 = 1.28 | 0.38 / 0.30 = 1.27 | 0.33 / 0.60 = 0.54 |
| `islower` | 0.42 / 0.71 = 0.59 | 0.27 / 0.48 = 0.56 | 0.43 / 0.76 = 0.57 |
| `isupper` | 0.40 / 0.64 = 0.62 | 0.26 / 0.48 = 0.56 | 0.40 / 0.69 = 0.58 |
| `istitle` | 0.85 / 0.91 = 0.94 | 0.61 / 0.45 = 1.37 | 0.37 / 0.87 = 0.43 |
| `isalpha` | 0.38 / 0.32 = 1.21 | 0.28 / 0.15 = 1.86 | 0.25 / 0.28 = 0.88 |
| `isalnum` | 0.38 / 0.27 = 1.44 | 0.27 / 0.14 = 1.87 | 0.26 / 0.35 = 0.76 |
| `repr` | 0.36 / 0.73 = 0.49 | 0.34 / 0.34 = 0.99 | 0.34 / 1.03 = 0.33 |

The executable takes 0.49 to 1.44 times CPython's time on the Russian text, 0.56 to
1.87 times on the Chinese one and 0.28 to 0.88 times on the French one. Its slowest
case is a classification predicate on characters of three bytes, each of which it
decodes from UTF-8 where CPython reads a 16-bit unit. With no repetitions a run takes
0.002 s as an executable and 0.013 s under CPython.

The ratios are approximate. The host is shared, and a sample differs from its median by
up to 41%. This CPython was built from source at `-O3` without profile-guided
optimization, so a distribution's build may be faster. JIT, other architectures and
other operating systems were not measured.

### Main on text that is not ASCII

Main has the classification predicates and `repr()` for such text, and searched a
sorted table for each character. The same runs with the parent's executable give its
time by CPython's, beside the candidate's from the table above:

| Method | Russian | Chinese | French |
|---|---:|---:|---:|
| `isalpha` | 9.82 → 1.21 | 10.54 → 1.86 | 2.91 → 0.88 |
| `isalnum` | 9.57 → 1.44 | 10.91 → 1.87 | 2.37 → 0.76 |
| `repr` | 6.39 → 0.49 | 6.25 → 0.99 | 1.32 → 0.33 |

Main's case methods map ASCII letters only, so its times for them are not comparable.
