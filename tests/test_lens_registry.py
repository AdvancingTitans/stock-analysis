from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_stock_analysis_skill_lens_registry_self_test():
    path = Path(__file__).resolve().parents[1] / "skills" / "stock-analysis" / "tests" / "test_lens_registry.py"
    subprocess.run([sys.executable, str(path)], check=True)
