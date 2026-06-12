import requests
import os
import psycopg2
import time

DATABASE_URL = os.environ.get('DATABASE_URL')
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("SELECT id, link FROM jobs WHERE link IS NOT NULL AND link != ''")
jobs = cur.fetchall()
total = len(jobs)
print(f"[*] Checking {total} jobs...")

dead_count = 0
for i, (job_id, link) in enumerate(jobs, 1):
    try:
        r = requests.get(link, timeout=10, allow_redirects=True)
        if r.status_code == 404:
            cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
            dead_count += 1
            print(f"[{i}/{total}] Deleted #{job_id}: 404")
        else:
            print(f"[{i}/{total}] OK #{job_id}: {r.status_code}")
        time.sleep(0.3)
    except Exception as e:
        print(f"[{i}/{total}] Skip #{job_id}: {e}")
    
    # Commit every 50 jobs to avoid losing progress
    if i % 50 == 0:
        conn.commit()
        print(f"    [Saved: {dead_count} deleted so far]")

conn.commit()
cur.close()
conn.close()
print(f"\nDone! {dead_count} dead jobs removed.")