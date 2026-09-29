#!/bin/sh
set -e

python3 -c "
import sqlite3

conn = sqlite3.connect('/var/lib/sparrow_cam/index.db')
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('''
    CREATE TABLE IF NOT EXISTS recordings (
        date TEXT NOT NULL,
        stream TEXT NOT NULL,
        detections TEXT,
        manual_annotations TEXT,
        birds TEXT,
        PRIMARY KEY (date, stream)
    )
''')
conn.execute('CREATE INDEX IF NOT EXISTS idx_recordings_date ON recordings(date)')
conn.commit()
conn.close()
"

exec "$@"
