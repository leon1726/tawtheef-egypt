@echo off
cd "E:\py projects\tawtheef-egypt"
set DATABASE_URL=postgresql://postgres:JqcOpKxTdbRItlBPTiOudArKxlnmtIpt@shinkansen.proxy.rlwy.net:19267/railway
python scrapper.py --pages 1 --enrich
echo Scrape complete. Check your site.
pause