# Pystachy port: Any is inferred from each call here; the modules that store repaired values opt in.
from typing import Any


def parse_json_llm_block(parser) -> Any:
    """
    Extracts and normalizes JSON enclosed in ```json ... ``` blocks.
    """
    # Try to find a ```json ... ``` block
    if parser.json_str[parser.index : parser.index + 7] == "```json":
        i = parser.skip_to_character("`", idx=7)
        if parser.json_str[parser.index + i : parser.index + i + 3] == "```":
            parser.index += 7  # Move past ```json
            return parser.parse_json()
    return False
