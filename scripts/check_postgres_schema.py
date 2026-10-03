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
        for name, value in {
            "room": "'test-room'",
            "user": "'test-user'",
            "meeting": "'test-meeting'",
            "token": "'fixture'",
            "expires": "100",
            "now": "50",
        }.items():
            reserve = reserve.replace(":" + name, value)
        (path / "schema.json").write_text(json.dumps(SCHEMA + LEASE_SCHEMA))
        (path / "reserve.json").write_text(json.dumps(reserve))
        migration = Path(__file__).resolve().parents[1] / "sql" / "supabase-website.sql"
        (path / "migration.sql").write_text(migration.read_text())
        runner = path / "check.mjs"
        runner.write_text(
            "import {PGlite} from " + json.dumps(args.pglite.resolve().as_uri()) + ";\n"
            "import fs from 'node:fs';\nconst db=new PGlite();\ntry {\n"
            "await db.exec('CREATE ROLE anon; CREATE ROLE authenticated; "
            "CREATE ROLE service_role; CREATE TABLE public.chat_fixture (id int);');\n"
            "const migration=fs.readFileSync(process.argv[4],'utf8');\n"
            "await db.exec(migration); await db.exec(migration);\n"
            "await db.exec('SET ROLE aedrova_website; "
            "SET search_path TO aedrova_billing;');\n"
            "async function denied(sql) { try { await db.exec(sql); } "
            "catch(e) { if(e.code==='42501') return; throw e; } "
            "throw new Error('Unexpected permission: '+sql); }\n"
            "await denied('CREATE SCHEMA unwanted');\n"
            "await denied('SELECT * FROM public.chat_fixture');\n"
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
            'await db.exec("UPDATE meeting_leases SET expires=0");\n'
            "if ((await db.query(reserve)).rows.length!==1) throw new Error('Rejoin failed');\n"
            "await db.exec('RESET ROLE; SET ROLE anon');\n"
            "await denied('SELECT * FROM aedrova_billing.meeting_leases');\n"
            "await db.exec('RESET ROLE; SET ROLE authenticated');\n"
            "await denied('SELECT * FROM aedrova_billing.meeting_leases');\n"
            "await db.exec('RESET ROLE; SET ROLE service_role');\n"
            "await denied('SELECT * FROM aedrova_billing.meeting_leases');\n"
            "console.log('PASS private PostgreSQL ledger/meeting schema and atomic lease SQL; "
            "networked concurrency remains a live acceptance gate');\n"
            "}finally{await db.close();}\n"
        )
        subprocess.run(
            [
                args.node,
                str(runner),
                str(path / "schema.json"),
                str(path / "reserve.json"),
                str(path / "migration.sql"),
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
