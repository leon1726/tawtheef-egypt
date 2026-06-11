import os
import math
import sqlite3
import logging
from functools import wraps
from flask import Flask, render_template, request, redirect, g, session, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

logging.basicConfig(level=logging.DEBUG)

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

import json
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials

service_account_info = json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON'))
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred)

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is not set!")

TRANSLATIONS = {
    'en': {
        'home': 'Home',
        'find_jobs': 'Find Jobs',
        'career_advice': 'Career Advice',
        'categories': 'Categories',
        'search_placeholder': 'Search jobs...',
        'login': 'Login',
        'signup': 'Sign Up',
        'logout': 'Logout',
        'apply_now': 'Apply Now',
        'latest_jobs': 'Latest Openings',
        'featured_positions': 'Featured Positions',
        'top_compensation': 'Top Compensation',
        'browse_categories': 'Browse Categories',
        'footer_text': 'Data from Wuzzuf.net',
        'search': 'Search',
        'go': 'Go',
        'welcome_back': 'Welcome back',
        'sign_in_account': 'Sign in to your Tawtheef account',
        'email_address': 'Email address',
        'password': 'Password',
        'forgot_password': 'Forgot password?',
        'login_btn': 'Login →',
        'or_continue': 'or continue with',
        'continue_google': 'Continue with Google',
        'create_account': 'Create account',
        'join_thousands': 'Join thousands of job seekers in Egypt',
        'full_name': 'Full name',
        'signup_btn': 'Create Account →',
    },
    'ar': {
        'home': 'الرئيسية',
        'find_jobs': 'البحث عن وظائف',
        'career_advice': 'نصائح مهنية',
        'categories': 'التصنيفات',
        'search_placeholder': 'ابحث عن وظائف...',
        'login': 'دخول',
        'signup': 'تسجيل',
        'logout': 'خروج',
        'apply_now': 'تقدم الآن',
        'latest_jobs': 'أحدث الوظائف',
        'featured_positions': 'وظائف مميزة',
        'top_compensation': 'أعلى الرواتب',
        'browse_categories': 'تصفح التصنيفات',
        'footer_text': 'بيانات من Wuzzuf.net',
        'search': 'بحث',
        'go': 'بحث',
        'welcome_back': 'مرحباً بعودتك',
        'sign_in_account': 'سجل الدخول إلى حساب توظيف مصر',
        'email_address': 'البريد الإلكتروني',
        'password': 'كلمة المرور',
        'forgot_password': 'نسيت كلمة المرور؟',
        'login_btn': '← دخول',
        'or_continue': 'أو تابع باستخدام',
        'continue_google': 'تابع مع جوجل',
        'create_account': 'إنشاء حساب',
        'join_thousands': 'انضم إلى آلاف الباحثين عن عمل في مصر',
        'full_name': 'الاسم الكامل',
        'signup_btn': '← إنشاء حساب',
    }
}

app.config['WTF_CSRF_EXEMPT_LIST'] = ['/api/auth/session', '/api/auth/save-user', '/sitemap.xml', '/robots.txt']
limiter = Limiter(app=app, key_func=get_remote_address)
csrf = CSRFProtect(app)

# ── Security headers on every response ────────────────────────────────────────
@app.after_request
def security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# ── Inject globals into all templates ─────────────────────────────────────────
@app.context_processor
def inject_globals():
    lang = request.args.get('lang', 'en')
    if lang not in ('en', 'ar'):
        lang = 'en'
    return {
        'lang': lang,
        'is_ar': lang == 'ar',
        't': TRANSLATIONS[lang],
        'FIREBASE_API_KEY': os.environ.get('FIREBASE_API_KEY', ''),
        'FIREBASE_AUTH_DOMAIN': os.environ.get('FIREBASE_AUTH_DOMAIN', ''),
        'FIREBASE_PROJECT_ID': os.environ.get('FIREBASE_PROJECT_ID', ''),
        'FIREBASE_STORAGE_BUCKET': os.environ.get('FIREBASE_STORAGE_BUCKET', ''),
        'FIREBASE_MESSAGING_SENDER_ID': os.environ.get('FIREBASE_MESSAGING_SENDER_ID', ''),
        'FIREBASE_APP_ID': os.environ.get('FIREBASE_APP_ID', ''),
    }

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_SQLITE = DATABASE_URL is None
SQLITE_PATH = "jobs.db"


# ── DB helpers ─────────────────────────────────────────────────────────────────
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


def init_users_table():
    try:
        conn = get_db()
        cur = conn.cursor()
        if USE_SQLITE:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    picture TEXT,
                    created_at TEXT
                )
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    picture TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
        conn.commit()
    except Exception as e:
        print(f"init_users_table error: {e}")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route('/health')
def health():
    return "OK"


@app.route('/')
def index():
    try:
        category = request.args.get('category', '').strip()

        if category:
            latest = query("SELECT * FROM jobs WHERE category = %s ORDER BY scraped_at DESC LIMIT 20", [category])
            hot = query("SELECT * FROM jobs WHERE skills IS NOT NULL AND skills != '' AND category = %s ORDER BY LENGTH(skills) DESC LIMIT 10", [category])
            top_paying = query("SELECT * FROM jobs WHERE salary IS NOT NULL AND salary != 'Confidential' AND salary != '' AND salary != 'Not specified' AND LOWER(salary) NOT LIKE %s AND category = %s ORDER BY scraped_at DESC LIMIT 10", ['%kpi%', category])
            total_result = query_one("SELECT COUNT(*) as count FROM jobs WHERE category = %s", [category])
        else:
            latest = query("SELECT * FROM jobs ORDER BY scraped_at DESC LIMIT 20")
            hot = query("SELECT * FROM jobs WHERE skills IS NOT NULL AND skills != '' ORDER BY LENGTH(skills) DESC LIMIT 10")
            top_paying = query("SELECT * FROM jobs WHERE salary IS NOT NULL AND salary != 'Confidential' AND salary != '' AND salary != 'Not specified' AND LOWER(salary) NOT LIKE %s ORDER BY scraped_at DESC LIMIT 10", ['%kpi%'])
            total_result = query_one("SELECT COUNT(*) as count FROM jobs")

        overall_total_result = query_one("SELECT COUNT(*) as count FROM jobs")
        overall_total = overall_total_result['count'] if overall_total_result else 0
        categories = query("SELECT category, COUNT(*) as count FROM jobs GROUP BY category ORDER BY count DESC")
        total = total_result['count'] if total_result else 0
    except Exception as e:
        return f"Database error: {e}", 500

    return render_template('index.html', jobs=latest, hot_jobs=hot, top_paying=top_paying,
                           categories=categories, total=total, overall_total=overall_total,
                           selected_category=category)


@app.route('/search')
@limiter.limit("30 per minute")
def search():
    try:
        q = request.args.get('q', '').strip()
        category = request.args.get('category', '').strip()
        try:
            page = max(1, int(request.args.get('page', 1)))
        except (ValueError, TypeError):
            page = 1
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

    # Related jobs: same category, exclude current job
    related = query(
        "SELECT id, title, company, location, salary, experience, category FROM jobs WHERE category = %s AND id != %s ORDER BY scraped_at DESC LIMIT 6",
        (job['category'], job_id)
    )

    # If not enough, fill with same location
    if len(related) < 3:
        location_jobs = query(
            "SELECT id, title, company, location, salary, experience, category FROM jobs WHERE location ILIKE %s AND id != %s AND id NOT IN %s ORDER BY scraped_at DESC LIMIT 6",
            (f"%{job['location'].split(',')[0].strip()}%", job_id, tuple([j['id'] for j in related] + [0]))
        )
        related = (related + location_jobs)[:6]

    return render_template('job.html', job=job, related=related)


@app.route('/apply/<int:job_id>')
def apply(job_id):
    job = query_one("SELECT link FROM jobs WHERE id = %s", (job_id,))
    if job and job['link'] and job['link'].startswith('https://wuzzuf.net'):
        return redirect(job['link'])
    return "Not found", 404


@app.route('/career-advice')
def career_advice():
    return render_template('career-advice.html')


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/signup')
def signup_page():
    return render_template('signup.html')


@app.route('/api/auth/session', methods=['POST'])
@limiter.limit("10 per minute")
def api_set_session():
    data = request.get_json()
    if not data:
        return {'success': False, 'error': 'No data'}, 400
    try:
        decoded = firebase_auth.verify_id_token(data.get('idToken', ''))
    except Exception:
        return {'success': False, 'error': 'Invalid token'}, 401
    session['user'] = {
        'uid': decoded['uid'],
        'email': decoded.get('email', ''),
        'name': decoded.get('name', ''),
        'picture': decoded.get('picture', '')
    }
    return {'success': True}


@app.route('/api/auth/save-user', methods=['POST'])
@limiter.limit("10 per minute")
def save_user():
    data = request.get_json()
    if not data:
        return {'success': False, 'error': 'No data'}, 400
    uid = data.get('uid')
    email = data.get('email')
    name = data.get('name', '')
    picture = data.get('picture', '')
    if not uid or not email:
        return {'success': False, 'error': 'Missing uid or email'}, 400
    try:
        conn = get_db()
        cur = conn.cursor()
        if USE_SQLITE:
            cur.execute(
                "INSERT OR IGNORE INTO users (uid, email, name, picture, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
                [uid, email, name, picture]
            )
        else:
            cur.execute(
                "INSERT INTO users (uid, email, name, picture, created_at) VALUES (%s, %s, %s, %s, NOW()) ON CONFLICT (uid) DO UPDATE SET email=%s, name=%s, picture=%s",
                [uid, email, name, picture, email, name, picture]
            )
        conn.commit()
        cur.close()
        return {'success': True}
    except Exception as e:
        print(f"Save user error: {e}")
        return {'success': False, 'error': str(e)}, 500

LANDING_PAGES = {
    'elevator-jobs-egypt': {
        'title': 'Elevator Jobs in Egypt',
        'title_ar': 'وظائف مصاعد في مصر',
        'h1': 'Elevator Jobs in Egypt',
        'description': 'Browse the latest elevator engineer, technician, and sales jobs in Egypt. Find elevator installation, maintenance, and sales engineer positions at top companies across Cairo, Giza, and Alexandria.',
        'keywords': ['elevator', 'lift', 'escalator'],
        'category': None,
    },
    'electrical-maintenance-jobs-egypt': {
        'title': 'Electrical Maintenance Jobs in Egypt',
        'title_ar': 'وظائف صيانة كهربائية في مصر',
        'h1': 'Electrical Maintenance Jobs in Egypt',
        'description': 'Find electrical maintenance engineer and technician jobs in Egypt. Browse positions at factories, facilities, and construction companies across Cairo and beyond.',
        'keywords': ['electrical maintenance', 'electrical engineer', 'maintenance engineer'],
        'category': 'Engineering / Construction / Civil / Architecture',
    },
    'technical-office-jobs-egypt': {
        'title': 'Technical Office Engineer Jobs in Egypt',
        'title_ar': 'وظائف مهندس مكتب فني في مصر',
        'h1': 'Technical Office Engineer Jobs in Egypt',
        'description': 'Explore technical office engineer and manager jobs in Egypt. Find quantity surveying, BOQ, and site engineering roles at leading construction and contracting companies.',
        'keywords': ['technical office', 'technical office engineer', 'quantity survey'],
        'category': 'Engineering / Construction / Civil / Architecture',
    },
    'digital-marketing-jobs-egypt': {
        'title': 'Digital Marketing Jobs in Egypt',
        'title_ar': 'وظائف تسويق رقمي في مصر',
        'h1': 'Digital Marketing Jobs in Egypt',
        'description': 'Browse digital marketing specialist, manager, and executive jobs in Egypt. Find SEO, social media, content, and performance marketing roles at top Egyptian companies.',
        'keywords': ['digital marketing', 'social media', 'seo', 'content marketing'],
        'category': 'Marketing / PR / Advertising',
    },
    'it-software-jobs-egypt': {
        'title': 'IT & Software Developer Jobs in Egypt',
        'title_ar': 'وظائف تكنولوجيا المعلومات في مصر',
        'h1': 'IT & Software Jobs in Egypt',
        'description': 'Find software developer, web developer, and IT engineer jobs in Egypt. Browse backend, frontend, full stack, and mobile development positions at tech companies in Cairo.',
        'keywords': ['software', 'developer', 'programming', 'backend', 'frontend', 'flutter', 'react'],
        'category': 'IT / Software / Development',
    },
    'sales-jobs-egypt': {
        'title': 'Sales Jobs in Egypt',
        'title_ar': 'وظائف مبيعات في مصر',
        'h1': 'Sales Jobs in Egypt',
        'description': 'Browse sales representative, sales engineer, and account manager jobs in Egypt. Find B2B, retail, and outdoor sales positions at leading companies across Egypt.',
        'keywords': ['sales', 'sales engineer', 'account manager', 'sales representative'],
        'category': 'Sales / Retail',
    },
    'accounting-finance-jobs-egypt': {
        'title': 'Accounting & Finance Jobs in Egypt',
        'title_ar': 'وظائف محاسبة ومالية في مصر',
        'h1': 'Accounting & Finance Jobs in Egypt',
        'description': 'Find accountant, financial analyst, and CFO jobs in Egypt. Browse junior and senior accounting, auditing, and finance roles at top Egyptian companies.',
        'keywords': ['accountant', 'accounting', 'finance', 'financial analyst', 'audit'],
        'category': 'Accounting / Finance',
    },
    'customer-service-jobs-egypt': {
        'title': 'Customer Service Jobs in Egypt',
        'title_ar': 'وظائف خدمة عملاء في مصر',
        'h1': 'Customer Service Jobs in Egypt',
        'description': 'Browse call center, customer support, and customer service representative jobs in Egypt. Find remote and on-site roles at leading companies in Cairo and Giza.',
        'keywords': ['customer service', 'call center', 'customer support', 'chat support'],
        'category': 'Customer / Service',
    },
}


@app.route('/jobs/<slug>')
def category_landing(slug):
    page_data = LANDING_PAGES.get(slug)
    if not page_data:
        return "Page not found", 404

    try:
        where = "WHERE 1=1"
        params = []

        if page_data['category']:
            where += " AND category = %s"
            params.append(page_data['category'])

        keyword_conditions = []
        for kw in page_data['keywords']:
            keyword_conditions.append("(title ILIKE %s OR description ILIKE %s OR skills ILIKE %s)")
            params += [f'%{kw}%', f'%{kw}%', f'%{kw}%']

        if keyword_conditions:
            where += " AND (" + " OR ".join(keyword_conditions) + ")"

        jobs = query(f"SELECT * FROM jobs {where} ORDER BY scraped_at DESC LIMIT 30", params)
        total_result = query_one(f"SELECT COUNT(*) as count FROM jobs {where}", params)
        total = total_result['count'] if total_result else 0

    except Exception as e:
        return f"Error: {e}", 500

    return render_template('category_landing.html',
                           page=page_data,
                           slug=slug,
                           jobs=jobs,
                           total=total)

@app.route('/sitemap.xml')
@limiter.exempt
def sitemap():
    from flask import Response
    import datetime

    base_url = 'https://tawtheef-egypt.site'
    today = datetime.date.today().isoformat()

    urls = []

    # Static pages
    static_pages = [
        ('/', '1.0', 'daily'),
        ('/search', '0.8', 'daily'),
        ('/career-advice', '0.6', 'weekly'),
    ]
    for path, priority, freq in static_pages:
        urls.append(f"""  <url>
    <loc>{base_url}{path}</loc>
    <changefreq>{freq}</changefreq>
    <priority>{priority}</priority>
    <lastmod>{today}</lastmod>
  </url>""")

    # Landing pages
    for slug in LANDING_PAGES:
        urls.append(f"""  <url>
    <loc>{base_url}/jobs/{slug}</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
    <lastmod>{today}</lastmod>
  </url>""")

    # All job pages from DB
    try:
        jobs = query("SELECT id, scraped_at FROM jobs ORDER BY scraped_at DESC")
        for job in jobs:
            lastmod = str(job['scraped_at'])[:10] if job['scraped_at'] else today
            urls.append(f"""  <url>
    <loc>{base_url}/job/{job['id']}</loc>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
    <lastmod>{lastmod}</lastmod>
  </url>""")
    except Exception as e:
        pass

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '\n'.join(urls)
    xml += '\n</urlset>'

    return Response(xml, mimetype='application/xml')


# ── Startup ────────────────────────────────────────────────────────────────────
with app.app_context():
    init_users_table()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)