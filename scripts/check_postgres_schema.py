"""Validate private ledger DDL in the already installed embedded PostgreSQL engine."""

import argparse
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from aedrova_site.meeting_leases import LEASE_SCHEMA, RESERVE_LEASE
from aedrova_site.store import SCHEMA


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", required=True)
    parser.add_argument("--pglite", required=True, type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="aedrova-billing-schema-") as folder:
        path = Path(folder)
        reserve = RESERVE_LEASE
        for name, value in {'room': "'test-room'", 'user': "'test-user'",
                            'meeting': "'test-meeting'", 'token': "'fixture'",
                            'expires': '100', 'now': '50'}.items():
            reserve = reserve.replace(':' + name, value)
        (path / "schema.json").write_text(json.dumps(SCHEMA + LEASE_SCHEMA))
        (path / "reserve.json").write_text(json.dumps(reserve))
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
            "if (tables.rows[0].n!==12) throw new Error('Missing private tables');\n"
            "const reserve=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));\n"
            "if ((await db.query(reserve)).rows.length!==1) throw new Error('Reserve failed');\n"
            "if ((await db.query(reserve)).rows.length!==0) throw new Error('Duplicate allowed');\n"
            "await db.exec(\"UPDATE meeting_leases SET state='revoked',expires=60\");\n"
            "if ((await db.query(reserve)).rows.length!==0) throw new Error('Grace bypassed');\n"
            "await db.exec(\"UPDATE meeting_leases SET expires=0\");\n"
            "if ((await db.query(reserve)).rows.length!==1) throw new Error('Rejoin failed');\n"
            "console.log('PASS private PostgreSQL ledger/meeting schema and atomic lease SQL; "
            "networked concurrency remains a live acceptance gate');\n"
            "}finally{await db.close();}\n"
        )
        subprocess.run([args.node, str(runner), str(path / "schema.json"),
                        str(path / 'reserve.json')], check=True)


if __name__ == "__main__":
    main()
