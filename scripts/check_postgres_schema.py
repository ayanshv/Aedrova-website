"""Validate private ledger DDL in the already installed embedded PostgreSQL engine."""

import argparse
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from aedrova_site.store import SCHEMA


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", required=True)
    parser.add_argument("--pglite", required=True, type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="aedrova-billing-schema-") as folder:
        path = Path(folder)
        (path / "schema.json").write_text(json.dumps(SCHEMA))
        runner = path / "check.mjs"
        runner.write_text(
            "import {PGlite} from " + json.dumps(args.pglite.resolve().as_uri()) + ";\n"
            "import fs from 'node:fs';\nconst db=new PGlite();\ntry {\n"
            "await db.exec('CREATE SCHEMA aedrova_billing; "
            "REVOKE ALL ON SCHEMA aedrova_billing FROM PUBLIC; "
            "SET search_path TO aedrova_billing;');\n"
            "for (const sql of JSON.parse(fs.readFileSync(process.argv[2],'utf8'))) "
            "await db.exec(sql);\n"
            'const tables=await db.query("SELECT count(*)::int AS n '
            "FROM information_schema.tables "
            "WHERE table_schema='aedrova_billing'\");\n"
            "if (tables.rows[0].n!==10) throw new Error('Missing private tables');\n"
            "console.log('PASS private PostgreSQL ledger schema; "
            "networked concurrency remains a live acceptance gate');\n"
            "}finally{await db.close();}\n"
        )
        subprocess.run([args.node, str(runner), str(path / "schema.json")], check=True)


if __name__ == "__main__":
    main()
