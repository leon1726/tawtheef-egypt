import sqlite3
from urllib.parse import quote

BASE = 'https://tawtheef-egypt.site'
conn = sqlite3.connect('jobs.db')
c = conn.cursor()

lines = []
lines.append('<?xml version="1.0" encoding="UTF-8"?>')
lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
lines.append(f'  <url><loc>{BASE}/</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>')
lines.append(f'  <url><loc>{BASE}/search</loc><changefreq>hourly</changefreq><priority>0.9</priority></url>')

for row in c.execute('SELECT DISTINCT category FROM jobs'):
    cat = quote(row[0], safe='')
    lines.append(f'  <url><loc>{BASE}/search?category={cat}</loc><changefreq>daily</changefreq><priority>0.7</priority></url>')

for row in c.execute('SELECT id FROM jobs'):
    lines.append(f'  <url><loc>{BASE}/job/{row[0]}</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>')

lines.append('</urlset>')
conn.close()

xml = '\n'.join(lines)
with open('static/sitemap.xml', 'w', encoding='utf-8') as f:
    f.write(xml)
print('Done')