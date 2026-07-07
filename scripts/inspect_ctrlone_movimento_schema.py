"""Inspeciona o schema Oracle real de MOVIMENTO_BANCARIO no CtrlOne."""

from __future__ import annotations

import json
import sys
from pathlib import Path

RLOGIX = Path("/Users/marcos/Documents/rlogix")
sys.path.insert(0, str(RLOGIX))

from dotenv import load_dotenv

load_dotenv(RLOGIX / ".env")

from database.connection import get_conn


def main() -> int:
    query = """
        SELECT owner, table_name, column_name, data_type, data_length, nullable
        FROM all_tab_columns
        WHERE table_name IN ('MOVIMENTO_BANCARIO', 'CONTA_BANCARIA_EMPRESA', 'FATURAS')
        ORDER BY owner, table_name, column_id
    """
    with get_conn() as conn:
        current_user = conn.execute("SELECT USER AS username FROM dual").fetchone()["username"]
        rows = conn.execute(query).fetchall()

    print("=== CtrlOne - schema real Oracle ===")
    print(f"current_user={current_user}")
    output = {"current_user": current_user, "tables": {}}
    for row in rows:
        item = {key.lower(): row[key] for key in row.keys()}
        table = item["table_name"]
        output["tables"].setdefault(table, []).append(item)

    for table in ("CONTA_BANCARIA_EMPRESA", "FATURAS", "MOVIMENTO_BANCARIO"):
        cols = output["tables"].get(table, [])
        print(f"{table}: {len(cols)} colunas")
        for item in cols:
            print(json.dumps(item, ensure_ascii=False))

    path = Path("bancsynk/docs/ctrlone_movimento_bancario_schema.json")
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Schema salvo em {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
