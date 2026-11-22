"""Result checks of the regex benchmark ports."""
import regex_compile
import regex_dna
import regex_effbot
import regex_v8


def test_regex_compile():
    regexes = regex_compile.capture_regexes("bench/pyperformance/data/regex_compile.txt")
    assert len(regexes) == 4267
    compiled = 0
    for regex, flags, pattern in regexes:
        if pattern is not None:
            assert flags == 0 and pattern.pattern == regex
            assert regex_compile.re.compile(pattern, flags) is pattern
            compiled += 1
    assert compiled == 1470
    assert regexes[0] == ("Python|Perl", 0, None)
    regex_compile.bench_regex_compile(1, regexes[:300])
    assert len(regex_compile.TIMED) == 1 and regex_compile.TIMED[0] >= 0.0


def test_regex_dna():
    source = regex_dna.init_benchmarks(100, regex_dna.DEFAULT_RNG_SEED)
    assert regex_dna.bench_regex_dna(1, source, None) == ([0, 0, 0, 0, 0, 0, 0, 0, 0], 1095, 1000, 1334)


def test_regex_effbot():
    assert regex_effbot.bench_regex_effbot(1) == 636833


def test_regex_v8():
    assert regex_v8.bench_regex_v8(1) == 369067584475
