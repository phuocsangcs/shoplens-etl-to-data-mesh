"""Tiện ích dùng chung của platform: đọc contract của các domain, mở warehouse của domain."""
from pathlib import Path

import duckdb
import yaml

MESH_DIR = Path(__file__).resolve().parent.parent
ROOT = MESH_DIR.parent
DOMAINS_DIR = MESH_DIR / "domains"


def load_policies() -> dict:
    return yaml.safe_load((MESH_DIR / "platform" / "policies.yml").read_text(encoding="utf-8"))


def load_contracts() -> dict[str, dict]:
    """{domain: data_product.yml đã parse}. Domain = thư mục con trong domains/ có data_product.yml."""
    contracts = {}
    for f in sorted(DOMAINS_DIR.glob("*/data_product.yml")):
        contracts[f.parent.name] = yaml.safe_load(f.read_text(encoding="utf-8"))
    return contracts


def open_output_port(contract: dict) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(ROOT / contract["output_port"]["warehouse"]), read_only=True)


def split_table(contract: dict) -> tuple[str, str]:
    schema, table = contract["output_port"]["table"].split(".")
    return schema, table
