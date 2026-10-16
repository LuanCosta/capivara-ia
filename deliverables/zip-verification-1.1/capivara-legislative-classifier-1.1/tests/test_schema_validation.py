import json
import unittest
from pathlib import Path

from classifier import classify_record
from test_classifier import record
from validate_schema import SchemaValidationError, validate


ROOT = Path(__file__).parents[1]
SCHEMA_PATH = ROOT / "schema" / "capivara_classificacao_contrato.json"
if not SCHEMA_PATH.exists():
    SCHEMA_PATH = ROOT / "artifacts" / "capivara_classificacao_contrato.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class SchemaValidationTests(unittest.TestCase):
    def test_generated_record_matches_schema(self):
        validate(classify_record(record("Aprovado o Projeto de Lei nº 1.")), SCHEMA)

    def test_invalid_decision_role_is_rejected(self):
        output = classify_record(record("Aprovado o Projeto de Lei nº 1."))
        output["classification"]["decisionRole"] = "MADE_UP"
        with self.assertRaises(SchemaValidationError):
            validate(output, SCHEMA)


if __name__ == "__main__":
    unittest.main()
