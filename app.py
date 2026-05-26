import os
import math
import sqlite3
import logging
from flask import Flask, render_template, request, redirect, g


logging.basicConfig(level=logging.DEBUG)

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

app = Flask(__name__)



DATABASE_URL = os.environ.get("DATABASE_URL")
USE_SQLITE = DATABASE_URL is None
SQLITE_PATH = "jobs.db"


def get_db():
    if 'db' not in g:
        if USE_SQLITE:
            conn = sqlite3.connect(SQLITE_PATH)
            conn.row_factory = sqlite3.Row
        else:
            conn = psycopg2.connect(DATABASE_URL)
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()


def query(sql, params=None):
    conn = get_db()
    if USE_SQLITE:
        sql = sql.replace('%s', '?').replace('ILIKE', 'LIKE')
        cur = conn.cursor()
        cur.execute(sql, params or [])
        return [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
    else:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or [])
        return cur.fetchall()


def query_one(sql, params=None):
    conn = get_db()
    if USE_SQLITE:
        sql = sql.replace('%s', '?').replace('ILIKE', 'LIKE')
        cur = conn.cursor()
        cur.execute(sql, params or [])
        row = cur.fetchone()
        if row:
            return dict(zip([d[0] for d in cur.description], row))
        return None
    else:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or [])
        return cur.fetchone()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


@app.route('/health')
def health():
    return "OK"


@app.route('/')
def index():
    try:
        latest = query("SELECT * FROM jobs ORDER BY scraped_at DESC LIMIT 20")
        hot = query("SELECT * FROM jobs WHERE skills IS NOT NULL AND skills != '' ORDER BY LENGTH(skills) DESC LIMIT 10")
        top_paying = query("""
            SELECT * FROM jobs 
            WHERE salary IS NOT NULL 
            AND salary != 'Confidential' 
            AND salary != '' 
            AND salary != 'Not specified'
            AND LOWER(salary) NOT LIKE %s
            ORDER BY scraped_at DESC 
            LIMIT 10
        """, ['%kpi%'])
        categories = query("SELECT category, COUNT(*) as count FROM jobs GROUP BY category ORDER BY count DESC")
        total_result = query_one("SELECT COUNT(*) as count FROM jobs")
        total = total_result['count'] if total_result else 0
    except Exception as e:
        return f"Database error: {e}", 500

    return render_template('index.html', jobs=latest, hot_jobs=hot, top_paying=top_paying, categories=categories, total=total)


@app.route('/search')
def search():
    try:
        q = request.args.get('q', '').strip()
        category = request.args.get('category', '').strip()
        page = max(1, int(request.args.get('page', 1)))
        per_page = 20
        offset = (page - 1) * per_page

        where = "WHERE 1=1"
        params = []

        if q:
            where += " AND (title ILIKE %s OR company ILIKE %s OR skills ILIKE %s OR description ILIKE %s)"
            params += [f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%']
        if category:
            where += " AND category = %s"
            params.append(category)

        total_result = query_one(f"SELECT COUNT(*) as count FROM jobs {where}", params)
        total = total_result['count'] if total_result else 0
        jobs = query(f"SELECT * FROM jobs {where} ORDER BY scraped_at DESC LIMIT %s OFFSET %s", params + [per_page, offset])
        categories = query("SELECT category, COUNT(*) as count FROM jobs GROUP BY category ORDER BY count DESC")
        total_pages = math.ceil(total / per_page) if total > 0 else 1
    except Exception as e:
        return f"Search error: {e}", 500

    return render_template('search.html', jobs=jobs, q=q, category=category,
                           page=page, total=total, total_pages=total_pages,
                           categories=categories)


@app.route('/job/<int:job_id>')
def job_detail(job_id):
    job = query_one("SELECT * FROM jobs WHERE id = %s", (job_id,))
    if not job:
        return "Job not found", 404
    return render_template('job.html', job=job)


@app.route('/apply/<int:job_id>')
def apply(job_id):
    job = query_one("SELECT link FROM jobs WHERE id = %s", (job_id,))
    if job:
        return redirect(job['link'])
    return "Not found", 404


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/signup')
def signup_page():
    return render_template('signup.html')


@app.route('/api/auth/session', methods=['POST'])
def api_set_session():
    data = request.get_json()
    session['user'] = {
        'uid': data.get('uid'),
        'email': data.get('email'),
        'name': data.get('name', ''),
        'picture': data.get('picture', '')
    }
    return {'success': True}


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)