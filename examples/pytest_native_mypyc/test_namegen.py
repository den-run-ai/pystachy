"""Original tests of the unmodified pinned mypyc namegen module."""
import pytest
from namegen import NameGenerator, candidate_suffixes, exported_name, make_module_translation_map


@pytest.mark.parametrize("source,expected", [
    ("pkg.module.value", "pkg___module___value"),
    ("pkg.___value", "pkg______3_value"),
    ("plain", "plain"),
])
def test_exported_name(source: str, expected: str):
    assert exported_name(source) == expected


def test_candidate_suffixes():
    assert candidate_suffixes("app.tools.parser") == ["", "parser.", "tools.parser.", "app.tools.parser."]


def test_minimal_unique_module_names():
    names = make_module_translation_map(["app.parser", "app.lexer", "vendor.parser"])
    assert names["app.parser"] == "app.parser."
    assert names["app.lexer"] == "lexer."
    assert names["vendor.parser"] == "vendor.parser."


@pytest.fixture
def generator() -> NameGenerator:
    return NameGenerator([["app.parser", "app.lexer"]])


def test_private_name_cache(generator: NameGenerator):
    first = generator.private_name("app.parser", "parse.expr")
    assert first == "parser___parse___expr"
    assert generator.private_name("app.parser", "parse.expr") == first
    assert len(generator.translations) == 1


def test_unknown_module_and_global_name(generator: NameGenerator):
    assert generator.private_name("external.module", "run") == "external___module___run"
    assert generator.private_name("", "temporary") == "temporary"


def test_whole_module_name(generator: NameGenerator):
    assert generator.private_name("app.parser") == "parser"
    with pytest.raises(KeyError):
        generator.private_name("not.compiled")


def test_separate_compilation():
    generator = NameGenerator([["app.parser"]], separate=True)
    assert generator.private_name("app.parser", "run") == "app___parser___run"


def test_single_module_shortens_entire_prefix():
    generator = NameGenerator([["app.parser"]])
    assert generator.private_name("app.parser", "run") == "run"
