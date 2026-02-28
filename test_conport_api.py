#!/usr/bin/env python3
"""Test what the ConPort API is actually returning."""

import sqlite3
from pathlib import Path

db_path = Path("/home/pwp/srv/apps/model-proxy/context_portal/context.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Simulate the exact query the API uses (from conport.py line 588-593)
print("=" * 80)
print("SIMULATING API QUERY: /api/v1/conport/progress?limit=50")
print("=" * 80)

cursor = conn.execute("""
    SELECT id, timestamp, status, description, parent_id 
    FROM progress_entries 
    ORDER BY id DESC 
    LIMIT 50
""")

rows = cursor.fetchall()
print(f"\nTotal rows returned: {len(rows)}")
print(f"First 10 IDs (newest): {[r['id'] for r in rows[:10]]}")
print(f"Last 10 IDs (oldest in this batch): {[r['id'] for r in rows[-10:]]}")

print("\n" + "=" * 80)
print("FIRST 5 ENTRIES (what the UI should show at the top):")
print("=" * 80)
for i, row in enumerate(rows[:5], 1):
    desc = row["description"][:70] + "..." if len(row["description"]) > 70 else row["description"]
    print(f"{i}. ID={row['id']:3d} | {row['status']:12s} | {desc}")

print("\n" + "=" * 80)
print("CHECKING FOR LITELLM PHASES (IDs 94-100):")
print("=" * 80)

litellm_ids = [94, 95, 96, 97, 98, 99, 100]
found_ids = [r['id'] for r in rows]

for lid in litellm_ids:
    if lid in found_ids:
        idx = found_ids.index(lid)
        row = rows[idx]
        desc = row["description"][:70] + "..." if len(row["description"]) > 70 else row["description"]
        print(f"✅ ID {lid} FOUND at position {idx+1}: {desc}")
    else:
        print(f"❌ ID {lid} NOT in first 50 results")

# Check if there are entries AFTER id 100
cursor = conn.execute("SELECT MAX(id) as max_id FROM progress_entries")
max_id = cursor.fetchone()["max_id"]
print(f"\n📊 Highest ID in database: {max_id}")

if max_id > 100:
    print(f"\n⚠️  WARNING: There are {max_id - 100} entries NEWER than your LiteLLM phases!")
    print("   Your phases (94-100) are being pushed out of the default 50-entry limit.")
    
    cursor = conn.execute("""
        SELECT id, timestamp, description 
        FROM progress_entries 
        WHERE id > 100
        ORDER BY id DESC 
        LIMIT 10
    """)
    print("\n   Newer entries:")
    for row in cursor:
        desc = row["description"][:60] + "..." if len(row["description"]) > 60 else row["description"]
        print(f"     ID {row['id']:3d}: {desc}")

conn.close()
