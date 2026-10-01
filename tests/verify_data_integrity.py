import os
import sqlite3
import json

paths = [
    r'D:\VisionClaw-main\data',
    r'C:\Users\Shara\AppData\Local\Programs\SG-CUBE\data'
]

for base in paths:
    print(f"=== INSPECTING DATA INTEGRITY AT: {base} ===")
    if not os.path.exists(base):
        print("  Directory does not exist!")
        continue
    for root, dirs, files in os.walk(base):
        for f in files:
            full = os.path.join(root, f)
            if not os.path.exists(full):
                continue
            if "tmp" in root.lower() or f.endswith("-shm") or f.endswith("-wal"):
                continue
            rel = os.path.relpath(full, base)
            size = os.path.getsize(full)
            if f.endswith('.db'):
                try:
                    conn = sqlite3.connect(full)
                    cur = conn.cursor()
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = [r[0] for r in cur.fetchall() if not r[0].startswith('sqlite_')]
                    counts = {}
                    for t in tables:
                        try:
                            cur.execute(f"SELECT count(*) FROM [{t}]")
                            counts[t] = cur.fetchone()[0]
                        except Exception as e:
                            counts[t] = str(e)
                    conn.close()
                    print(f"  [DB] {rel:35} size={size:8} bytes | tables={counts}")
                except Exception as ex:
                    print(f"  [DB ERR] {rel}: {ex}")
            elif f.endswith('.json'):
                try:
                    with open(full, 'r', encoding='utf-8') as jf:
                        data = json.load(jf)
                    print(f"  [JSON] {rel:33} size={size:8} bytes | keys={list(data.keys()) if isinstance(data, dict) else len(data)}")
                except Exception as ex:
                    print(f"  [JSON ERR] {rel}: {ex}")
            else:
                print(f"  [FILE] {rel:33} size={size:8} bytes")
