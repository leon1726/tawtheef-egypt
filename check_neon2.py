import os
import psycopg2

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("SELECT id, company, link FROM jobs WHERE company IN ('TECHNOSAT', 'Tahya Masr Holding', 'Ibn Sina Pharma') LIMIT 5")
rows = cur.fetchall()
for r in rows:
    print(f"Neon - ID:{r[0]}, Company:{r[1]}, Link:{r[2][:100]}")
cur.close()
conn.close()