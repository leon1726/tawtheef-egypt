import os
import sys

# Set Neon DB
os.environ['DATABASE_URL'] = "postgresql://neondb_owner:npg_t7oKaQpW2VPj@ep-super-dew-aq8hf1ps.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require"

print("=" * 50)
print("Step 1: Scrape new jobs")
print("=" * 50)
os.system("python scrapper.py --pages 3")

print("\n" + "=" * 50)
print("Step 2: Enrich new jobs with details + logos")
print("=" * 50)
os.system("python scrapper.py --enrich")

print("\n" + "=" * 50)
print("Step 3: Scrape remaining logos")
print("=" * 50)
os.system("python scrape_logos_only.py")

print("\n[✓] Daily scrape complete!")