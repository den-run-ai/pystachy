"""URL decoding, duplicate query fields and canonicalization without a CLI."""
import pytest
import urlstats


@pytest.mark.parametrize("line,expected", [
    ('host "GET /search?q=one HTTP/1.1" 200', "/search?q=one"),
    ("no request", ""), ('host "broken" 400', ""),
])
def test_request_target(line: str, expected: str):
    assert urlstats.request_target(line) == expected


def test_canonical_url_keeps_escaped_slash_and_sorts_pairs():
    assert urlstats.canonical("/a%2fb/café", [("z", "two words"), ("a", "")]) == "/a%2Fb/caf%C3%A9?a=&z=two%20words"


def test_duplicate_parameter_values_count_once_per_request():
    stats = urlstats.Stats()
    assert urlstats.add(stats, "/find?q=x&q=x&q=y&empty=") == "/find?empty=&q=x&q=x&q=y"
    assert stats.requests == 1
    assert stats.params == {"q": 1, "empty": 1}
    assert stats.values["q"] == {"x": 2, "y": 1}
    urlstats.add(stats, "/find?q=%ff")
    assert stats.undecodable == 1
    assert stats.paths == {"/find": 2}
