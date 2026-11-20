"""The TOML kernel on a small generated document, read back as dynamic values."""
import tomli_loads


def test_tomli_loads():
    text = tomli_loads.synthetic_document(3)
    assert len(text) == 24096
    before = len(tomli_loads.TIMED)
    tomli_loads.bench_tomli_loads(2, text)
    assert len(tomli_loads.TIMED) == before + 1
    pulls = tomli_loads.tomli.loads(text)["data"]
    assert len(pulls) == 3
    assert pulls[0]["number"] + pulls[1]["number"] + pulls[2]["number"] == 93214 + 93213 + 93212
    assert pulls[2]["title"] == '[3.11] gh-91922: Fix item 2 for a "quoted" encoding'
    assert pulls[0]["body"] == "Fix item 0.\r\n\r\nA second paragraph with a tab\tand é.\r\n"
    assert pulls[1]["head"]["repo"]["topics"] == ["topic1", "topic1", "shared"]
    assert pulls[2]["labels"][1]["name"] == "awaiting review 1"
    assert pulls[0]["locked"] and not pulls[1]["locked"]
    assert "requested_reviewers" not in pulls[0] and len(pulls[2]["requested_reviewers"]) == 2
    assert pulls[2]["_links"]["statuses"]["href"].endswith("/pulls/93212/statuses")
