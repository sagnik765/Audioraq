#!/usr/bin/env python3

import argparse
from typing import Iterable

def batched(items: Iterable[dict], size: int):
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def migrate_collection(source_db, target_db, name: str, batch_size: int):
    from pymongo import ReplaceOne

    source_collection = source_db[name]
    target_collection = target_db[name]

    operations = []
    migrated = 0

    for document in source_collection.find({}):
        operations.append(ReplaceOne({"_id": document["_id"]}, document, upsert=True))
        if len(operations) >= batch_size:
            target_collection.bulk_write(operations, ordered=False)
            migrated += len(operations)
            operations = []

    if operations:
        target_collection.bulk_write(operations, ordered=False)
        migrated += len(operations)

    return migrated


def main():
    parser = argparse.ArgumentParser(description="Copy a MongoDB database from one cluster to another.")
    parser.add_argument("--source-uri", required=True, help="Source MongoDB URI")
    parser.add_argument("--source-db", required=True, help="Source database name")
    parser.add_argument("--target-uri", required=True, help="Target MongoDB URI")
    parser.add_argument("--target-db", required=True, help="Target database name")
    parser.add_argument("--drop-target", action="store_true", help="Drop the target database before import")
    parser.add_argument("--batch-size", type=int, default=500, help="Bulk upsert batch size")
    args = parser.parse_args()

    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise SystemExit(
            "pymongo is required to run this migration. Install backend dependencies first, "
            "for example: pip install -r backend/requirements.prod.txt"
        ) from exc

    source_client = MongoClient(args.source_uri)
    target_client = MongoClient(args.target_uri)

    source_db = source_client[args.source_db]
    target_db = target_client[args.target_db]

    if args.drop_target:
        target_client.drop_database(args.target_db)
        target_db = target_client[args.target_db]

    collections = sorted(name for name in source_db.list_collection_names() if not name.startswith("system."))

    if not collections:
        print("No collections found in source database.")
        return

    print(f"Migrating {len(collections)} collections from {args.source_db} to {args.target_db}")

    for name in collections:
        migrated = migrate_collection(source_db, target_db, name, args.batch_size)
        print(f"- {name}: {migrated} documents")

    print("Migration complete.")


if __name__ == "__main__":
    main()
