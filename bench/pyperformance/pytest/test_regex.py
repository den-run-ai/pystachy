"""Result checks of the three existing regex benchmark ports."""
import regex_dna
import regex_effbot
import regex_v8


def test_regex_dna():
    source = regex_dna.init_benchmarks(100, regex_dna.DEFAULT_RNG_SEED)
    assert regex_dna.bench_regex_dna(1, source, None) == ([0, 0, 0, 0, 0, 0, 0, 0, 0], 1095, 1000, 1334)


def test_regex_effbot():
    assert regex_effbot.bench_regex_effbot(1) == 636833


def test_regex_v8():
    assert regex_v8.bench_regex_v8(1) == 369067584475
