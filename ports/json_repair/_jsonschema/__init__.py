"""JSON Schema validation for schema-guided repair.

Pystachy port: upstream validates with the optional jsonschema package, which no native program
can import. This package stands in for the part of it that json_repair calls
(jsonschema.validators.validator_for(), a validator's check_schema(), evolve(), is_valid() and
validate(), and the two exceptions it catches), with jsonschema 4.26's keywords, evaluation
order and messages. PORT.md lists what it leaves out.
"""
from . import exceptions, validators

__all__ = ["exceptions", "validators"]
