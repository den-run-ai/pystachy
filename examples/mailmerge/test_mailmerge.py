"""Template and split rendering share inputs and assertions across runtimes."""
from string import Template

import mailmerge
import pytest


def test_template_and_split_rendering_agree():
    template = Template("Dear $name: $$${amount} ($seq/$count)")
    record = mailmerge.parse(["name", "amount"], "Ada\t12\n", 2)
    texts, names = mailmerge.split(template)
    assert mailmerge.check(template, ["name", "amount"], False) == ""
    assert mailmerge.render(template, record, 1, 3, False) == "Dear Ada: $12 (1/3)"
    assert mailmerge.render_split(texts, names, record, 1, 3) == "Dear Ada: $12 (1/3)"


def test_safe_rendering_preserves_missing_field():
    template = Template("$name: $missing")
    assert mailmerge.check(template, ["name"], False) == "no field missing in the data"
    assert mailmerge.check(template, ["name"], True) == ""
    assert mailmerge.render(template, {"name": "Ada"}, 1, 1, True) == "Ada: $missing"


def test_record_width_is_checked():
    with pytest.raises(ValueError, match="line 7: 1 fields"):
        mailmerge.parse(["name", "amount"], "only one", 7)


def test_mbox_escape_only_changes_from_lines():
    assert mailmerge.escape_from("From first\nFrom second\nnot From third") == ">From first\n>From second\nnot From third"
