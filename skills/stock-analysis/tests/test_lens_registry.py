from __future__ import annotations

import importlib.util
import pathlib
import unittest


SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY_PATH = SKILL_ROOT / "scripts" / "lens_registry.py"
EXPECTED_LENSES = {
    "buffett",
    "munger",
    "graham",
    "klarman",
    "lynch",
    "o_neil",
    "wood",
    "dalio",
    "soros",
    "livermore",
    "minervini",
    "simons",
    "duan_yongping",
    "zhang_kun",
    "feng_liu",
}
REQUIRED_FIELDS = {
    "name",
    "chinese_name",
    "core_philosophy",
    "evidence_weight_adjustments",
    "key_questions",
    "red_flags",
    "valuation_preference",
    "risk_focus",
    "analysis_modules_to_emphasize",
    "output_rules",
    "committee_role",
    "committee_synthesis_rules",
}


def load_registry_module():
    spec = importlib.util.spec_from_file_location("stock_analysis_lens_registry", REGISTRY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LensRegistryTest(unittest.TestCase):
    def test_loads_all_structured_lens_files_without_young_stock_cli(self):
        registry = load_registry_module()

        definitions = registry.load_lens_definitions()

        self.assertEqual(set(definitions), EXPECTED_LENSES)
        for lens_id, definition in definitions.items():
            self.assertEqual(set(definition), REQUIRED_FIELDS)
            self.assertEqual(set(definition["evidence_weight_adjustments"]), {"m1", "m2", "m3", "m4", "m5", "m6"})
            self.assertTrue(definition["core_philosophy"])
            self.assertTrue(definition["key_questions"])
            self.assertTrue(definition["red_flags"])
            self.assertTrue(definition["analysis_modules_to_emphasize"])
            self.assertTrue(definition["output_rules"])
            self.assertTrue(definition["committee_role"])
            self.assertTrue(definition["committee_synthesis_rules"])
            self.assertIn(lens_id, registry.lens_ids())

    def test_default_committee_is_valid_complementary_subset(self):
        registry = load_registry_module()

        members = registry.get_default_committee_members()

        self.assertGreaterEqual(len(members), 4)
        self.assertLessEqual(len(members), 6)
        self.assertEqual(len(set(members)), len(members))
        self.assertLessEqual(set(members), EXPECTED_LENSES)
        self.assertLessEqual({"buffett", "munger", "duan_yongping", "zhang_kun"}, set(members))
        self.assertEqual(registry.get_lens_definition(" Buffett ")["chinese_name"], "巴菲特")


if __name__ == "__main__":
    unittest.main()
