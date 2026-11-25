"""The ConfigMap in k8s/ must match config/verdict.json (the file docker-compose mounts)."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ConfigSync(unittest.TestCase):
    def test_configmap_matches_config_file(self):
        import yaml  # dev dependency (requirements-dev.txt)
        cm = yaml.safe_load((ROOT / "k8s" / "verdict-configmap.yaml").read_text())
        self.assertEqual(json.loads(cm["data"]["verdict.json"]),
                         json.loads((ROOT / "config" / "verdict.json").read_text()))


if __name__ == "__main__":
    unittest.main()
