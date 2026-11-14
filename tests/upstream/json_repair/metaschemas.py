"""Regenerate the json_repair port's metaschemas from jsonschema-specifications.

Usage: metaschemas.py SCHEMAS [--check]
SCHEMAS is the schemas directory of an installed jsonschema-specifications 2025.9.1 (its files'
SHA-256 hashes are pinned below). Writes ports/json_repair/_jsonschema/_metaschemas.py, or with
--check only compares it.

Each vocabulary document that a 2019-09 or 2020-12 metaschema refers to is inlined where its
$ref stood, its $defs join the root's, and $dynamicRef "#meta" and $recursiveRef "#" become
$ref "#", which is what they resolve to while a schema is checked against its metaschema.
Annotations (titles, comments, defaults) are dropped. The order of the other keywords is kept:
jsonschema reports the first error in that order.
"""
import hashlib
import json
from pathlib import Path
import sys

ANNOTATIONS = {"title", "description", "$comment", "default", "deprecated", "examples", "$schema", "$id", "id",
               "$vocabulary", "$dynamicAnchor", "$recursiveAnchor"}
MAPS = {"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"}
ARRAYS = {"allOf", "anyOf", "oneOf", "prefixItems"}
SCHEMAS = {"items", "additionalItems", "additionalProperties", "contains", "propertyNames", "not", "if", "then", "else",
           "unevaluatedItems", "unevaluatedProperties", "contentSchema"}


def flat(node, documents, defs):
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str) and ref in documents:
        assert list(node) == ["$ref"], node
        body = documents[ref]
        defs.update(body.get("$defs", {}))
        return flat({key: value for key, value in body.items() if key != "$defs"}, documents, defs)
    out = {}
    for key, value in node.items():
        if key in ANNOTATIONS:
            continue
        if key == "$dynamicRef":
            assert value == "#meta"
            key, value = "$ref", "#"
        elif key == "$recursiveRef":
            assert value == "#"
            key, value = "$ref", "#"
        elif key == "$ref":
            if "#" in value and value.split("#")[0] in documents:
                value = "#" + value.split("#", 1)[1]
            assert value.startswith("#"), value
        elif key in MAPS:
            value = {name: flat(each, documents, defs) for name, each in value.items()}
        elif key in ARRAYS or (key == "items" and isinstance(value, list)):
            value = [flat(each, documents, defs) for each in value]
        elif key in SCHEMAS:
            value = flat(value, documents, defs)
        elif key == "dependencies":
            value = {name: flat(each, documents, defs) if isinstance(each, dict) else each for name, each in value.items()}
        out[key] = value
    return out


SHA256 = {
    "draft201909/metaschema.json": "7b761b3e121f0a0ca1ea2a0b8e2cc856bcf801604b8268d71bacaa202bc0c13b",
    "draft201909/vocabularies/applicator": "6895100e99726fbb107058512bbec3ecfd4b24e8fd2facee3e505ee72b0d4c31",
    "draft201909/vocabularies/content": "9b7d4f55a4e2fdb02c430068fdffabc732addce238da3f1df2690249c3353274",
    "draft201909/vocabularies/core": "b5a2c4957f6495d0a5081f0409ebe8a14e4139acb203fc748471f8ede2af5b2c",
    "draft201909/vocabularies/format": "50ebbfe790611a849b8cc400a09c1d0e0fb6ab5c0d43a0f22201fd3625056bf4",
    "draft201909/vocabularies/meta-data": "d47e2445dd6a82271a298d83cc6c6cb8d4ae1e15e0dc56becd37a163ecf01286",
    "draft201909/vocabularies/validation": "1e526c1d335a734805fc82cf5798c12b960ad7da2517c66cda5a1b09359c3c1c",
    "draft202012/metaschema.json": "41da76f5afb7ce062d248f762463a92f7ca47e4e0f905b224ba6afeef91ded0f",
    "draft202012/vocabularies/applicator": "c4a6e4147b91fef7fea6dc058cb1bf93402f7414b76578a8b16aaf1dad6aacef",
    "draft202012/vocabularies/content": "08343747764e4a5814262793cf4d652057a7913863c5950d43297e8e1fdac5b6",
    "draft202012/vocabularies/core": "c2d12a8e4dd11d336dfc83a3f663aa4c69f0b49b3beb094ffeb25b5316f4803d",
    "draft202012/vocabularies/format-annotation": "abc775adfefd89d22358170d9bf93f4ebd2349563bbbedd60f02bef7c812bcc0",
    "draft202012/vocabularies/format-assertion": "c52242b9a1bb786b26c3e82c7add428c31f9c96e575dce99e56ea5feaa6da20c",
    "draft202012/vocabularies/meta-data": "8f76d6e14f41b9b92ef933b708cdc5144c8b5268651ad11918485fb1754f1c76",
    "draft202012/vocabularies/unevaluated": "2dbfbcb73994b670b0976492adee1fffb46c21682784d2f5a4ca561f9e2d0cb4",
    "draft202012/vocabularies/validation": "7010a31e541f32d2be721e2de348df75c9b36876a3ed304877fc0abda1d37a58",
    "draft4/metaschema.json": "e1489d0b4755f02793302591d3fcb8f07b6893a82a94f24895f8e4edf11b82e2",
    "draft6/metaschema.json": "c29dfce9f54835c3a06c03b3c5d5ec0eda77706568f9c4df7cfbc7566a51006d",
    "draft7/metaschema.json": "3d5392088261606c559b603f385329c9f1ab45b5d667eb990687453b055d405e",
}
MODULE = Path(__file__).resolve().parents[3] / "ports/json_repair/_jsonschema/_metaschemas.py"
HEADER = '''"""The metaschemas of JSON Schema drafts 4, 6, 7, 2019-09 and 2020-12, one self-contained schema each.

Pystachy port: generated by tests/upstream/json_repair/metaschemas.py from the metaschemas that
jsonschema-specifications 2025.9.1 distributes (MIT, Julian Berman; the schemas are the JSON Schema
organisation's). A 2019-09 or 2020-12 metaschema's vocabulary documents are inlined where it refers to
them, $dynamicRef "#meta" and $recursiveRef "#" are the $ref "#" they resolve to while a schema is
checked, and annotations are dropped. The order of the other keywords is the metaschema's: it decides
which error a schema that fails is reported with.
"""

METASCHEMAS: dict[int, str] = {
'''


def flattened(root):
    """Each draft's flattened metaschema, from sources that must be the pinned release's."""
    result = {}
    for name, directory in (("4", "draft4"), ("6", "draft6"), ("7", "draft7"), ("2019", "draft201909"),
                            ("2020", "draft202012")):
        def load(relative):
            data = (root / relative).read_bytes()
            if hashlib.sha256(data).hexdigest() != SHA256.get(relative):
                raise ValueError(f"{root / relative} is not jsonschema-specifications 2025.9.1's {relative}")
            return json.loads(data)

        top = load(f"{directory}/metaschema.json")
        documents = {"meta/" + relative.rsplit("/", 1)[1]: load(relative) for relative in sorted(SHA256)
                     if relative.startswith(directory + "/vocabularies/")}
        defs = {}
        schema = flat(top, documents, defs)
        if defs:
            key = "$defs" if name in ("2019", "2020") else "definitions"
            schema[key] = {**schema.get(key, {}), **{each: flat(value, documents, {}) for each, value in defs.items()}}
        result[name] = schema
    return result


def module(schemas):
    lines = [HEADER.rstrip("\n")]
    for name, schema in schemas.items():
        text = json.dumps(schema, separators=(",", ":"))
        if "'" in text or "\\" in text:
            raise ValueError("a metaschema needs another quoting")
        lines.append(f"    {name}: (")
        lines.extend(f"        '{text[at:at + 106]}'" for at in range(0, len(text), 106))
        lines.append("    ),")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv):
    text = module(flattened(Path(argv[1])))
    if "--check" in argv[2:]:
        if MODULE.read_text() != text:
            raise ValueError(f"{MODULE} is not what {Path(__file__).name} generates")
        print(f"{MODULE.name}: as generated")
    else:
        MODULE.write_text(text)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (ValueError, OSError) as error:
        sys.exit(f"metaschemas: {error}")
