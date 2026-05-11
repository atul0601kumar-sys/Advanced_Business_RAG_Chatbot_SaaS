from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any


class CSVBuilder:
    def build_text(self, rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: self._serialize_value(row.get(key)) for key in fieldnames})
        return buffer.getvalue()

    def build_bytes(self, rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
        return self.build_text(rows, fieldnames).encode("utf-8")

    def flatten_payload(self, payload: dict[str, Any]) -> str:
        flattened = self._flatten("", payload)
        rows = [{"field": key, "value": flattened[key]} for key in sorted(flattened)]
        return self.build_text(rows, ["field", "value"])

    def _flatten(self, prefix: str, value: Any) -> dict[str, str]:
        if isinstance(value, dict):
            flattened: dict[str, str] = {}
            for key, child in value.items():
                child_prefix = f"{prefix}.{key}" if prefix else key
                flattened.update(self._flatten(child_prefix, child))
            return flattened
        if isinstance(value, list):
            return {prefix: json.dumps(value, ensure_ascii=False, default=str)}
        return {prefix: self._serialize_value(value)}

    def _serialize_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return str(value)
