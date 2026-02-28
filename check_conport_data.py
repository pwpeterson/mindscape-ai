#!/usr/bin/env python3
"""Diagnostic script to check ConPort database contents."""

import sqlite3
from pathlib import Path

# Use the model-proxy database path
db_path = Path("/home/pwp/srv/apps/model-proxy/context_portal/context.db")

if not db_path.exists():
    print(f"❌ Database not found at {db_path}")
    exit(1)

print(f"✅ Database found at {db_path}\n")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Check progress entries
cursor = conn.execute("SELECT COUNT(*) as count FROM progress_entries")
total = cursor.fetchone()["count"]
print(f"📊 Total progress entries: {total}")

# Check recent entries
cursor = conn.execute("""
    SELECT id, status, description, parent_id, timestamp 
    FROM progress_entries 
    ORDER BY id DESC 
    LIMIT 10
""")
print("\n📝 Last 10 progress entries:")
print("-" * 80)
for row in cursor:
    desc = row["description"][:60] + "..." if len(row["description"]) > 60 else row["description"]
    parent = str(row['parent_id']) if row['parent_id'] is not None else 'None'
    print(f"  ID: {row['id']:3d} | Status: {row['status']:12s} | Parent: {parent:4s} | {desc}")

# Check WBS metadata
cursor = conn.execute("""
    SELECT COUNT(*) as count 
    FROM custom_data 
    WHERE category = 'wbs_meta'
""")
wbs_count = cursor.fetchone()["count"]
print(f"\n🏗️  WBS metadata entries: {wbs_count}")

# Check status distribution
cursor = conn.execute("""
    SELECT status, COUNT(*) as count 
    FROM progress_entries 
    GROUP BY status 
    ORDER BY count DESC
""")
print("\n📈 Status distribution:")
for row in cursor:
    print(f"  {row['status']:15s}: {row['count']:3d}")

# Check for phases (entity_type = 'phase')
cursor = conn.execute("""
    SELECT COUNT(*) as count
    FROM custom_data cd
    WHERE cd.category = 'wbs_meta'
    AND json_extract(cd.value, '$.entity_type') = 'phase'
""")
phase_count = cursor.fetchone()["count"]
print(f"\n📋 Phase entries (entity_type='phase'): {phase_count}")

# List all phases
cursor = conn.execute("""
    SELECT cd.key, json_extract(cd.value, '$.title') as title,
           json_extract(cd.value, '$.entity_type') as entity_type
    FROM custom_data cd
    WHERE cd.category = 'wbs_meta'
    AND json_extract(cd.value, '$.entity_type') = 'phase'
    ORDER BY cd.id DESC
    LIMIT 10
""")
print("\n📋 Recent phases:")
print("-" * 80)
for row in cursor:
    key = row["key"]
    progress_id = key.split(":")[-1] if ":" in key else "?"
    print(f"  Progress ID: {progress_id:4s} | Title: {row['title']}")

conn.close()

print("\n" + "=" * 80)
print("✅ Diagnostic complete!")
print("\n🔍 TROUBLESHOOTING STEPS:")
print("  1. Hard refresh the browser (Ctrl+Shift+R or Cmd+Shift+R)")
print("  2. Check browser console for errors (F12)")
print("  3. Verify the API server is running and restart it if needed")
print("  4. Check if any filters are applied in the UI (status, parent_id)")
print("  5. Make sure you're viewing the correct app_id in the ConPort panel")
print("     - The UI should be using app_id='model-proxy' or similar")
print("     - Check the URL for ?app_id= parameter")
