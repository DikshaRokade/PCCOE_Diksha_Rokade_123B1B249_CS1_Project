"""Configuration loading. All tunables live in Model_Prompts_Config/config.yaml."""
import copy
import hashlib
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]  # project root (holds Code/, Input_Data/, ...)
DEFAULT_CONFIG = ROOT / "Model_Prompts_Config" / "config.yaml"


def _merge(base, over):
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path=None, overrides=None):
    p = Path(path or os.environ.get("HLD_CONFIG", DEFAULT_CONFIG))
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    _merge(cfg, copy.deepcopy(overrides or {}))
    data_dir = Path(os.environ.get("HLD_DATA_DIR", ROOT / cfg["paths"]["data_dir"]))
    cfg["paths"]["data_dir_abs"] = str(data_dir)
    cfg["paths"]["prompts_dir_abs"] = str(ROOT / cfg["paths"]["prompts_dir"])
    cfg["_config_path"] = str(p)
    return cfg


def config_hash(cfg):
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    clean["paths"] = {k: v for k, v in clean["paths"].items() if not k.endswith("_abs")}
    return hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()[:16]


def read_prompt(cfg, name):
    return (Path(cfg["paths"]["prompts_dir_abs"]) / name).read_text(encoding="utf-8")
