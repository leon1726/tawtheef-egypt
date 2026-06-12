import argparse
import csv
import os
import random
import time
import schedule
import sqlite3
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from deep_translator import GoogleTranslator
import os

translator = GoogleTranslator(source="en", target="ar")

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_SQLITE = DATABASE_URL is None
SQLITE_PATH = "jobs.db"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

CATEGORIES = [
    "Accounting-Finance",
    "Engineering-Construction-Civil-Architecture",
    "Writing-Editorial",
    "IT-Software-Development",
    "Manufacturing-Production",
    "Project-Program-Management",
    "Media-Journalism-Publishing",
    "Administration",
    "Business-Development",
    "Hospitality-Hotels-Food-Services",
    "Legal",
    "Marketing-PR-Advertising",
    "Quality",
    "Sports-and-Leisure",
    "Banking",
    "Creative-Design-Art",
    "Human-Resources",
    "Logistics-Supply-Chain",
    "Medical-Healthcare",
    "Analyst-Research",
    "Fashion",
    "R-D-Science",
    "Customer-Service",
    "Installation-Maintenance-Repair",
    "Sales-Retail",
    "Pharmaceutical",
]


def get_db():
    if USE_SQLITE:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    else:
        return psycopg2.connect(DATABASE_URL)





def init_db():
    conn = get_db()
    c = conn.cursor()
    if USE_SQLITE:
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                title_ar TEXT,
                company TEXT,
                location TEXT,
                location_ar TEXT,
                link TEXT UNIQUE,
                category TEXT,
                posted_date TEXT,
                scraped_at TEXT,
                description TEXT,
                description_ar TEXT,
                skills TEXT,
                job_type TEXT,
                experience TEXT,
                career_level TEXT,
                education TEXT,
                salary TEXT,
                details_scraped INTEGER DEFAULT 0
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                title TEXT,
                title_ar TEXT,
                company TEXT,
                location TEXT,
                location_ar TEXT,
                link TEXT UNIQUE,
                category TEXT,
                posted_date TEXT,
                scraped_at TEXT,
                description TEXT,
                description_ar TEXT,
                skills TEXT,
                job_type TEXT,
                experience TEXT,
                career_level TEXT,
                education TEXT,
                salary TEXT,
                details_scraped INTEGER DEFAULT 0
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_category ON jobs(category)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_details_scraped ON jobs(details_scraped)")
    conn.commit()
    conn.close()
    print("[✓] Database initialized.")


class WuzzufCategoryScraper:
    def __init__(self, headless=True, proxy=None, user_agent=None):
        self.headless = headless
        self.proxy = proxy
        self.user_agent = user_agent or random.choice(USER_AGENTS)
        self.jobs = []
        self.seen_links = set()
        init_db()

    def scrape_all_categories(self, max_pages=None):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context_options = {"user_agent": self.user_agent}
            if self.proxy:
                context_options["proxy"] = {"server": self.proxy}
            context = browser.new_context(**context_options)
            page = context.new_page()
            page.set_default_timeout(30000)

            for cat_idx, category in enumerate(CATEGORIES):
                print(f"\n{'='*50}")
                print(f"[{cat_idx+1}/{len(CATEGORIES)}] Category: {category}")
                print(f"{'='*50}")

                display_name = category.replace("-", " / ")
                if category == "R-D-Science":
                    display_name = "R&D / Science"

                url = f"https://www.wuzzuf.net/a/{category}-Jobs-in-Egypt?start=0"
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    page.keyboard.press("Escape")
                    time.sleep(random.uniform(0.8, 1.5))
                except Exception as e:
                    print(f"    Failed to load: {e}")
                    continue

                total_jobs = 0
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)
                    showing_el = page.locator("li.css-18tzj4n").first
                    showing_el.wait_for(state="attached", timeout=8000)
                    text = showing_el.inner_text().strip()
                    print(f"    {text}")
                    total_jobs = int(text.split("of")[-1].strip().replace(",", ""))
                except Exception:
                    pass

                if total_jobs == 0:
                    try:
                        count_el = page.query_selector("span.css-kkk7bn")
                        if count_el:
                            count_text = count_el.inner_text().strip()
                            total_jobs = int(count_text.replace(",", "").split()[0])
                    except Exception:
                        pass

                total_pages = (total_jobs + 19) // 20 if total_jobs > 0 else 1
                if max_pages:
                    total_pages = min(total_pages, max_pages)

                print(f"    Total jobs: {total_jobs}, Pages: {total_pages}")
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(0.5)

                for page_num in range(total_pages):
                    if page_num > 0:
                        start_val = page_num * 20
                        url = f"https://www.wuzzuf.net/a/{category}-Jobs-in-Egypt?start={start_val}"
                        try:
                            page.goto(url, wait_until="domcontentloaded")
                            page.wait_for_timeout(2500)
                            time.sleep(random.uniform(0.8, 1.5))
                        except Exception as e:
                            print(f"    Failed page {page_num+1}: {e}")
                            continue

                    print(f"    Page {page_num+1}/{total_pages}")

                    cards = page.query_selector_all("div.css-ovk77c")
                    if not cards:
                        cards = page.query_selector_all("div.css-ghe2tq")

                    if not cards:
                        print("    No cards found.")
                        break

                    new_jobs = 0
                    for card in cards:
                        try:
                            job = self._parse_card(card, display_name)
                            if job:
                                self.jobs.append(job)
                                new_jobs += 1
                        except Exception:
                            continue

                    print(f"    New: {new_jobs} | Total: {len(self.jobs)}")

                self._save_to_db()
                time.sleep(random.uniform(6, 12))

            context.close()
            browser.close()

        return self.jobs

    def _parse_card(self, card, category_name):
        try:
            title = ""
            title_el = card.query_selector("h2 a") or card.query_selector("h2")
            if not title_el:
                title_el = card.query_selector("h3.css-zfogyn a.css-f2utrv")
            if title_el:
                title = title_el.inner_text().strip()

            company = ""
            company_el = (
                card.query_selector("a.css-ipsyv7") or
                card.query_selector("a.css-r5lqqx")
            )
            if company_el:
                company = company_el.inner_text().strip().rstrip(" -").strip()

            location = ""
            location_el = (
                card.query_selector("span.css-16x61xq") or
                card.query_selector("span.css-e9gnws")
            )
            if location_el:
                location = location_el.inner_text().strip().lstrip("- ").strip()

            link = ""
            link_el = (
                card.query_selector("a.css-o171kl") or
                card.query_selector("a.css-f2utrv")
            )
            if link_el:
                link = link_el.get_attribute("href")
                if link:
                    link = link.split("?")[0]
                    link = urljoin("https://www.wuzzuf.net", link)

            posted_date = ""
            date_el = (
                card.query_selector("div.css-eg55jf") or
                card.query_selector("span.css-156vnf7") or
                card.query_selector("span.css-1ot5gkr") or
                card.query_selector("div.css-1jldrig")
            )
            if date_el:
                posted_date = date_el.inner_text().strip()

            if not link or not title:
                return None

            if link in self.seen_links:
                return None

            self.seen_links.add(link)

            title_ar = ""
            location_ar = ""
            try:
                title_ar = translator.translate(title) if title else ""
            except Exception:
                pass
            try:
                location_ar = translator.translate(location) if location else ""
            except Exception:
                pass

            return {
                "title": title,
                "title_ar": title_ar,
                "company": company,
                "location": location,
                "location_ar": location_ar,
                "link": link,
                "category": category_name,
                "posted_date": posted_date,
                "scraped_at": datetime.now().isoformat(),
            }
        except Exception:
            return None

    def _save_to_db(self):
        conn = get_db()
        c = conn.cursor()
        saved = 0
        for job in self.jobs:
            try:
                if USE_SQLITE:
                    c.execute("""
                        INSERT OR IGNORE INTO jobs
                        (title, company, location, link, category, posted_date, scraped_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        job.get("title"), job.get("company"), job.get("location"),
                        job.get("link"), job.get("category"), job.get("posted_date"),
                        job.get("scraped_at"),
                    ))
                else:
                    c.execute("""
                        INSERT INTO jobs (title, title_ar, company, location, location_ar, link, category, posted_date, scraped_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (link) DO NOTHING
                    """, (
                        job.get("title"), job.get("title_ar"), job.get("company"),
                        job.get("location"), job.get("location_ar"),
                        job.get("link"), job.get("category"), job.get("posted_date"),
                        job.get("scraped_at"),
                    ))
                if c.rowcount > 0:
                    saved += 1
            except Exception:
                pass
        conn.commit()
        conn.close()
        self.jobs = []
        print(f"    [DB: {saved} new jobs saved]")

    def scrape_job_details(self, page, job_url):
        details = {}
        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=12000)
            page.wait_for_timeout(1500)
            
            # Scrape logo
            try:
                logo_el = page.query_selector('img[src*="logo"], img[alt*="logo"], .company-logo img, img.css-1d44yfr')
                if logo_el:
                    details["logo_url"] = logo_el.get_attribute('src')
            except Exception:
                pass

            labels = page.query_selector_all("span.css-720fa0")
            values = page.query_selector_all("span.css-2rozun")

            for label_el, value_el in zip(labels, values):
                label = label_el.inner_text().strip().lower()
                value = value_el.inner_text().strip()
                if "experience" in label:
                    details["experience"] = value
                elif "career" in label:
                    details["career_level"] = value
                elif "salary" in label:
                    details["salary"] = value
                elif "education" in label:
                    details["education"] = value
                elif "job type" in label or "employment" in label:
                    details["job_type"] = value

            skill_els = page.query_selector_all("span.css-1vi25m1")
            skills = [el.inner_text().strip() for el in skill_els if el.inner_text().strip()]
            details["skills"] = ", ".join(skills) if skills else ""

            req_header = page.query_selector("h2.css-19118j8")
            if req_header:
                desc_text = ""
                requirements_list = []

                desc_headers = page.query_selector_all("h2.css-19118j8")
                for header in desc_headers:
                    header_text = header.inner_text().strip()
                    content_parts = []
                    try:
                        sibling = header.query_selector("xpath=following-sibling::*[1]")
                        while sibling:
                            tag = sibling.evaluate("el => el.tagName")
                            if tag == "H2":
                                break
                            text = sibling.inner_text().strip()
                            if text:
                                content_parts.append(text)
                            sibling = sibling.query_selector("xpath=following-sibling::*[1]")
                    except Exception:
                        pass

                    if "job description" in header_text.lower():
                        desc_text = "\n".join(content_parts)
                    elif "job requirements" in header_text.lower():
                        requirements_list = content_parts

                if desc_text:
                    details["description"] = desc_text[:5000]
                elif requirements_list:
                    details["description"] = "\n".join(requirements_list)[:5000]
                else:
                    desc_el = (
                        page.query_selector("div.css-1o5p7h1") or
                        page.query_selector("div[class*='description']")
                    )
                    if desc_el:
                        details["description"] = desc_el.inner_text().strip()[:5000]

        except Exception as e:
            print(f"        Error: {e}")

        return details

    def scrape_general_search(self, max_pages=10):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(user_agent=self.user_agent)
            page = context.new_page()
            page.set_default_timeout(30000)

            for page_num in range(max_pages):
                start = page_num * 15
                url = f"https://www.wuzzuf.net/search/jobs/?a=spd&start={start}"
                print(f"    Page {page_num+1}: {url}")

                try:
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(2500)
                    time.sleep(random.uniform(0.8, 1.5))
                except Exception as e:
                    print(f"    Failed: {e}")
                    continue

                cards = page.query_selector_all("div.css-ghe2tq")
                if not cards:
                    cards = page.query_selector_all("div.css-ovk77c")

                if not cards:
                    print("    No cards, stopping.")
                    break

                new_jobs = 0
                for card in cards:
                    try:
                        job = self._parse_card(card, "General")
                        if job:
                            self.jobs.append(job)
                            new_jobs += 1
                    except Exception:
                        continue

                print(f"    New: {new_jobs} | Total: {len(self.jobs)}")
                time.sleep(random.uniform(1, 2))

            self._save_to_db()
            context.close()
            browser.close()
        return self.jobs

    def scrape_single_category(self, category, max_pages=None):
        old_categories = CATEGORIES.copy()
        CATEGORIES.clear()
        CATEGORIES.append(category)
        result = self.scrape_all_categories(max_pages)
        CATEGORIES.clear()
        CATEGORIES.extend(old_categories)
        return result


def enrich_jobs(max_jobs=None, delay=2):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, link FROM jobs WHERE details_scraped = 0 ORDER BY id DESC")
    jobs = c.fetchall()
    conn.close()

    if max_jobs:
        jobs = jobs[:max_jobs]

    total = len(jobs)
    if total == 0:
        print("[*] No jobs need enrichment.")
        return

    print(f"[*] Enriching {total} new jobs only...")

    scraper = WuzzufCategoryScraper(headless=True)
    enriched = 0
    failed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=random.choice(USER_AGENTS))
        page = context.new_page()
        page.set_default_timeout(12000)

        for i, row in enumerate(jobs):
            job_id = row[0]
            link = row[1]
            print(f"[{i+1}/{total}] {link}")

            try:
                details = scraper.scrape_job_details(page, link)
                if details.get("description"):
                    try:
                        details["description_ar"] = translator.translate(details["description"][:4500])
                    except Exception:
                        details["description_ar"] = ""
            except Exception as e:
                print(f"        Detail error: {e}")
                details = {}
                failed += 1
                try:
                    context.close()
                except Exception:
                    pass
                context = browser.new_context(user_agent=random.choice(USER_AGENTS))
                page = context.new_page()
                page.set_default_timeout(12000)

            if details:
                conn = get_db()
                c = conn.cursor()
                if USE_SQLITE:
                    c.execute("""
                        UPDATE jobs
                        SET description=?, skills=?, job_type=?, experience=?,
                            career_level=?, education=?, salary=?, logo_url=?,
                            details_scraped=1
                        WHERE id=?
                    """, (
                        details.get("description", ""), details.get("skills", ""),
                        details.get("job_type", ""), details.get("experience", ""),
                        details.get("career_level", ""), details.get("education", ""),
                        details.get("salary", ""), details.get("logo_url", ""), job_id,
                    ))
                else:
                    c.execute("""
                        UPDATE jobs
                        SET description=%s, description_ar=%s, skills=%s, job_type=%s,
                            experience=%s, career_level=%s, education=%s, salary=%s,
                            logo_url=%s, details_scraped=1
                        WHERE id=%s
                    """, (
                        details.get("description", ""), details.get("description_ar", ""),
                        details.get("skills", ""), details.get("job_type", ""),
                        details.get("experience", ""), details.get("career_level", ""),
                        details.get("education", ""), details.get("salary", ""),
                        details.get("logo_url", ""), job_id,
                    ))
                conn.commit()
                conn.close()
                enriched += 1
            else:
                failed += 1

            if (i + 1) % 50 == 0:
                print(f"    [Progress: {enriched}/{total} enriched, {failed} failed]")
                try:
                    context.close()
                except Exception:
                    pass
                context = browser.new_context(user_agent=random.choice(USER_AGENTS))
                page = context.new_page()
                page.set_default_timeout(12000)

            time.sleep(random.uniform(delay, delay + 1))

        context.close()
        browser.close()

    print(f"[✓] Enriched {enriched}/{total} jobs. Failed: {failed}")


def scheduled_scrape():
    print(f"\n{'='*50}")
    print(f"[*] Scheduled scrape: {datetime.now().isoformat()}")
    print(f"{'='*50}")

    scraper = WuzzufCategoryScraper(headless=True)
    scraper.scrape_all_categories(max_pages=1)

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM jobs WHERE details_scraped = 0")
    new_count = c.fetchone()[0]
    conn.close()

    print(f"[*] {new_count} new jobs to enrich...")

    if new_count > 0:
        enrich_jobs()
    else:
        print("[*] No new jobs to enrich. Skipping.")

    print(f"[✓] Scheduled run complete.")


def start_scheduler(interval_hours=6):
    print(f"[*] Auto-scraper started. Running every {interval_hours} hours.")
    scheduled_scrape()
    schedule.every(interval_hours).hours.do(scheduled_scrape)
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[*] Scheduler stopped.")


def migrate_from_sqlite(sqlite_path="jobs.db"):
    print(f"[*] Migrating from {sqlite_path}...")
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_conn.text_factory = lambda x: str(x, 'utf-8', 'ignore')
    jobs = sqlite_conn.execute("SELECT * FROM jobs").fetchall()
    sqlite_conn.close()
    print(f"[*] Found {len(jobs)} jobs to migrate...")
    pg_conn = psycopg2.connect(DATABASE_URL)
    c = pg_conn.cursor()
    migrated = 0
    for job in jobs:
        try:
            c.execute("""
                INSERT INTO jobs (title, company, location, link, category, posted_date,
                    scraped_at, description, skills, job_type, experience, career_level,
                    education, salary, details_scraped)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (link) DO NOTHING
            """, (
                job["title"], job["company"], job["location"], job["link"],
                job["category"], job["posted_date"], job["scraped_at"],
                job["description"], job["skills"], job["job_type"],
                job["experience"], job["career_level"], job["education"],
                job["salary"], job["details_scraped"]
            ))
            if c.rowcount > 0:
                migrated += 1
        except Exception as e:
            print(f"    Error: {e}")
    pg_conn.commit()
    pg_conn.close()
    print(f"[✓] Migrated {migrated}/{len(jobs)} jobs.")

def backfill_arabic():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, title, location, description FROM jobs WHERE title_ar IS NULL OR title_ar = ''")
    jobs = c.fetchall()
    conn.close()
    
    total = len(jobs)
    print(f"[*] Backfilling Arabic for {total} jobs...")
    
    updated = 0
    for i, row in enumerate(jobs):
        job_id, title, location, description = row[0], row[1], row[2], row[3]
        title_ar = ""
        location_ar = ""
        description_ar = ""
        try:
            title_ar = translator.translate(title) if title else ""
        except Exception:
            pass
        try:
            location_ar = translator.translate(location) if location else ""
        except Exception:
            pass
        try:
            description_ar = translator.translate(description[:4500]) if description else ""
        except Exception:
            pass
        
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            UPDATE jobs SET title_ar=%s, location_ar=%s, description_ar=%s
            WHERE id=%s
        """, (title_ar, location_ar, description_ar, job_id))
        conn.commit()
        conn.close()
        updated += 1
        
        if (i + 1) % 50 == 0:
            print(f"    [{i+1}/{total}] done...")
        time.sleep(0.3)
    
    print(f"[✓] Backfilled {updated} jobs.")


def export_csv():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM jobs")
    jobs = c.fetchall()
    conn.close()

    if not jobs:
        print("[!] No jobs to export.")
        return

    keys = ["title", "company", "location", "link", "category",
            "posted_date", "scraped_at", "skills", "job_type",
            "experience", "career_level", "education", "salary"]

    with open("jobs.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()
        writer.writerows([dict(j) for j in jobs])

    print(f"[+] Exported {len(jobs)} jobs to jobs.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wuzzuf Job Scraper")
    parser.add_argument("--init-db", action="store_true", help="Initialize database tables")
    parser.add_argument("--migrate", action="store_true", help="Migrate from SQLite to PostgreSQL")
    parser.add_argument("--sqlite-path", default="jobs.db", help="Path to SQLite DB for migration")
    parser.add_argument("--pages", type=int, default=None, help="Max pages per category")
    parser.add_argument("--category", help="Scrape a single category")
    parser.add_argument("--export-csv", action="store_true", help="Export DB to CSV")
    parser.add_argument("--headful", action="store_true", help="Show browser window")
    parser.add_argument("--proxy", help="Proxy server URL")
    parser.add_argument("--enrich", action="store_true", help="Enrich existing jobs with details")
    parser.add_argument("--enrich-max", type=int, default=None, help="Max jobs to enrich")
    parser.add_argument("--schedule", action="store_true", help="Run auto-scraper on schedule")
    parser.add_argument("--interval", type=int, default=6, help="Hours between scheduled runs")
    parser.add_argument("--backfill-arabic", action="store_true", help="Backfill Arabic translations for existing jobs")

    args = parser.parse_args()

    if args.init_db:
        init_db()
    elif args.migrate:
        init_db()
        migrate_from_sqlite(args.sqlite_path)
    elif args.backfill_arabic:
        backfill_arabic()
    elif args.schedule:
        start_scheduler(interval_hours=args.interval)    
    elif args.enrich:
        enrich_jobs(max_jobs=args.enrich_max)
    elif args.export_csv:
        export_csv()
    else:
        scraper = WuzzufCategoryScraper(
            headless=not args.headful,
            proxy=args.proxy,
        )
        if args.category:
            print(f"[*] Scraping category: {args.category}")
            jobs = scraper.scrape_single_category(args.category, max_pages=args.pages)
        else:
            print(f"[*] Scraping all {len(CATEGORIES)} categories")
            jobs = scraper.scrape_all_categories(max_pages=args.pages)

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT category, COUNT(*) FROM jobs GROUP BY category ORDER BY COUNT(*) DESC")
        print(f"\n{'='*50}")
        print("[✓] Database summary:")
        for row in c.fetchall():
            print(f"    {row[0]:<55} {row[1]} jobs")
        c.execute("SELECT COUNT(DISTINCT link) FROM jobs")
        print(f"\n[✓] Total unique jobs: {c.fetchone()[0]}")
        conn.close()




        # Ping Google to re-crawl sitemap after scrape
        try:
            import urllib.request
            sitemap_url = "https://tawtheef-egypt.site/sitemap.xml"
            ping_url = f"https://www.google.com/ping?sitemap={sitemap_url}"
            urllib.request.urlopen(ping_url, timeout=10)
            print("[✓] Google sitemap ping sent")
        except Exception as e:
            print(f"[!] Sitemap ping failed: {e}")