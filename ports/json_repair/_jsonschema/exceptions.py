"""The exceptions of jsonschema.exceptions that json_repair names, and the one it lets through."""


class _Error(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ValidationError(_Error):
    """An instance was invalid under a provided schema."""


class SchemaError(_Error):
    """A schema was invalid under its corresponding metaschema."""


class Unresolvable(Exception):
    """A reference was unresolvable (referencing.exceptions.Unresolvable)."""


class PointerToNowhere(Unresolvable):
    """A JSON Pointer leads to a part of a document that does not exist."""


class _RefResolutionError(Exception):
    """A ref could not be resolved."""


class _WrappedReferencingError(_RefResolutionError):
    """A reference that does not resolve, or that this validator does not resolve."""


class UnknownType(Exception):
    """A validator was asked to validate an instance against an unknown type."""
