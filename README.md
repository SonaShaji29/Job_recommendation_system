# JobConnect - Job Recommendation System

A full-featured job portal built with **Flask + SQLite3 + Bootstrap 5**.

## Features

### 3 Roles
| Role | Capabilities |
|------|-------------|
| **Admin** | Dashboard analytics, manage all users/jobs, promote/demote roles, reports |
| **Recruiter** | Post jobs with due dates, manage own listings, review applicants, update status |
| **User** | Browse/filter jobs by skill/location/type, apply with cover letter, AI-powered recommendations |

### Key Modules
- **Authentication** — Register, Login, Role-based access
- **Job Matching Engine** — Skill-based match score (0-100%) 
- **Smart Search & Filter** — Search by keyword, skill, location, type, category, experience
- **Application Tracker** — Full status pipeline (Applied → Reviewed → Shortlisted → Interview → Offered/Rejected)
- **Admin Reports** — Application trends, job categories, top recruiters, monthly registrations

## Setup & Run

```bash
# 1. Install Flask
pip install flask

# 2. Run the app
python app.py
```

Open browser: **http://localhost:5000**

## Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@jobportal.com | admin123 |
| Recruiter | recruiter@jobportal.com | recruiter123 |
| User | Register at /register | - |

## Project Structure

```
job_recommendation/
├── app.py                    # Main Flask app + routes
├── job_recommendation.db     # SQLite database (auto-created)
├── static/
│   └── resumes/              # Uploaded resumes
└── templates/
    ├── base.html             # Sidebar layout
    ├── login.html
    ├── register.html
    ├── user_dashboard.html
    ├── admin_dashboard.html
    ├── recruiter_dashboard.html
    ├── jobs.html             # Job listing + filters
    ├── job_detail.html
    ├── job_form.html         # Add/Edit job
    ├── apply_job.html
    ├── my_applications.html
    ├── job_applications.html # Recruiter view
    ├── profile.html
    ├── admin_users.html
    ├── recruiter_jobs.html
    └── admin_reports.html
```

## Database Tables
- `users` — All users (admin/recruiter/user)
- `user_profiles` — Skills, experience, resume, education
- `jobs` — Job listings with due dates, categories
- `applications` — Application tracking with status pipeline
- `recommendations` — Computed match scores per user-job pair
"# Job_recommendation_system" 
