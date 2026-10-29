import csv
import io
import os
import sqlite3
from datetime import datetime, date

from flask import Flask, redirect, render_template, request, send_file, send_from_directory, session, make_response, flash, get_flashed_messages

app = Flask(__name__)
app.secret_key = "blw-training-portal-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "training_portal.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present', 'Absent'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)",
        ("aman", "aman123"),
    )
    conn.commit()
    conn.close()


@app.route("/")
def root():
    return redirect("/index.php")


@app.route("/index.php", methods=["GET"])
def index_page():
    return render_template("index.html")


@app.route("/login.php", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        return render_template("index.html")

    username = request.form.get("username", "")
    password = request.form.get("password", "")

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, password),
    ).fetchone()
    conn.close()

    if user:
        session["username"] = username
        return redirect("/dashboard.php")

    return render_template("index.html", error="Invalid Username or Password")


@app.route("/dashboard.php")
def dashboard_page():
    if "username" not in session:
        return redirect("/index.php")

    conn = get_db()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    attendance_count = conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
    notice_count = conn.execute("SELECT COUNT(*) FROM notices").fetchone()[0]
    present_count = conn.execute("SELECT COUNT(*) FROM attendance WHERE status = 'Present'").fetchone()[0]
    absent_count = conn.execute("SELECT COUNT(*) FROM attendance WHERE status = 'Absent'").fetchone()[0]
    total_attendance = present_count + absent_count
    if total_attendance > 0:
        present_percent = round((present_count / total_attendance) * 100)
        absent_percent = round((absent_count / total_attendance) * 100)
    else:
        present_percent = 0
        absent_percent = 0

    recent = conn.execute("SELECT * FROM notices ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()

    return render_template(
        "dashboard.html",
        username=session["username"],
        user_count=user_count,
        attendance_count=attendance_count,
        notice_count=notice_count,
        present_count=present_count,
        absent_count=absent_count,
        present_percent=present_percent,
        absent_percent=absent_percent,
        recent=recent,
    )


@app.route("/attendance.php", methods=["GET", "POST"])
def attendance_page():
    if "username" not in session:
        return redirect("/index.php")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        attendance_date = request.form.get("date", "").strip()
        status = request.form.get("status", "")

        try:
            date.fromisoformat(attendance_date)
        except ValueError:
            attendance_date = ""

        if not name or not attendance_date or status not in ("Present", "Absent"):
            flash("Please enter a student name, valid date and status (Present or Absent).", "error")
        else:
            conn = get_db()
            conn.execute(
                "INSERT INTO attendance (name, date, status) VALUES (?, ?, ?)",
                (name, attendance_date, status),
            )
            conn.commit()
            conn.close()
            flash("Attendance added successfully.", "success")
            return redirect("/attendance.php")

    if request.args.get("delete"):
        record_id = request.args.get("delete")
        conn = get_db()
        conn.execute("DELETE FROM attendance WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()

    conn = get_db()
    query = "SELECT * FROM attendance WHERE 1=1"
    params = []

    search = request.args.get("search", "").strip()
    if search:
        query += " AND name COLLATE NOCASE LIKE ? ESCAPE '\\'"
        escaped_search = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped_search}%")

    from_date = request.args.get("from_date", "").strip()
    if from_date:
        query += " AND date >= ?"
        params.append(from_date)

    to_date = request.args.get("to_date", "").strip()
    if to_date:
        query += " AND date <= ?"
        params.append(to_date)

    query += " ORDER BY id DESC"
    records = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "attendance.html",
        records=records,
        search=search,
        from_date=from_date,
        to_date=to_date,
        sn=1,
    )


@app.route("/notice.php", methods=["GET", "POST"])
def notice_page():
    if "username" not in session:
        return redirect("/index.php")

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title or not description:
            flash("Please enter both notice title and description.", "error")
        else:
            conn = get_db()
            conn.execute(
                "INSERT INTO notices (title, description, created_at) VALUES (?, ?, ?)",
                (title, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            conn.close()
            flash("Notice posted successfully.", "success")
            return redirect("/notice.php")

    if request.args.get("delete"):
        notice_id = request.args.get("delete")
        conn = get_db()
        conn.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
        conn.commit()
        conn.close()

    conn = get_db()
    notices = conn.execute("SELECT * FROM notices ORDER BY id DESC").fetchall()
    conn.close()

    return render_template("notice.html", notices=notices, sn=1)


@app.route("/edit_attendance.php", methods=["GET", "POST"])
def edit_attendance_page():
    if "username" not in session:
        return redirect("/index.php")

    record_id = request.args.get("id")
    conn = get_db()
    record = conn.execute("SELECT * FROM attendance WHERE id = ?", (record_id,)).fetchone()
    conn.close()

    if not record:
        return redirect("/attendance.php")

    if request.method == "POST" and request.form.get("update"):
        name = request.form.get("name", "")
        date = request.form.get("date", "")
        status = request.form.get("status", "Present")
        conn = get_db()
        conn.execute(
            "UPDATE attendance SET name = ?, date = ?, status = ? WHERE id = ?",
            (name, date, status, record_id),
        )
        conn.commit()
        conn.close()
        return redirect("/attendance.php")

    return render_template("edit_attendance.html", record=record)


@app.route("/edit_notice.php", methods=["GET", "POST"])
def edit_notice_page():
    if "username" not in session:
        return redirect("/index.php")

    notice_id = request.args.get("id")
    conn = get_db()
    notice = conn.execute("SELECT * FROM notices WHERE id = ?", (notice_id,)).fetchone()
    conn.close()

    if not notice:
        return redirect("/notice.php")

    if request.method == "POST" and request.form.get("update"):
        title = request.form.get("title", "")
        description = request.form.get("description", "")
        conn = get_db()
        conn.execute(
            "UPDATE notices SET title = ?, description = ? WHERE id = ?",
            (title, description, notice_id),
        )
        conn.commit()
        conn.close()
        return redirect("/notice.php")

    return render_template("edit_notice.html", notice=notice)


@app.route("/download_report.php")
def download_report():
    if "username" not in session:
        return redirect("/index.php")

    conn = get_db()
    rows = conn.execute("SELECT * FROM attendance ORDER BY id").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["S.No", "Name", "Date", "Status"])
    for index, row in enumerate(rows, start=1):
        writer.writerow([index, row["name"], row["date"], row["status"]])

    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = "attachment; filename=attendance_report.csv"
    return response


@app.route("/logout.php")
def logout_page():
    session.clear()
    return redirect("/index.php")


@app.route("/style.css")
def serve_stylesheet():
    return send_file(os.path.join(BASE_DIR, "style.css"), mimetype="text/css")


@app.route("/blw_logo.png")
def serve_logo():
    return send_file(os.path.join(BASE_DIR, "blw_logo.png"), mimetype="image/png")


@app.route("/images/<path:filename>")
def serve_images(filename):
    return send_from_directory(os.path.join(BASE_DIR, "images"), filename)


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
