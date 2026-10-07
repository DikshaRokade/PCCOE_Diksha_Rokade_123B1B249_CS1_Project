import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Code" / "src"))
sys.path.insert(0, str(ROOT / "Code" / "scripts"))
INPUT = ROOT / "Input_Data"


@pytest.fixture(scope="session")
def data_dir():
    d = tempfile.mkdtemp()
    os.environ["HLD_DATA_DIR"] = d
    return d


@pytest.fixture(scope="session")
def service(data_dir):
    from hldrag.config import load_config
    from hldrag.pipeline import HLDService
    cfg = load_config(overrides={"embedding": {"provider": "hash"}, "llm": {"provider": "extractive"}})
    s = HLDService(cfg, "pytest")
    for v in ("1.0", "1.1"):
        s.ingest(INPUT / f"BDC_HLD_v{v}.pdf")
    return s
