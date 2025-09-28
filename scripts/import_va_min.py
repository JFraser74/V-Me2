#!/usr/bin/env python3
"""
scripts/import_va_min.py

Simple, idempotent importer from a legacy Postgres (VA-min) into V-Me2 (Supabase).

Usage examples:

  # dry-run first, reading DSN from env
  VA_MIN_DSN="postgres://..." python scripts/import_va_min.py --source-table messages --target-table va_messages --key-columns message_id --limit 1000 --dry-run

  # store DSN encrypted in va_settings (requires Supabase configured and APP_ENCRYPTION_KEY set locally)
  VA_MIN_DSN="postgres://..." python scripts/import_va_min.py --store-config

Notes:
 - Requires a Postgres client library: `pip install psycopg[binary]` or `pip install psycopg2-binary`.
 - Requires Supabase server credentials available to this app (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SERVICE_KEY).
 - The script prefers using the DSN from the environment variable VA_MIN_DSN, or from the repo settings (settings_get('VA_MIN_DSN')).
 - The script uses the repo's Supabase client to upsert rows into the target table. If the underlying supabase client lacks upsert, it falls back to delete+insert per-row.
"""
import argparse
import os
import sys
import json
from typing import List, Dict, Any

try:
    import psycopg
except Exception:
    try:
        import psycopg2 as psycopg
    except Exception:
        psycopg = None

from vme_lib import supabase_client as _sbmod
from vme_lib.supabase_client import settings_get, settings_put


def get_source_dsn(provided: str | None) -> str | None:
    if provided:
        return provided
    env = os.getenv('VA_MIN_DSN')
    if env:
        return env
    # try settings (encrypted)
    try:
        v = settings_get('VA_MIN_DSN', default=None, decrypt=True)
        if v:
            return v
    except Exception:
        pass
    return None


def connect_source(dsn: str):
    if psycopg is None:
        raise RuntimeError('psycopg not installed. pip install psycopg[binary] or psycopg2-binary')
    # support both psycopg>=3 and psycopg2
    try:
        # psycopg3 style
        conn = psycopg.connect(dsn)
        return conn
    except Exception:
        try:
            conn = psycopg.connect(dsn)
            return conn
        except Exception as e:
            raise


def fetch_batch(conn, table: str, limit: int, offset: int):
    cur = conn.cursor()
    sql = f"SELECT * FROM {table} ORDER BY 1 LIMIT %s OFFSET %s"
    cur.execute(sql, (limit, offset))
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    results = [dict(zip(cols, r)) for r in rows]
    cur.close()
    return results


def upsert_to_supabase(sb, target_table: str, rows: List[Dict[str, Any]], key_columns: List[str], dry_run: bool):
    if not rows:
        return {'inserted': 0, 'updated': 0, 'skipped': 0}
    inserted = 0
    updated = 0
    skipped = 0
    try:
        if dry_run:
            return {'inserted': len(rows), 'updated': 0, 'skipped': 0}
        # attempt bulk upsert (preferred)
        try:
            res = sb.table(target_table).upsert(rows).execute()
            # best-effort: assume rows were inserted/updated
            inserted = len(rows)
            return {'inserted': inserted, 'updated': updated, 'skipped': skipped}
        except AttributeError:
            # older client: fall back to delete+insert per-row
            for r in rows:
                where = {k: r.get(k) for k in key_columns}
                try:
                    sb.table(target_table).delete().match(where).execute()
                except Exception:
                    pass
                sb.table(target_table).insert(r).execute()
                inserted += 1
            return {'inserted': inserted, 'updated': updated, 'skipped': skipped}
    except Exception as e:
        print('Supabase upsert failed:', e)
        return {'inserted': 0, 'updated': 0, 'skipped': len(rows)}


def main(argv: List[str]):
    p = argparse.ArgumentParser()
    p.add_argument('--source-dsn', help='Legacy VA-min Postgres DSN (overrides env/settings)')
    p.add_argument('--source-table', required=True)
    p.add_argument('--target-table', required=True)
    p.add_argument('--key-columns', required=True, help='comma-separated list of key columns to dedupe on')
    p.add_argument('--limit', type=int, default=1000, help='maximum rows to process (0 for all)')
    p.add_argument('--batch-size', type=int, default=500)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--store-config', action='store_true', help='store provided DSN into va_settings (encrypted)')
    args = p.parse_args(argv)

    dsn = get_source_dsn(args.source_dsn)
    if not dsn:
        print('ERROR: source DSN not provided. Set VA_MIN_DSN env var or use --source-dsn or store in settings as VA_MIN_DSN')
        sys.exit(2)

    # option to store DSN encrypted in settings
    if args.store_config:
        if args.dry_run:
            print('dry-run: would store DSN to settings')
        else:
            settings_put({'VA_MIN_DSN': dsn})
            print('stored VA_MIN_DSN into va_settings (encrypted if APP_ENCRYPTION_KEY is set)')
        return

    # connect to source
    conn = connect_source(dsn)

    sb = _sbmod._client()
    if not sb:
        print('ERROR: Supabase client not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY/SUPABASE_SERVICE_KEY')
        sys.exit(2)

    key_cols = [k.strip() for k in args.key_columns.split(',') if k.strip()]
    processed = 0
    totals = {'inserted': 0, 'updated': 0, 'skipped': 0}

    offset = 0
    batch = args.batch_size
    limit = args.limit
    while True:
        if limit and processed >= limit:
            break
        to_fetch = batch if (not limit or processed + batch <= limit) else (limit - processed)
        rows = fetch_batch(conn, args.source_table, to_fetch, offset)
        if not rows:
            break
        # sanitize rows: JSON serializable conversions if needed
        for r in rows:
            for k, v in list(r.items()):
                # psycopg may return bytes for some fields; convert
                if isinstance(v, (bytes, bytearray)):
                    try:
                        r[k] = v.decode('utf-8')
                    except Exception:
                        r[k] = None
        res = upsert_to_supabase(sb, args.target_table, rows, key_cols, args.dry_run)
        totals['inserted'] += res.get('inserted', 0)
        totals['updated'] += res.get('updated', 0)
        totals['skipped'] += res.get('skipped', 0)
        processed += len(rows)
        offset += len(rows)
        print(f"processed {processed} rows (inserted {totals['inserted']})")
        if limit and processed >= limit:
            break

    print('done; summary:', totals)


if __name__ == '__main__':
    main(sys.argv[1:])
