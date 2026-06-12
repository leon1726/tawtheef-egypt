import os
import psycopg2

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute("SELECT id, company, logo_url FROM jobs WHERE logo_url IS NOT NULL AND logo_url != '' LIMIT 5")
rows = cur.fetchall()
print(f"Found {len(rows)} jobs with logos:")
for r in rows:
    print(f"  ID: {r[0]}, Company: {r[1]}")
    print(f"  URL: https://tawtheef-egypt.site/job/{r[0]}")
    print(f"  Logo: {r[2][:80]}")
    print()
cur.close()
conn.close()