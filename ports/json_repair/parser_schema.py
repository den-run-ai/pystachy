# pystachy: dynamic-any
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .schema_repair import SchemaRepairer


@dataclass(frozen=True)
class ObjectSchemaConfig:
    properties: dict[str, Any]
    pattern_properties: dict[str, Any]
    additional_properties: object | None
    required: set[str]


@dataclass(frozen=True)
class ArraySchemaConfig:
    items_schema: object | None
    additional_items: object | None


def resolve_parser_object_schema(
    repairer: SchemaRepairer | None,
    schema: dict[str, Any] | bool | None,
) -> tuple[SchemaRepairer | None, dict[str, Any] | bool | None, ObjectSchemaConfig | None]:
    if repairer is None or schema in (None, True):
        return None, schema, None

    schema = repairer.resolve_schema(schema)
    if schema is False:
        raise ValueError("Schema does not allow any values.")
    if schema is True or not repairer.is_object_schema(schema):
        return None, schema, None
    return repairer, schema, object_schema_config(schema)


def resolve_parser_array_schema(
    repairer: SchemaRepairer | None,
    schema: dict[str, Any] | bool | None,
) -> tuple[SchemaRepairer | None, dict[str, Any] | bool | None, ArraySchemaConfig | None]:
    if repairer is None or schema in (None, True):
        return None, schema, None

    schema = repairer.resolve_schema(schema)
    if schema is False:
        raise ValueError("Schema does not allow any values.")
    if schema is True or not repairer.is_array_schema(schema):
        return None, schema, None
    return repairer, schema, array_schema_config(schema)


def object_schema_config(schema: dict[str, Any]) -> ObjectSchemaConfig:
    # Pystachy port: not reached; a JSON Schema dict raises before parsing (schema_repair.py).
    raise ValueError("jsonschema is required when using schema-aware repair.")


def array_schema_config(schema: dict[str, Any]) -> ArraySchemaConfig:
    # Pystachy port: not reached; a JSON Schema dict raises before parsing (schema_repair.py).
    raise ValueError("jsonschema is required when using schema-aware repair.")
