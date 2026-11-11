"""Exercise cached/uncached routing and rule replacement through real fixtures."""
import pytest
import route


@pytest.fixture(autouse=True)
def rules():
    route.load(["auth.* auth", "*.failed errors", "# comment", "bad extra fields ignored"])
    yield
    route.load([])


@pytest.mark.parametrize("name,expected", [
    ("auth.failed", 0), ("db.failed", 1), ("nothing", -1), ("AUTH.failed", 1),
])
def test_cached_and_uncached_routes(name: str, expected: int):
    assert route.route(name) == expected
    assert route.route(name) == expected
    assert route.route.__wrapped__(name) == expected
    assert route.route_fnmatch(name) == expected


def test_rule_reload_invalidates_cached_answers():
    assert route.route("auth.failed") == 0
    route.load(["*.failed changed", "auth.* auth"])
    assert route.route("auth.failed") == 0
    assert route.DESTINATIONS[route.route("auth.failed")] == "changed"
    route.load([])
    assert route.route("auth.failed") == -1


def test_fixture_starts_with_fresh_rules():
    assert route.PATTERNS == ["auth.*", "*.failed"]
    assert route.DESTINATIONS == ["auth", "errors"]
