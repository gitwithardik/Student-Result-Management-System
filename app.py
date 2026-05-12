from __future__ import annotations

import io
import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "student_results.db"

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "dev-secret-change-me")
app.config["TEACHER_USERNAME"] = os.getenv("TEACHER_USERNAME", "teacher")
app.config["TEACHER_PASSWORD"] = os.getenv("TEACHER_PASSWORD", "teacher123")


def teacher_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_role") != "teacher":
            flash("Teacher login required.", "error")
            return redirect(url_for("teacher_login"))
        return view(*args, **kwargs)

    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_role") != "student" or not session.get("student_id"):
            flash("Student login required.", "error")
            return redirect(url_for("student_login"))
        return view(*args, **kwargs)

    return wrapped


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_number TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                student_password TEXT
            );

            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_code TEXT UNIQUE NOT NULL,
                subject_name TEXT NOT NULL,
                max_marks INTEGER NOT NULL CHECK(max_marks > 0)
            );

            CREATE TABLE IF NOT EXISTS marks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                marks_obtained REAL NOT NULL CHECK(marks_obtained >= 0),
                UNIQUE(student_id, subject_id),
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            );
            """
        )
        # Migration-safe: add student_password if database existed earlier.
        cols = [row["name"] for row in conn.execute("PRAGMA table_info(students)").fetchall()]
        if "student_password" not in cols:
            conn.execute("ALTER TABLE students ADD COLUMN student_password TEXT")
            conn.execute(
                "UPDATE students SET student_password = roll_number WHERE student_password IS NULL OR student_password = ''"
            )


def grade_from_percentage(percentage: float) -> str:
    if percentage >= 90:
        return "A+"
    if percentage >= 80:
        return "A"
    if percentage >= 70:
        return "B"
    if percentage >= 60:
        return "C"
    if percentage >= 50:
        return "D"
    return "F"


def get_results():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT s.roll_number, s.full_name, s.class_name,
                   COALESCE(SUM(m.marks_obtained), 0) AS total_obtained,
                   COALESCE(SUM(sub.max_marks), 0) AS total_max,
                   COUNT(m.id) AS subjects_attempted
            FROM students s
            LEFT JOIN marks m ON m.student_id = s.id
            LEFT JOIN subjects sub ON sub.id = m.subject_id
            GROUP BY s.id, s.roll_number, s.full_name, s.class_name
            ORDER BY s.roll_number
            """
        ).fetchall()

    results = []
    for row in rows:
        total_max = float(row["total_max"])
        total_obtained = float(row["total_obtained"])
        percentage = (total_obtained / total_max * 100) if total_max > 0 else 0.0
        status = "PASS" if percentage >= 50 and total_max > 0 else "FAIL"
        results.append(
            {
                "roll_number": row["roll_number"],
                "full_name": row["full_name"],
                "class_name": row["class_name"],
                "subjects_attempted": row["subjects_attempted"],
                "total_obtained": round(total_obtained, 2),
                "total_max": round(total_max, 2),
                "percentage": round(percentage, 2),
                "grade": grade_from_percentage(percentage) if total_max > 0 else "N/A",
                "status": status,
            }
        )
    return results


@app.get("/")
def home():
    role = session.get("user_role")
    if role == "teacher":
        return redirect(url_for("dashboard"))
    if role == "student":
        return redirect(url_for("student_results"))
    return render_template("landing.html")


@app.route("/teacher/login", methods=["GET", "POST"])
def teacher_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if (
            username == app.config["TEACHER_USERNAME"]
            and password == app.config["TEACHER_PASSWORD"]
        ):
            session.clear()
            session["user_role"] = "teacher"
            session["teacher_user"] = username
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "error")
    return render_template("teacher_login.html")


@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        roll_number = request.form.get("roll_number", "").strip()
        password = request.form.get("password", "").strip()
        with get_connection() as conn:
            student = conn.execute(
                """
                SELECT id, roll_number, full_name
                FROM students
                WHERE roll_number = ? AND student_password = ?
                """,
                (roll_number, password),
            ).fetchone()
        if not student:
            flash("Invalid roll number or password.", "error")
            return redirect(url_for("student_login"))
        session.clear()
        session["user_role"] = "student"
        session["student_id"] = student["id"]
        session["student_name"] = student["full_name"]
        flash("Student login successful.", "success")
        return redirect(url_for("student_results"))
    return render_template("student_login.html")


@app.get("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("teacher_login"))


@app.route("/dashboard")
@teacher_required
def dashboard():
    with get_connection() as conn:
        students = conn.execute("SELECT COUNT(*) AS c FROM students").fetchone()["c"]
        subjects = conn.execute("SELECT COUNT(*) AS c FROM subjects").fetchone()["c"]
        mark_entries = conn.execute("SELECT COUNT(*) AS c FROM marks").fetchone()["c"]
    return render_template(
        "index.html",
        students=students,
        subjects=subjects,
        mark_entries=mark_entries,
    )


@app.route("/students", methods=["GET", "POST"])
@teacher_required
def students_page():
    if request.method == "POST":
        roll_number = request.form.get("roll_number", "").strip()
        full_name = request.form.get("full_name", "").strip()
        class_name = request.form.get("class_name", "").strip()
        student_password = request.form.get("student_password", "").strip()
        if not all([roll_number, full_name, class_name]):
            flash("All student fields are required.", "error")
            return redirect(url_for("students_page"))
        if not student_password:
            student_password = roll_number
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO students (roll_number, full_name, class_name, student_password)
                    VALUES (?, ?, ?, ?)
                    """,
                    (roll_number, full_name, class_name, student_password),
                )
            flash("Student added successfully.", "success")
        except sqlite3.IntegrityError:
            flash("Roll number already exists.", "error")
        return redirect(url_for("students_page"))

    with get_connection() as conn:
        students = conn.execute(
            """
            SELECT id, roll_number, full_name, class_name, student_password
            FROM students
            ORDER BY id DESC
            """
        ).fetchall()
    return render_template("students.html", students=students)


@app.post("/students/delete/<int:student_id>")
@teacher_required
def delete_student(student_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    flash("Student deleted.", "success")
    return redirect(url_for("students_page"))


@app.route("/subjects", methods=["GET", "POST"])
@teacher_required
def subjects_page():
    if request.method == "POST":
        subject_code = request.form.get("subject_code", "").strip()
        subject_name = request.form.get("subject_name", "").strip()
        max_marks = request.form.get("max_marks", "").strip()
        if not all([subject_code, subject_name, max_marks]):
            flash("All subject fields are required.", "error")
            return redirect(url_for("subjects_page"))
        try:
            max_marks_int = int(max_marks)
            if max_marks_int <= 0:
                raise ValueError
        except ValueError:
            flash("Max marks must be a positive integer.", "error")
            return redirect(url_for("subjects_page"))
        try:
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO subjects (subject_code, subject_name, max_marks) VALUES (?, ?, ?)",
                    (subject_code, subject_name, max_marks_int),
                )
            flash("Subject added successfully.", "success")
        except sqlite3.IntegrityError:
            flash("Subject code already exists.", "error")
        return redirect(url_for("subjects_page"))

    with get_connection() as conn:
        subjects = conn.execute(
            "SELECT id, subject_code, subject_name, max_marks FROM subjects ORDER BY id DESC"
        ).fetchall()
    return render_template("subjects.html", subjects=subjects)


@app.post("/subjects/delete/<int:subject_id>")
@teacher_required
def delete_subject(subject_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    flash("Subject deleted.", "success")
    return redirect(url_for("subjects_page"))


@app.route("/marks", methods=["GET", "POST"])
@teacher_required
def marks_page():
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        subject_id = request.form.get("subject_id", "").strip()
        marks_obtained = request.form.get("marks_obtained", "").strip()
        if not all([student_id, subject_id, marks_obtained]):
            flash("All mark fields are required.", "error")
            return redirect(url_for("marks_page"))
        try:
            marks_value = float(marks_obtained)
            student_id_int = int(student_id)
            subject_id_int = int(subject_id)
        except ValueError:
            flash("Student, subject, and marks must be numeric.", "error")
            return redirect(url_for("marks_page"))

        with get_connection() as conn:
            subject = conn.execute(
                "SELECT max_marks FROM subjects WHERE id = ?", (subject_id_int,)
            ).fetchone()
            if not subject:
                flash("Invalid subject selected.", "error")
                return redirect(url_for("marks_page"))
            max_marks = float(subject["max_marks"])
            if marks_value < 0 or marks_value > max_marks:
                flash(f"Marks must be between 0 and {max_marks:g}.", "error")
                return redirect(url_for("marks_page"))
            try:
                conn.execute(
                    "INSERT INTO marks (student_id, subject_id, marks_obtained) VALUES (?, ?, ?)",
                    (student_id_int, subject_id_int, marks_value),
                )
                flash("Marks saved.", "success")
            except sqlite3.IntegrityError:
                conn.execute(
                    "UPDATE marks SET marks_obtained = ? WHERE student_id = ? AND subject_id = ?",
                    (marks_value, student_id_int, subject_id_int),
                )
                flash("Marks updated.", "success")
        return redirect(url_for("marks_page"))

    with get_connection() as conn:
        students = conn.execute(
            "SELECT id, roll_number, full_name FROM students ORDER BY roll_number"
        ).fetchall()
        subjects = conn.execute(
            "SELECT id, subject_code, subject_name, max_marks FROM subjects ORDER BY subject_code"
        ).fetchall()
        marks = conn.execute(
            """
            SELECT m.id, s.roll_number, s.full_name, sub.subject_name, sub.max_marks, m.marks_obtained
            FROM marks m
            JOIN students s ON s.id = m.student_id
            JOIN subjects sub ON sub.id = m.subject_id
            ORDER BY m.id DESC
            """
        ).fetchall()
    return render_template("marks.html", students=students, subjects=subjects, marks=marks)


@app.post("/marks/delete/<int:mark_id>")
@teacher_required
def delete_mark(mark_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM marks WHERE id = ?", (mark_id,))
    flash("Mark entry deleted.", "success")
    return redirect(url_for("marks_page"))


@app.get("/results")
@teacher_required
def results_page():
    return render_template("results.html", results=get_results())


@app.get("/results/pdf")
@teacher_required
def results_pdf():
    data = get_results()
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "Student Result Management System - Result Report")
    y -= 24
    pdf.setFont("Helvetica", 9)
    pdf.drawString(40, y, "Roll")
    pdf.drawString(95, y, "Name")
    pdf.drawString(250, y, "Class")
    pdf.drawString(300, y, "Total")
    pdf.drawString(350, y, "Out Of")
    pdf.drawString(400, y, "%")
    pdf.drawString(435, y, "Grade")
    pdf.drawString(480, y, "Status")
    y -= 12
    pdf.line(40, y, 540, y)
    y -= 14

    for item in data:
        if y < 40:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 9)
        pdf.drawString(40, y, str(item["roll_number"]))
        pdf.drawString(95, y, item["full_name"][:25])
        pdf.drawString(250, y, item["class_name"][:8])
        pdf.drawString(300, y, str(item["total_obtained"]))
        pdf.drawString(350, y, str(item["total_max"]))
        pdf.drawString(400, y, str(item["percentage"]))
        pdf.drawString(435, y, item["grade"])
        pdf.drawString(480, y, item["status"])
        y -= 14

    pdf.save()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="student_results_report.pdf",
        mimetype="application/pdf",
    )


@app.get("/my-results")
@student_required
def student_results():
    student_id = session["student_id"]
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.id, s.roll_number, s.full_name, s.class_name,
                   COALESCE(SUM(m.marks_obtained), 0) AS total_obtained,
                   COALESCE(SUM(sub.max_marks), 0) AS total_max,
                   COUNT(m.id) AS subjects_attempted
            FROM students s
            LEFT JOIN marks m ON m.student_id = s.id
            LEFT JOIN subjects sub ON sub.id = m.subject_id
            WHERE s.id = ?
            GROUP BY s.id, s.roll_number, s.full_name, s.class_name
            """,
            (student_id,),
        ).fetchone()
        subject_wise = conn.execute(
            """
            SELECT sub.subject_code, sub.subject_name, sub.max_marks, COALESCE(m.marks_obtained, 0) AS marks_obtained
            FROM subjects sub
            LEFT JOIN marks m ON m.subject_id = sub.id AND m.student_id = ?
            ORDER BY sub.subject_code
            """,
            (student_id,),
        ).fetchall()

    total_max = float(row["total_max"]) if row else 0.0
    total_obtained = float(row["total_obtained"]) if row else 0.0
    percentage = (total_obtained / total_max * 100) if total_max > 0 else 0.0
    result = {
        "roll_number": row["roll_number"] if row else "",
        "full_name": row["full_name"] if row else "",
        "class_name": row["class_name"] if row else "",
        "subjects_attempted": row["subjects_attempted"] if row else 0,
        "total_obtained": round(total_obtained, 2),
        "total_max": round(total_max, 2),
        "percentage": round(percentage, 2),
        "grade": grade_from_percentage(percentage) if total_max > 0 else "N/A",
        "status": "PASS" if percentage >= 50 and total_max > 0 else "FAIL",
    }
    return render_template("student_results.html", result=result, subject_wise=subject_wise)


@app.get("/my-results/pdf")
@student_required
def student_results_pdf():
    student_id = session["student_id"]
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.roll_number, s.full_name, s.class_name,
                   COALESCE(SUM(m.marks_obtained), 0) AS total_obtained,
                   COALESCE(SUM(sub.max_marks), 0) AS total_max
            FROM students s
            LEFT JOIN marks m ON m.student_id = s.id
            LEFT JOIN subjects sub ON sub.id = m.subject_id
            WHERE s.id = ?
            GROUP BY s.id, s.roll_number, s.full_name, s.class_name
            """,
            (student_id,),
        ).fetchone()

        subject_wise = conn.execute(
            """
            SELECT sub.subject_code, sub.subject_name, sub.max_marks, COALESCE(m.marks_obtained, 0) AS marks_obtained
            FROM subjects sub
            LEFT JOIN marks m ON m.subject_id = sub.id AND m.student_id = ?
            ORDER BY sub.subject_code
            """,
            (student_id,),
        ).fetchall()

    if not row:
        flash("No result data found for this student.", "error")
        return redirect(url_for("student_results"))

    total_max = float(row["total_max"])
    total_obtained = float(row["total_obtained"])
    percentage = (total_obtained / total_max * 100) if total_max > 0 else 0.0
    grade = grade_from_percentage(percentage) if total_max > 0 else "N/A"
    status = "PASS" if percentage >= 50 and total_max > 0 else "FAIL"

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _, height = A4
    y = height - 40

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "Student Result Report")
    y -= 24

    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, f"Roll Number: {row['roll_number']}")
    y -= 16
    pdf.drawString(40, y, f"Name: {row['full_name']}")
    y -= 16
    pdf.drawString(40, y, f"Class: {row['class_name']}")
    y -= 16
    pdf.drawString(40, y, f"Total: {round(total_obtained, 2)} / {round(total_max, 2)}")
    y -= 16
    pdf.drawString(40, y, f"Percentage: {round(percentage, 2)}%")
    y -= 16
    pdf.drawString(40, y, f"Grade: {grade}    Status: {status}")
    y -= 22

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Code")
    pdf.drawString(100, y, "Subject")
    pdf.drawString(320, y, "Obtained")
    pdf.drawString(400, y, "Max")
    y -= 10
    pdf.line(40, y, 520, y)
    y -= 14

    pdf.setFont("Helvetica", 10)
    for item in subject_wise:
        if y < 40:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 10)
        pdf.drawString(40, y, str(item["subject_code"]))
        pdf.drawString(100, y, str(item["subject_name"])[:36])
        pdf.drawString(320, y, str(item["marks_obtained"]))
        pdf.drawString(400, y, str(item["max_marks"]))
        y -= 14

    pdf.save()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{row['roll_number']}_result.pdf",
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
