import os
import random
import time
import psycopg2
from playwright.sync_api import sync_playwright

DATABASE_URL = os.environ['DATABASE_URL']
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.5 Safari/605.1.15",
]

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute("SELECT id, link, company FROM jobs WHERE logo_url IS NULL OR logo_url = '' ORDER BY id")
jobs = cur.fetchall()
cur.close()
conn.close()

print(f"Found {len(jobs)} jobs without logos")

updated = 0
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=random.choice(USER_AGENTS))
    page = context.new_page()
    page.set_default_timeout(15000)

    for i, (job_id, link, company) in enumerate(jobs):
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000)
            
            logo_el = page.query_selector('img[src*="logo"], img[alt*="logo"], .company-logo img')
            logo_url = logo_el.get_attribute('src') if logo_el else None
            
            if logo_url:
                conn = psycopg2.connect(DATABASE_URL)
                c = conn.cursor()
                c.execute('UPDATE jobs SET logo_url=%s WHERE id=%s', (logo_url, job_id))
                conn.commit()
                c.close()
                conn.close()
                updated += 1
            
            if (i + 1) % 50 == 0:
                print(f"  [{i+1}/{len(jobs)}] {updated} logos found")
                context.close()
                context = browser.new_context(user_agent=random.choice(USER_AGENTS))
                page = context.new_page()
            
            time.sleep(random.uniform(0.5, 1.5))
        except:
            pass

    context.close()
    browser.close()

print(f"Done! {updated} logos scraped out of {len(jobs)} jobs")
