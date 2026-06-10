import sqlite3
import os
import psycopg2

# Get logos from local DB
local = sqlite3.connect('jobs.db')
local.row_factory = sqlite3.Row
logos = local.execute("SELECT id, logo_url FROM jobs WHERE logo_url IS NOT NULL AND logo_url != ''").fetchall()
local.close()
print(f'Found {len(logos)} logos in local DB')

# Push to Neon
pg = psycopg2.connect(os.environ['DATABASE_URL'])
c = pg.cursor()
for row in logos:
    c.execute('UPDATE jobs SET logo_url=%s WHERE id=%s', (row['logo_url'], row['id']))
pg.commit()
pg.close()
print(f'Updated {len(logos)} logos on Neon')