# pystachy: dynamic-any
"""Span endpoints retain post-append heuristics, log locations and stream rules."""
import json

from json_repair import repair_json


prefix = "ordinary " * 8 + "é🌲"
sources = [
    # Quoted keys exercise the colon handling after an ordinary append.
    '{"' + prefix + ': 1,"next":2}',
    '{"' + prefix + '\\nkey: 1}',
    # Missing-key whitespace and colon must still terminate at the same position.
    '{ordinary_key: "' + prefix + '\\ntail",}',
    '{ordinary key: "' + prefix + '\\ntail",}',
    # A quote in a compact regex class is different from one after whitespace.
    '{"a":"[' + prefix.replace(" ", "") + '\"x]tail\\nend",}',
    '{"a":"[' + prefix + '\"x]tail\\nend",}',
    '{"a":"[' + prefix.replace(" ", "") + '\u2003\"x]tail\\nend",}',
    # Low smart-quote spans close at either the straight or the smart quote.
    '{"a":"' + prefix + '„inside\"tail\\nend",}',
    '{"a":"' + prefix + '„inside”tail\\nend",}',
    # Pending and nested inline containers must keep their existing state.
    '{"a":"' + prefix + ', {one: 1, two: [2]} tail\\nend",}',
    '{"a":"' + prefix + ', [one, {two: 2}] tail\\nend",}',
    # Plain spans before malformed quotes or a new member retain all logs.
    '{"a":"' + prefix + '\\nword "inside" tail", "b":2}',
    '{"a":"' + prefix + '\\ntail, "b":2}',
    # A decoded delimiter changes metadata even if the following span is plain.
    '{"a":"\\u005b' + prefix.replace(" ", "") + '\"x\\u005d tail",}',
    '{"a":"\\u007b' + prefix + '\\u007d tail',
    '["' + prefix + '\\ntail], "next"]',
    '{"a":"' + prefix + "\\",
]
for index, source in enumerate(sources):
    for stable in [False, True]:
        try:
            result = repair_json(source, return_objects=True, skip_json_loads=True,
                                 logging=True, stream_stable=stable, strict=True)
            # Include full repaired values and log contexts, never a checksum only.
            print(index, stable, json.dumps(result, ensure_ascii=True))
        except ValueError as error:
            print(index, stable, "ValueError", str(error))
