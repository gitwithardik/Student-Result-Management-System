# STUDENT RESULT MANAGEMENT SYSTEM

Web-based project with separate teacher/student authentication and PDF result export.

## Features
- Teacher login/logout (session-based)
- Student login/logout (session-based)
- Student management
- Subject management
- Marks entry and update
- Automatic grade and pass/fail calculation
- Download result report as PDF

## Default Teacher Login
- Username: `teacher`
- Password: `teacher123`

## Student Login
- Roll number: student roll number
- Password: `student_password` field (defaults to roll number in seeded data)

Set custom credentials via environment variables:
- `TEACHER_USERNAME`
- `TEACHER_PASSWORD`
- `APP_SECRET_KEY`

## Run
```bash
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`

## Demo College Database
You can populate a realistic sample college dataset (dummy data) with:

```bash
python seed_college_data.py
```

This creates:
- 60 students
- 6 subjects
- 360 marks entries

Note: This is synthetic sample data, not a real college's private database.
