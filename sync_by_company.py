import sqlite3
import os
import psycopg2

local = sqlite3.connect('jobs.db')
local.row_factory = sqlite3.Row
logos = local.execute("SELECT company, logo_url FROM jobs WHERE logo_url IS NOT NULL AND logo_url != ''").fetchall()
local.close()

pg = psycopg2.connect(os.environ['DATABASE_URL'])
c = pg.cursor()
updated = 0
for row in logos:
    c.execute('UPDATE jobs SET logo_url=%s WHERE company=%s', (row['logo_url'], row['company']))
    count = c.rowcount
    updated += count
    print(f"  {row['company']}: {count} jobs updated")
pg.commit()
pg.close()
print(f'\nTotal: {updated} jobs updated')