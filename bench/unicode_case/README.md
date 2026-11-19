# Unicode case, classification and repr costs

`str`'s case methods, its classification predicates and `repr()` read a character's
Unicode properties from generated tables, without a search, in loops that keep ASCII
text on a path of its own (see
[Unicode classification](../../docs/runtime-in-subset.md#unicode-classification) and
[Unicode case](../../docs/runtime-in-subset.md#unicode-case)). These two programs
measure what that costs ASCII text against main, and how main and the candidate compare
with CPython on text that is not ASCII. Both run unchanged under CPython, whose output
is the expected one.

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

On 2026-11-18, parent `e2b97bb4` (main, v0.6.0-alpha.2) and candidate `a7611599` built
the programs as AOT executables at the default optimization, each with its own
CPython-hosted compiler and a private runtime cache, on x86-64 Linux with LLVM 18.1.3
and CPython 3.13.16. Every output matched CPython's.
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
| `bench/words.py` | its own | 494,019,280 | 480,057,028 | −2.8% |
| `casebench.py short 20000` | mixed case | 160,924,069 | 140,829,133 | −12.5% |
| `casebench.py long 20` | mixed case | 143,152,907 | 74,969,016 | −47.6% |
| `opbench.py lower 100 2000` | mixed case | 91,241,883 | 23,062,747 | −74.7% |
| `opbench.py upper 100 2000` | mixed case | 91,245,883 | 23,066,847 | −74.7% |
| `opbench.py swapcase 100 2000` | mixed case | 92,027,562 | 23,848,626 | −74.1% |
| `opbench.py casefold 100 2000` | mixed case | 91,253,862 | 23,074,726 | −74.7% |
| `opbench.py capitalize 100 2000` | mixed case | 91,007,965 | 22,822,976 | −74.9% |
| `opbench.py title 100 2000` | mixed case | 227,346,551 | 227,352,315 | 0.0% |
| `opbench.py islower 100 2000` | lower case | 128,972,692 | 128,977,865 | 0.0% |
| `opbench.py isupper 100 2000` | upper case | 141,367,792 | 141,372,965 | 0.0% |
| `opbench.py istitle 100 2000` | titled | 177,115,292 | 177,119,965 | 0.0% |
| `opbench.py isalpha 100 2000` | no spaces | 170,699,161 | 170,704,234 | 0.0% |
| `opbench.py isalnum 100 2000` | no spaces | 200,704,261 | 200,709,334 | 0.0% |
| `opbench.py repr 100 2000` | mixed case | 175,972,138 | 175,977,050 | 0.0% |
| `opbench.py isupper 100 2000` | lower case | 703,941 | 709,214 | +0.8% |

The five methods that map a long string's ASCII letters sixteen bytes at a time take
about a quarter of main's instructions. The others keep main's loops for ASCII text. In
the last row the first letter decides, and the difference is startup's.

A string of fewer than 16 bytes takes a path of its own. The next counts are
instructions for one call on a word of five letters: the difference between
`opbench.py METHOD 200000 1 WORD` and `opbench.py METHOD 0 1 WORD`, by 200,000. They
include the benchmark's own loop, which is the same on both sides.

| Method | Word | Parent | Candidate | Change |
|---|---|---:|---:|---:|
| `lower` | `Hello` | 202.5 | 166.5 | −36 |
| `upper` | `Hello` | 242.5 | 208.5 | −34 |
| `swapcase` | `Hello` | 222.7 | 188.8 | −34 |
| `casefold` | `Hello` | 256.7 | 220.8 | −36 |
| `capitalize` | `hello` | 220.5 | 205.5 | −15 |
| `title` | `hello` | 320.5 | 299.5 | −21 |
| `islower` | `hello` | 225.8 | 200.8 | −25 |
| `isupper` | `HELLO` | 182.8 | 156.8 | −26 |
| `istitle` | `Hello` | 281.8 | 278.8 | −3 |
| `isalpha` | `hello` | 343.8 | 344.8 | +1 |
| `isalnum` | `hello` | 409.8 | 410.8 | +1 |
| `repr` | `hello` | 687.4 | 686.5 | −1 |

Hello world's executable is 152 bytes larger than main's, at 94,128. The executable of
`bench/words.py`, which calls `lower()`, grows by 4,464 bytes, of `opbench.py` by 4,704
and of `casebench.py` by 4,584.

### Text that is not ASCII

Each cell is the time of `opbench.py METHOD 2000 2000 TEXT` by CPython's, first for
main's executable, then for the candidate's: seconds of the whole process, the median of
five samples that alternate main, the candidate and CPython on one core. The Russian
text above is 112,000 characters of two bytes and spaces. The other two are:

```text
天地玄黃宇宙洪荒日月盈昃辰宿列張寒來暑往秋收冬藏
Élan vital à l'école élémentaire où ça coûte très cher déjà
```

Each is followed by a space, as the Russian one is. The Chinese text is 50,000
characters of three bytes and spaces, and the French one 120,000 characters, 11 of
each 60 not ASCII. The three case tests read the lower-case, upper-case and titled form
of each text, and `isalpha` and `isalnum` the text without its spaces and apostrophe,
so that every implementation tests every character.

| Method | Russian | Chinese | French |
|---|---:|---:|---:|
| `lower` | 4.39 → 1.41 | 6.62 → 1.44 | 2.15 → 0.56 |
| `upper` | 6.11 → 1.79 | 6.35 → 1.49 | 2.10 → 0.59 |
| `swapcase` | 4.00 → 0.98 | 5.81 → 1.22 | 1.41 → 0.30 |
| `casefold` | 4.53 → 1.44 | 5.95 → 1.36 | 2.04 → 0.54 |
| `title` | 3.54 → 0.89 | 6.12 → 1.47 | 1.35 → 0.62 |
| `capitalize` | 4.26 → 1.53 | 6.41 → 1.44 | 2.15 → 0.57 |
| `islower` | 6.09 → 0.59 | 4.90 → 0.64 | 2.29 → 0.52 |
| `isupper` | 5.94 → 0.55 | 4.66 → 0.64 | 2.52 → 0.53 |
| `istitle` | 4.22 → 0.72 | 5.29 → 1.21 | 1.65 → 0.38 |
| `isalpha` | 10.07 → 0.97 | 10.19 → 1.79 | 2.94 → 0.93 |
| `isalnum` | 9.45 → 0.91 | 10.19 → 1.79 | 3.07 → 0.95 |
| `repr` | 5.51 → 0.52 | 4.91 → 1.00 | 1.18 → 0.33 |

Main, which searches a sorted table for each character that is not ASCII, takes 3.5 to
10.2 times CPython's time on the Russian and Chinese texts and 1.2 to 3.1 times on the
French one. The candidate takes 0.52 to 1.79 times on the Russian text, 0.64 to 1.79
times on the Chinese one and 0.30 to 0.95 times on the French one. Its slowest cases are
`upper()` on the Russian text, which changes nearly every character, and `isalpha()` and
`isalnum()` on the Chinese one, whose characters it decodes from three bytes each where
CPython reads a 16-bit unit. With no repetitions a run takes 0.003 s as an executable
and 0.012 s under CPython.

The ratios are approximate. The host is shared: single samples strayed up to 73% from
their medians, which are of five. This CPython was built from source at `-O3` without
profile-guided optimization, so a distribution's build may be faster. JIT, other
architectures and other operating systems were not measured.
