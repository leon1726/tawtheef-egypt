import sqlite3
import os
import psycopg2

# Get logos from local DB with links
local = sqlite3.connect('jobs.db')
local.row_factory = sqlite3.Row
logos = local.execute("SELECT link, logo_url FROM jobs WHERE logo_url IS NOT NULL AND logo_url != ''").fetchall()
local.close()
print(f'Found {len(logos)} logos in local DB')

# Push to Neon matching by link
pg = psycopg2.connect(os.environ['DATABASE_URL'])
c = pg.cursor()
updated = 0
for row in logos:
    c.execute('UPDATE jobs SET logo_url=%s WHERE link=%s', (row['logo_url'], row['link']))
    if c.rowcount > 0:
        updated += 1
pg.commit()
pg.close()
print(f'Updated {updated} logos on Neon')