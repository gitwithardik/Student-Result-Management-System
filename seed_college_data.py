from __future__ import annotations

import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "student_results.db"


def seed() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # Ensure tables exist (same schema as app.py).
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_number TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            class_name TEXT NOT NULL
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

    # Reset demo data.
    cur.execute("DELETE FROM marks")
    cur.execute("DELETE FROM students")
    cur.execute("DELETE FROM subjects")
    cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('students', 'subjects', 'marks')")

    subjects = [
        ("CS101", "Programming Fundamentals", 100),
        ("CS102", "Data Structures", 100),
        ("CS103", "Database Management Systems", 100),
        ("CS104", "Computer Networks", 100),
        ("CS105", "Operating Systems", 100),
        ("MA101", "Engineering Mathematics", 100),
    ]
    cur.executemany(
        "INSERT INTO subjects (subject_code, subject_name, max_marks) VALUES (?, ?, ?)",
        subjects,
    )

    first_names = [
        "Aarav",
        "Vivaan",
        "Aditya",
        "Vishaal",
        "Arjun",
        "Sai",
        "Reyansh",
        "Krishna",
        "Ishaan",
        "Ananya",
        "Diya",
        "Ira",
        "Aadhya",
        "Sara",
        "Myra",
        "Riya",
        "Priya",
        "Sneha",
    ]
    last_names = [
        "Sharma",
        "Verma",
        "Patel",
        "Reddy",
        "Mehta",
        "Gupta",
        "Nair",
        "Iyer",
        "Singh",
        "Khan",
    ]

    classes = ["BCA-1", "BCA-2", "BSc CS-1", "BSc CS-2", "BTech CSE-1"]
    students = []
    for i in range(1, 61):
        roll = f"CLG2026{i:03d}"
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        class_name = random.choice(classes)
        students.append((roll, name, class_name, roll))

    cur.executemany(
        """
        INSERT INTO students (roll_number, full_name, class_name, student_password)
        VALUES (?, ?, ?, ?)
        """,
        students,
    )

    subject_rows = cur.execute("SELECT id, max_marks FROM subjects").fetchall()
    student_ids = [row[0] for row in cur.execute("SELECT id FROM students").fetchall()]

    marks_rows = []
    for sid in student_ids:
        for subject_id, max_marks in subject_rows:
            score = round(random.uniform(35, max_marks), 2)
            marks_rows.append((sid, subject_id, score))

    cur.executemany(
        "INSERT INTO marks (student_id, subject_id, marks_obtained) VALUES (?, ?, ?)",
        marks_rows,
    )

    conn.commit()
    conn.close()
    print("Seed complete: 60 students, 6 subjects, 360 marks entries.")


if __name__ == "__main__":
    seed()
