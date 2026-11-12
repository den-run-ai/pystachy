"""Original correctness checks of the imported pyperformance workload functions."""
import asyncio

import pytest

import async_generators
import async_tree
import bpe_tokeniser
import comprehensions
import coroutines
import fannkuch
import generators
import go
import hexiom
import meteor_contest
import nqueens
import pidigits
import richards
import richards_super
import unpack_sequence


@pytest.mark.parametrize("size,expected", [(2, 1), (3, 2), (4, 4), (5, 7), (6, 10), (7, 16)])
def test_fannkuch(size: int, expected: int):
    assert fannkuch.fannkuch(size) == expected


@pytest.mark.parametrize("size", [1, 3, 17, 100])
def test_generators(size: int):
    assert list(generators.tree(range(size))) == list(range(size))
    assert generators.bench_generators(1, size) == size * (size - 1) // 2


@pytest.mark.parametrize("size", [1, 3, 17, 100])
def test_async_generators(size: int):
    async_generators.VALUES.clear()
    async_generators.run(async_generators.collect(size))
    assert async_generators.VALUES == list(range(size))
    async_generators.run(async_generators.bench_async_generators(size))


@pytest.mark.parametrize("variant,cache", [("none", 0), ("memoization", 28), ("cpu_io_mixed", 21)])
def test_async_tree(variant: str, cache: int):
    async_tree.SIZES[0] = 2.0
    async_tree.SIZES[1] = 0.0
    tree = async_tree.make_tree(variant, False)
    asyncio.run(tree.run())
    assert len(tree.cache) == cache


@pytest.mark.parametrize("n,expected", [(0, 0), (1, 1), (10, 55), (20, 6765)])
def test_coroutines(n: int, expected: int):
    assert coroutines.bench_coroutines(1, n) == expected


def test_comprehensions():
    assert comprehensions.bench_comprehensions(1) == [
        1, 3, 4, 5, 6, 17, 7, 19, 20, 21, 22, 23, 9, 11, 12, 13, 14, 15,
    ]


@pytest.mark.parametrize("size,expected_count", [(4, 2), (5, 10), (6, 4)])
def test_nqueens(size: int, expected_count: int):
    solutions = nqueens.bench_n_queens(size)
    assert len(solutions) == expected_count
    for solution in solutions:
        assert sorted(solution) == list(range(size))
        assert len(set(solution[i] + i for i in range(size))) == size
        assert len(set(solution[i] - i for i in range(size))) == size
    if size == 4:
        assert solutions == [(1, 3, 0, 2), (2, 0, 3, 1)]


def test_pidigits():
    assert pidigits.calc_ndigits(20) == [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3, 2, 3, 8, 4]


def test_bpe_tokeniser():
    encoder = bpe_tokeniser.SimpleBytePairEncoding.train("banana banana", 260, bpe_tokeniser.BPE_PATTERN)
    assert len(encoder.mergeable_ranks) == 260
    assert encoder.encode("banana banana") == [259, 32, 259]
    for text in ["banana banana", "", "日本語 🦉\tÆ É Ġ\n"]:
        tokens = encoder.encode(text)
        assert encoder.decode_bytes(tokens) == text.encode("utf-8")
        assert encoder.decode(tokens) == text


def test_richards():
    assert richards.Richards().run(1)
    assert richards.taskWorkArea.holdCount == 9297
    assert richards.taskWorkArea.qpktCount == 23246


def test_richards_super():
    assert richards_super.Richards().run(1)
    assert richards_super.taskWorkArea.holdCount == 9297
    assert richards_super.taskWorkArea.qpktCount == 23246


def test_hexiom():
    assert hexiom.main(1, hexiom.DEFAULT_LEVEL) == (
        "  3 4 2\n 2 4 4 .\n. . . 4 2\n . 2 4 3\n  . 2 ."
    )


def test_meteor_contest():
    board, cti, pieces = meteor_contest.get_puzzle(meteor_contest.WIDTH, meteor_contest.HEIGHT)
    solutions = meteor_contest.bench_meteor_contest(
        1, board, pieces, meteor_contest.SOLVE_ARG,
        meteor_contest.get_footprints(board, cti, pieces), meteor_contest.get_senh(board, cti),
    )
    assert solutions == meteor_contest.SOLUTIONS
    assert len(solutions) == 60
    assert all(len(solution) == 50 for solution in solutions)


def test_go():
    assert go.versus_cpu() == 0
    assert go.MOVES == 21121


def test_unpack_sequence():
    assert unpack_sequence.bench_tuple_unpacking(1) == 45
    assert unpack_sequence.bench_list_unpacking(1) == 45
    assert unpack_sequence.bench_all(1) == 90
