"""Probe stand-in for the ast_serialize Rust extension; bodies raise."""


def parse(fnam: str, source: str | bytes | None = None, skip_function_bodies: bool = False,
          python_version: tuple[int, int] | None = None, platform: str | None = None,
          always_true: list[str] | None = None, always_false: list[str] | None = None,
          cache_version: int = 0) -> tuple[bytes, list[dict[str, str]], list[tuple[int, list[str]]], bytes, dict[str, str]]:
    raise NotImplementedError("ast_serialize.parse")


def parse_type_string(source: str, range: tuple[int, int, int, int], cache_version: int = 0) -> bytes:
    raise NotImplementedError("ast_serialize.parse_type_string")
