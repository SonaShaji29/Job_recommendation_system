from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
import hashlib
from datetime import datetime, date
from functools import wraps
import math

app = Flask(__name__)
app.secret_key = 'job_recommendation_secret_key_2024'
UPLOAD_FOLDER = 'static/resumes'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE = 'job_recommendation.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            phone VARCHAR(15),
            role VARCHAR(20) DEFAULT 'user',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            skills TEXT NOT NULL DEFAULT '',
            experience_years INTEGER DEFAULT 0,
            preferred_role VARCHAR(100),
            education VARCHAR(150),
            resume_path VARCHAR(255),
            bio TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS jobs (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title VARCHAR(150) NOT NULL,
            company_name VARCHAR(150) NOT NULL,
            location VARCHAR(100),
            required_skills TEXT NOT NULL,
            job_description TEXT NOT NULL,
            experience_required INTEGER DEFAULT 0,
            salary_range VARCHAR(50),
            job_type VARCHAR(50) DEFAULT 'Full-time',
            category VARCHAR(100),
            posted_by INTEGER,
            due_date DATE,
            posted_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) DEFAULT 'Active',
            FOREIGN KEY (posted_by) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            job_id INTEGER,
            cover_letter TEXT,
            applied_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            application_status VARCHAR(50) DEFAULT 'Applied',
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (job_id) REFERENCES jobs(job_id)
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            job_id INTEGER,
            match_score FLOAT,
            recommended_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (job_id) REFERENCES jobs(job_id)
        );
    ''')

    # Seed admin
    c.execute("SELECT * FROM users WHERE role='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (full_name, email, password, role) VALUES (?, ?, ?, ?)",
                  ('Admin', 'admin@jobportal.com', hash_password('admin123'), 'admin'))
    # Seed recruiter
    c.execute("SELECT * FROM users WHERE role='recruiter'")
    if not c.fetchone():
        c.execute("INSERT INTO users (full_name, email, password, role, phone) VALUES (?, ?, ?, ?, ?)",
                  ('Demo Recruiter', 'recruiter@jobportal.com', hash_password('recruiter123'), 'recruiter', '9876543210'))

    conn.commit()
    conn.close()

# --- Auth Decorators ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# --- Recommendation Engine ---
def calculate_match_score(user_skills, job_skills):
    if not user_skills or not job_skills:
        return 0.0
    user_set = set(s.strip().lower() for s in user_skills.split(',') if s.strip())
    job_set = set(s.strip().lower() for s in job_skills.split(',') if s.strip())
    if not job_set:
        return 0.0
    intersection = user_set & job_set
    score = len(intersection) / len(job_set) * 100
    return round(score, 2)

def generate_recommendations(user_id):
    conn = get_db()
    c = conn.cursor()
    profile = c.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
    if not profile:
        conn.close()
        return
    jobs = c.execute("SELECT * FROM jobs WHERE status='Active'").fetchall()
    c.execute("DELETE FROM recommendations WHERE user_id=?", (user_id,))
    for job in jobs:
        score = calculate_match_score(profile['skills'], job['required_skills'])
        if score > 0:
            c.execute("INSERT INTO recommendations (user_id, job_id, match_score) VALUES (?,?,?)",
                      (user_id, job['job_id'], score))
    conn.commit()
    conn.close()

# ==================== AUTH ====================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = hash_password(request.form['password'])
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['user_id']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['email'] = user['email']
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = hash_password(request.form['password'])
        phone = request.form.get('phone', '')
        role = request.form.get('role', 'user')
        if role not in ['user', 'recruiter']:
            role = 'user'
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (full_name, email, password, phone, role) VALUES (?,?,?,?,?)",
                         (full_name, email, password, phone, role))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists.', 'danger')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

# ==================== DASHBOARD ====================
@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    conn = get_db()
    if role == 'admin':
        stats = {
            'total_users': conn.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0],
            'total_recruiters': conn.execute("SELECT COUNT(*) FROM users WHERE role='recruiter'").fetchone()[0],
            'total_jobs': conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
            'active_jobs': conn.execute("SELECT COUNT(*) FROM jobs WHERE status='Active'").fetchone()[0],
            'total_applications': conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
        }
        recent_jobs = conn.execute("""
            SELECT j.*, u.full_name as recruiter_name FROM jobs j
            LEFT JOIN users u ON j.posted_by=u.user_id
            ORDER BY j.posted_date DESC LIMIT 5
        """).fetchall()
        recent_users = conn.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 5").fetchall()
        conn.close()
        return render_template('admin_dashboard.html', stats=stats, recent_jobs=recent_jobs, recent_users=recent_users)

    elif role == 'recruiter':
        user_id = session['user_id']
        stats = {
            'my_jobs': conn.execute("SELECT COUNT(*) FROM jobs WHERE posted_by=?", (user_id,)).fetchone()[0],
            'active_jobs': conn.execute("SELECT COUNT(*) FROM jobs WHERE posted_by=? AND status='Active'", (user_id,)).fetchone()[0],
            'total_applications': conn.execute("""
                SELECT COUNT(*) FROM applications a JOIN jobs j ON a.job_id=j.job_id WHERE j.posted_by=?
            """, (user_id,)).fetchone()[0],
        }
        my_jobs = conn.execute("""
            SELECT j.*, 
            (SELECT COUNT(*) FROM applications a WHERE a.job_id=j.job_id) as app_count
            FROM jobs j WHERE j.posted_by=? ORDER BY j.posted_date DESC LIMIT 5
        """, (user_id,)).fetchall()
        conn.close()
        return render_template('recruiter_dashboard.html', stats=stats, my_jobs=my_jobs)

    else:
        user_id = session['user_id']
        generate_recommendations(user_id)
        profile = conn.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
        recommendations = conn.execute("""
            SELECT r.match_score, j.* FROM recommendations r
            JOIN jobs j ON r.job_id=j.job_id
            WHERE r.user_id=? AND j.status='Active'
            ORDER BY r.match_score DESC LIMIT 6
        """, (user_id,)).fetchall()
        my_applications = conn.execute("""
            SELECT a.*, j.job_title, j.company_name FROM applications a
            JOIN jobs j ON a.job_id=j.job_id WHERE a.user_id=?
            ORDER BY a.applied_date DESC LIMIT 5
        """, (user_id,)).fetchall()
        total_apps = conn.execute("SELECT COUNT(*) FROM applications WHERE user_id=?", (user_id,)).fetchone()[0]
        conn.close()
        return render_template('user_dashboard.html', profile=profile,
                               recommendations=recommendations,
                               my_applications=my_applications,
                               total_apps=total_apps)

# ==================== JOBS ====================
@app.route('/jobs')
@login_required
def jobs():
    search = request.args.get('search', '')
    skill = request.args.get('skill', '')
    location = request.args.get('location', '')
    job_type = request.args.get('job_type', '')
    category = request.args.get('category', '')
    exp = request.args.get('experience', '')
    page = int(request.args.get('page', 1))
    per_page = 9

    conn = get_db()
    query = "SELECT j.*, u.full_name as recruiter_name FROM jobs j LEFT JOIN users u ON j.posted_by=u.user_id WHERE j.status='Active'"
    params = []

    if search:
        query += " AND (j.job_title LIKE ? OR j.company_name LIKE ? OR j.job_description LIKE ?)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    if skill:
        query += " AND j.required_skills LIKE ?"
        params.append(f'%{skill}%')
    if location:
        query += " AND j.location LIKE ?"
        params.append(f'%{location}%')
    if job_type:
        query += " AND j.job_type=?"
        params.append(job_type)
    if category:
        query += " AND j.category LIKE ?"
        params.append(f'%{category}%')
    if exp:
        query += " AND j.experience_required <= ?"
        params.append(int(exp))

    all_jobs = conn.execute(query + " ORDER BY j.posted_date DESC", params).fetchall()
    total = len(all_jobs)
    total_pages = math.ceil(total / per_page)
    jobs_list = all_jobs[(page-1)*per_page : page*per_page]

    # Get user's applications
    applied_ids = []
    if session.get('role') == 'user':
        apps = conn.execute("SELECT job_id FROM applications WHERE user_id=?", (session['user_id'],)).fetchall()
        applied_ids = [a['job_id'] for a in apps]

    categories = conn.execute("SELECT DISTINCT category FROM jobs WHERE category IS NOT NULL AND status='Active'").fetchall()
    conn.close()

    return render_template('jobs.html', jobs=jobs_list, total=total, page=page,
                           total_pages=total_pages, applied_ids=applied_ids,
                           categories=[c['category'] for c in categories],
                           search=search, skill=skill, location=location,
                           job_type=job_type, category=category, exp=exp)

@app.route('/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    conn = get_db()
    job = conn.execute("""
        SELECT j.*, u.full_name as recruiter_name, u.email as recruiter_email
        FROM jobs j LEFT JOIN users u ON j.posted_by=u.user_id WHERE j.job_id=?
    """, (job_id,)).fetchone()
    if not job:
        flash('Job not found.', 'danger')
        return redirect(url_for('jobs'))

    applied = False
    application = None
    match_score = 0
    if session.get('role') == 'user':
        application = conn.execute("SELECT * FROM applications WHERE user_id=? AND job_id=?",
                                   (session['user_id'], job_id)).fetchone()
        applied = application is not None
        profile = conn.execute("SELECT skills FROM user_profiles WHERE user_id=?", (session['user_id'],)).fetchone()
        if profile:
            match_score = calculate_match_score(profile['skills'], job['required_skills'])

    conn.close()
    return render_template('job_detail.html', job=job, applied=applied, application=application, match_score=match_score)

@app.route('/jobs/apply/<int:job_id>', methods=['GET', 'POST'])
@login_required
@role_required('user')
def apply_job(job_id):
    conn = get_db()
    existing = conn.execute("SELECT * FROM applications WHERE user_id=? AND job_id=?",
                            (session['user_id'], job_id)).fetchone()
    if existing:
        flash('You have already applied for this job.', 'warning')
        conn.close()
        return redirect(url_for('job_detail', job_id=job_id))

    job = conn.execute("SELECT * FROM jobs WHERE job_id=? AND status='Active'", (job_id,)).fetchone()
    if not job:
        flash('Job not available.', 'danger')
        conn.close()
        return redirect(url_for('jobs'))

    if request.method == 'POST':
        cover_letter = request.form.get('cover_letter', '')
        conn.execute("INSERT INTO applications (user_id, job_id, cover_letter) VALUES (?,?,?)",
                     (session['user_id'], job_id, cover_letter))
        conn.commit()
        conn.close()
        flash('Application submitted successfully!', 'success')
        return redirect(url_for('my_applications'))

    conn.close()
    return render_template('apply_job.html', job=job)

@app.route('/my-applications')
@login_required
@role_required('user')
def my_applications():
    conn = get_db()
    applications = conn.execute("""
        SELECT a.*, j.job_title, j.company_name, j.location, j.job_type, j.status as job_status
        FROM applications a JOIN jobs j ON a.job_id=j.job_id
        WHERE a.user_id=? ORDER BY a.applied_date DESC
    """, (session['user_id'],)).fetchall()
    conn.close()
    return render_template('my_applications.html', applications=applications)

# ==================== PROFILE ====================
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id=?", (session['user_id'],)).fetchone()
    profile_data = conn.execute("SELECT * FROM user_profiles WHERE user_id=?", (session['user_id'],)).fetchone()

    if request.method == 'POST':
        skills = request.form.get('skills', '')
        experience_years = int(request.form.get('experience_years', 0))
        preferred_role = request.form.get('preferred_role', '')
        education = request.form.get('education', '')
        bio = request.form.get('bio', '')
        phone = request.form.get('phone', '')

        conn.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, session['user_id']))

        resume_path = profile_data['resume_path'] if profile_data else ''
        if 'resume' in request.files and request.files['resume'].filename:
            resume = request.files['resume']
            filename = f"resume_{session['user_id']}_{resume.filename}"
            resume.save(os.path.join(UPLOAD_FOLDER, filename))
            resume_path = filename

        if profile_data:
            conn.execute("""
                UPDATE user_profiles SET skills=?, experience_years=?, preferred_role=?,
                education=?, bio=?, resume_path=?, updated_at=CURRENT_TIMESTAMP
                WHERE user_id=?
            """, (skills, experience_years, preferred_role, education, bio, resume_path, session['user_id']))
        else:
            conn.execute("""
                INSERT INTO user_profiles (user_id, skills, experience_years, preferred_role, education, bio, resume_path)
                VALUES (?,?,?,?,?,?,?)
            """, (session['user_id'], skills, experience_years, preferred_role, education, bio, resume_path))

        conn.commit()
        generate_recommendations(session['user_id'])
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    conn.close()
    return render_template('profile.html', user=user, profile=profile_data)

# ==================== RECRUITER ====================
@app.route('/recruiter/jobs')
@login_required
@role_required('recruiter', 'admin')
def recruiter_jobs():
    conn = get_db()
    if session['role'] == 'admin':
        jobs_list = conn.execute("""
            SELECT j.*, u.full_name as recruiter_name,
            (SELECT COUNT(*) FROM applications a WHERE a.job_id=j.job_id) as app_count
            FROM jobs j LEFT JOIN users u ON j.posted_by=u.user_id ORDER BY j.posted_date DESC
        """).fetchall()
    else:
        jobs_list = conn.execute("""
            SELECT j.*,
            (SELECT COUNT(*) FROM applications a WHERE a.job_id=j.job_id) as app_count
            FROM jobs j WHERE j.posted_by=? ORDER BY j.posted_date DESC
        """, (session['user_id'],)).fetchall()
    conn.close()
    return render_template('recruiter_jobs.html', jobs=jobs_list)

@app.route('/recruiter/jobs/new', methods=['GET', 'POST'])
@login_required
@role_required('recruiter', 'admin')
def new_job():
    if request.method == 'POST':
        conn = get_db()
        conn.execute("""
            INSERT INTO jobs (job_title, company_name, location, required_skills, job_description,
            experience_required, salary_range, job_type, category, posted_by, due_date, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            request.form['job_title'], request.form['company_name'], request.form['location'],
            request.form['required_skills'], request.form['job_description'],
            int(request.form.get('experience_required', 0)), request.form.get('salary_range', ''),
            request.form.get('job_type', 'Full-time'), request.form.get('category', ''),
            session['user_id'], request.form.get('due_date') or None,
            request.form.get('status', 'Active')
        ))
        conn.commit()
        conn.close()
        flash('Job posted successfully!', 'success')
        return redirect(url_for('recruiter_jobs'))
    return render_template('job_form.html', job=None, action='New')

@app.route('/recruiter/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('recruiter', 'admin')
def edit_job(job_id):
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if not job:
        conn.close()
        flash('Job not found.', 'danger')
        return redirect(url_for('recruiter_jobs'))

    if session['role'] != 'admin' and job['posted_by'] != session['user_id']:
        conn.close()
        flash('Access denied.', 'danger')
        return redirect(url_for('recruiter_jobs'))

    if request.method == 'POST':
        conn.execute("""
            UPDATE jobs SET job_title=?, company_name=?, location=?, required_skills=?,
            job_description=?, experience_required=?, salary_range=?, job_type=?,
            category=?, due_date=?, status=? WHERE job_id=?
        """, (
            request.form['job_title'], request.form['company_name'], request.form['location'],
            request.form['required_skills'], request.form['job_description'],
            int(request.form.get('experience_required', 0)), request.form.get('salary_range', ''),
            request.form.get('job_type', 'Full-time'), request.form.get('category', ''),
            request.form.get('due_date') or None, request.form.get('status', 'Active'), job_id
        ))
        conn.commit()
        conn.close()
        flash('Job updated successfully!', 'success')
        return redirect(url_for('recruiter_jobs'))

    conn.close()
    return render_template('job_form.html', job=job, action='Edit')

@app.route('/recruiter/jobs/<int:job_id>/delete', methods=['POST'])
@login_required
@role_required('recruiter', 'admin')
def delete_job(job_id):
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if job and (session['role'] == 'admin' or job['posted_by'] == session['user_id']):
        conn.execute("DELETE FROM applications WHERE job_id=?", (job_id,))
        conn.execute("DELETE FROM recommendations WHERE job_id=?", (job_id,))
        conn.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
        conn.commit()
        flash('Job deleted.', 'success')
    conn.close()
    return redirect(url_for('recruiter_jobs'))

@app.route('/recruiter/jobs/<int:job_id>/applications')
@login_required
@role_required('recruiter', 'admin')
def job_applications(job_id):
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if not job or (session['role'] != 'admin' and job['posted_by'] != session['user_id']):
        conn.close()
        flash('Access denied.', 'danger')
        return redirect(url_for('recruiter_jobs'))

    applications = conn.execute("""
        SELECT a.*, u.full_name, u.email, u.phone,
        up.skills, up.experience_years, up.education, up.preferred_role, up.resume_path
        FROM applications a
        JOIN users u ON a.user_id=u.user_id
        LEFT JOIN user_profiles up ON u.user_id=up.user_id
        WHERE a.job_id=? ORDER BY a.applied_date DESC
    """, (job_id,)).fetchall()
    conn.close()
    return render_template('job_applications.html', job=job, applications=applications)

@app.route('/recruiter/applications/<int:app_id>/status', methods=['POST'])
@login_required
@role_required('recruiter', 'admin')
def update_application_status(app_id):
    status = request.form['status']
    conn = get_db()
    conn.execute("UPDATE applications SET application_status=? WHERE application_id=?", (status, app_id))
    conn.commit()
    job_id = conn.execute("SELECT job_id FROM applications WHERE application_id=?", (app_id,)).fetchone()['job_id']
    conn.close()
    flash('Status updated.', 'success')
    return redirect(url_for('job_applications', job_id=job_id))

# ==================== ADMIN ====================
@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    conn = get_db()
    users = conn.execute("""
        SELECT u.*, 
        (SELECT COUNT(*) FROM applications WHERE user_id=u.user_id) as app_count,
        (SELECT COUNT(*) FROM jobs WHERE posted_by=u.user_id) as job_count
        FROM users u ORDER BY u.created_at DESC
    """).fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@role_required('admin')
def toggle_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    if user and user['role'] != 'admin':
        new_role = request.form.get('role', user['role'])
        conn.execute("UPDATE users SET role=? WHERE user_id=?", (new_role, user_id))
        conn.commit()
        flash(f'User role updated to {new_role}.', 'success')
    conn.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    if user and user['role'] != 'admin':
        conn.execute("DELETE FROM applications WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM recommendations WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM user_profiles WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        conn.commit()
        flash('User deleted.', 'success')
    conn.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/reports')
@login_required
@role_required('admin')
def admin_reports():
    conn = get_db()
    # Applications by status
    app_stats = conn.execute("""
        SELECT application_status, COUNT(*) as count FROM applications GROUP BY application_status
    """).fetchall()
    # Jobs by category
    job_cats = conn.execute("""
        SELECT category, COUNT(*) as count FROM jobs GROUP BY category ORDER BY count DESC
    """).fetchall()
    # Top recruiters
    top_recruiters = conn.execute("""
        SELECT u.full_name, COUNT(j.job_id) as job_count,
        SUM((SELECT COUNT(*) FROM applications a WHERE a.job_id=j.job_id)) as total_apps
        FROM users u JOIN jobs j ON u.user_id=j.posted_by WHERE u.role='recruiter'
        GROUP BY u.user_id ORDER BY job_count DESC LIMIT 5
    """).fetchall()
    # Monthly registrations
    monthly = conn.execute("""
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count
        FROM users WHERE role='user' GROUP BY month ORDER BY month DESC LIMIT 12
    """).fetchall()
    conn.close()
    return render_template('admin_reports.html', app_stats=app_stats, job_cats=job_cats,
                           top_recruiters=top_recruiters, monthly=monthly)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
