# pystachy: dynamic-any
# Pystachy port: schema-guided repair needs the optional jsonschema package (and pydantic for
# schema models), which upstream imports only when a schema is used. This module stands in for
# upstream's schema_repair.py with the same interface, and behaves as upstream does where those
# packages are not installed: boolean schemas work, and a JSON Schema dict raises upstream's
# "jsonschema is required" error before any repair.
from typing import Any, Literal

from .utils.constants import MISSING_VALUE, JSONReturnType, MissingValueType

SchemaRepairMode = Literal["standard", "salvage"]
SUPPORTED_SCHEMA_REPAIR_MODES: tuple[SchemaRepairMode, ...] = ("standard", "salvage")
JSONSCHEMA_REQUIRED = "jsonschema is required when using schema-aware repair."


class SchemaDefinitionError(ValueError):
    """Raised when schema metadata is invalid or unsupported."""


def normalize_schema_repair_mode(mode: str | None) -> SchemaRepairMode:
    if mode is None:
        return "standard"
    if mode == "standard":
        return "standard"
    if mode == "salvage":
        return "salvage"
    expected = ", ".join(SUPPORTED_SCHEMA_REPAIR_MODES)
    raise ValueError(f"schema_repair_mode must be one of: {expected}.")


def load_schema_model(path: str) -> Any:
    if ":" not in path:
        raise ValueError("Schema model must be in the form 'module:ClassName'.")
    raise ValueError("pydantic is required when using schema models.")


def normalize_missing_values(value: object) -> JSONReturnType:
    if value is MISSING_VALUE or isinstance(value, MissingValueType):
        return ""
    if isinstance(value, dict):
        normalized: dict[str, JSONReturnType] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Object keys must be strings.")
            normalized[key] = normalize_missing_values(item)
        return normalized
    if isinstance(value, list):
        return [normalize_missing_values(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("Value is not JSON compatible.")


def schema_from_input(schema: Any) -> dict[str, Any] | bool:
    if isinstance(schema, dict):
        return schema
    if schema is True or schema is False:
        return schema
    raise ValueError("Schema must be a JSON Schema dict, boolean schema, or pydantic v2 model.")


class SchemaRepairer:
    def __init__(
        self,
        schema: dict[str, Any] | bool,
        log: list[Any] | None,
        schema_repair_mode: str = "standard",
    ) -> None:
        self.root_schema = schema
        self.log = log
        self.schema_repair_mode = normalize_schema_repair_mode(schema_repair_mode)

    def _log(self, text: str, path: str) -> None:
        if self.log is not None:
            self.log.append({"text": text, "context": path})

    def _get_root_validator(self) -> Any:
        raise ValueError(JSONSCHEMA_REQUIRED)

    def is_valid(self, value: JSONReturnType, schema: dict[str, Any] | bool) -> bool:
        schema = self.resolve_schema(schema)
        if schema is True:
            return True
        if schema is False:
            return False
        raise ValueError(JSONSCHEMA_REQUIRED)

    def validate(self, value: JSONReturnType, schema: dict[str, Any] | bool) -> None:
        schema = self.resolve_schema(schema)
        if schema is True:
            return
        if schema is False:
            raise ValueError("Schema does not allow any values.")
        raise ValueError(JSONSCHEMA_REQUIRED)

    def resolve_schema(self, schema: object | None) -> dict[str, Any] | bool:
        if schema is None:
            return True
        if isinstance(schema, bool):
            return schema
        if not isinstance(schema, dict):
            raise SchemaDefinitionError("Schema must be an object.")
        raise ValueError(JSONSCHEMA_REQUIRED)

    def is_object_schema(self, schema: dict[str, Any] | bool | None) -> bool:
        schema = self.resolve_schema(schema)
        return False

    def is_array_schema(self, schema: dict[str, Any] | bool | None) -> bool:
        schema = self.resolve_schema(schema)
        return False

    def repair_value(self, value: Any, schema: dict[str, Any] | bool | None, path: str) -> JSONReturnType:
        """Apply schema rules to a parsed value, including unions, coercions, and defaults."""
        schema = self.resolve_schema(schema)
        if schema is True:
            return normalize_missing_values(value)
        if schema is False:
            raise ValueError("Schema does not allow any values.")
        raise ValueError(JSONSCHEMA_REQUIRED)

    def _copy_json_value(self, value: Any, path: str, label: str) -> JSONReturnType:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._copy_json_value(item, f"{path}[{idx}]", label) for idx, item in enumerate(value)]
        if isinstance(value, dict):
            copied: dict[str, JSONReturnType] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError(f"{label.capitalize()} value at {path} contains a non-string key.")
                copied[key] = self._copy_json_value(item, f"{path}.{key}", label)
            return copied
        raise ValueError(f"{label.capitalize()} value at {path} is not JSON compatible.")
