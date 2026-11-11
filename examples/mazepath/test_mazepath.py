"""BFS path invariants and input padding, shared by CPython and native tests."""
import mazepath


def test_shortest_path_and_depths():
    rows, width, start, end = mazepath.parse(["S..", ".#.", "..E"])
    parent = mazepath.search(rows, width, start)
    steps = mazepath.path(parent, end)
    assert steps[0] == start
    assert steps[-1] == end
    assert len(steps) == 5
    assert mazepath.depths(parent, start)[end] == 4
    for left, right in zip(steps, steps[1:]):
        assert abs(left - right) == 1 or abs(left - right) == width
        assert rows[right // width][right % width] != "#"


def test_unreachable_destination():
    rows, width, start, end = mazepath.parse(["S#E"])
    parent = mazepath.search(rows, width, start)
    assert parent[end] == -1
    assert mazepath.depths(parent, start) == [0, -1, -1]


def test_short_rows_are_padded_and_blank_rows_ignored():
    assert mazepath.parse(["", "S.\n", "E\n"]) == (["S.", "E#"], 2, 0, 2)
    assert mazepath.parse([]) == ([], 0, -1, -1)
