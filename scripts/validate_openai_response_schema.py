#!/usr/bin/env python3
from __future__ import annotations

from gradeai.services.ai_client import (
    GradingResponse,
    PointDetectionResponse,
    QuestionDetectionResponse,
    _make_schema_strict,
)


def _iter_object_schemas(schema: object) -> list[dict]:
    found: list[dict] = []
    if isinstance(schema, dict):
        if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
            found.append(schema)
        for value in schema.values():
            found.extend(_iter_object_schemas(value))
    elif isinstance(schema, list):
        for item in schema:
            found.extend(_iter_object_schemas(item))
    return found


def _validate_required_lists(schema: dict) -> None:
    errors: list[str] = []
    for obj in _iter_object_schemas(schema):
        props = obj.get("properties") or {}
        required = obj.get("required")
        if not isinstance(required, list):
            errors.append(f"missing/invalid required (props={sorted(props.keys())})")
            continue
        missing = sorted(set(props.keys()) - set(required))
        if missing:
            errors.append(f"required missing keys: {missing}")
    if errors:
        raise SystemExit("Schema validation failed:\n- " + "\n- ".join(errors))


def main() -> None:
    schemas = {
        "grading_response": GradingResponse.model_json_schema(),
        "question_detection_response": QuestionDetectionResponse.model_json_schema(),
        "point_detection_response": PointDetectionResponse.model_json_schema(),
    }

    for name, schema in schemas.items():
        strict_schema = _make_schema_strict(schema)
        _validate_required_lists(strict_schema)
        print(f"OK: {name}")


if __name__ == "__main__":
    main()

