"""Validador offline do subconjunto de JSON Schema usado pelo contrato.

Evita uma dependência nova no protótipo. Se o contrato passar a usar uma
palavra-chave desconhecida, o validador falha explicitamente.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class SchemaValidationError(ValueError):
    pass


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> None:
    if "oneOf" in schema:
        matches = 0
        for option in schema["oneOf"]:
            try:
                validate(instance, option, path)
                matches += 1
            except SchemaValidationError:
                pass
        if matches != 1:
            raise SchemaValidationError(f"{path}: oneOf teve {matches} correspondências")
        return

    if "const" in schema and instance != schema["const"]:
        raise SchemaValidationError(f"{path}: valor diferente de const")
    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaValidationError(f"{path}: valor fora do enum: {instance!r}")

    allowed_types = schema.get("type")
    if allowed_types is not None:
        allowed_types = [allowed_types] if isinstance(allowed_types, str) else allowed_types
        if not any(_is_type(instance, item) for item in allowed_types):
            raise SchemaValidationError(f"{path}: tipo inválido")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in instance]
        if missing:
            raise SchemaValidationError(f"{path}: campos ausentes {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = set(instance) - set(properties)
            if extras:
                raise SchemaValidationError(f"{path}: campos extras {sorted(extras)}")
        for key, value in instance.items():
            if key in properties:
                validate(value, properties[key], f"{path}.{key}")

    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            raise SchemaValidationError(f"{path}: poucos itens")
        if schema.get("uniqueItems") and len({json.dumps(i, sort_keys=True) for i in instance}) != len(instance):
            raise SchemaValidationError(f"{path}: itens duplicados")
        if "items" in schema:
            for index, value in enumerate(instance):
                validate(value, schema["items"], f"{path}[{index}]")

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            raise SchemaValidationError(f"{path}: string curta")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            raise SchemaValidationError(f"{path}: pattern inválido")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(instance.replace("Z", "+00:00"))
            except ValueError as error:
                raise SchemaValidationError(f"{path}: date-time inválido") from error
        if schema.get("format") == "uri":
            parsed = urlparse(instance)
            if not parsed.scheme or not parsed.netloc:
                raise SchemaValidationError(f"{path}: URI inválida")


def _is_type(value: Any, expected: str) -> bool:
    return {
        "null": value is None,
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
    }.get(expected, False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("schema", type=Path)
    parser.add_argument("document", type=Path)
    args = parser.parse_args()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    document = json.loads(args.document.read_text(encoding="utf-8"))
    records = document.get("records", [document])
    for index, record in enumerate(records):
        validate(record, schema, f"$.records[{index}]")
    print(f"OK: {len(records)} registro(s) válidos contra {args.schema.name}")


if __name__ == "__main__":
    main()
