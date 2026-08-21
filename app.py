from datetime import datetime, time
import io
import json
import os
import sqlite3
import zipfile
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for
import pandas as pd
import qrcode
from twilio.rest import Client

app = Flask(__name__)

# ==========================================
# PATH CONFIGURATION
# ==========================================
base_dir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(base_dir, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

DB_PATH = os.path.join(base_dir, "database.db")
SETTINGS_PATH = os.path.join(base_dir, "settings.json")

# ==========================================
# TWILIO WHATSAPP SETTINGS
# ==========================================
TWILIO_ACCOUNT_SID = "AC55dcfe411a96a1cf1cababade002cf05"
TWILIO_AUTH_TOKEN = "8f990743bc3a3943886dead24c926721"
TWILIO_PHONE_NUMBER = "whatsapp:+14155238886"

def send_whatsapp_msg(
    parent_number, index_no, time_str, is_paid, fee_month, fee_amount
):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("⚠️ Twilio credentials are not configured; WhatsApp message skipped.")
        return

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        if is_paid == "yes":
            msg_body = (
                f"Hello! Student (Index: {index_no}) has arrived safely at school "
                f"at {time_str}. Class fee for {fee_month} of LKR {fee_amount}.00 "
                f"has been paid successfully."
            )
        else:
            msg_body = (
                f"Hello, student (Index: {index_no}) has arrived at school "
                f"safely at {time_str}."
            )

        parent_number = (parent_number or "").strip()
        if parent_number.startswith("0"):
            parent_number = "94" + parent_number[1:]
        elif not parent_number.startswith("94"):
            parent_number = "94" + parent_number

        client.messages.create(
            from_=TWILIO_PHONE_NUMBER,
            body=msg_body,
            to=f"whatsapp:+{parent_number}",
        )
    except Exception as e:
        print("❌ මැසේජ් එක යවන්න බැරි වුණා:", e)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            index_no TEXT,
            student_name TEXT,
            class_name TEXT,
            phone TEXT,
            email TEXT,
            address TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            index_no TEXT,
            student_name TEXT,
            class_name TEXT,
            status TEXT,
            date TEXT,
            time TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paid_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            index_no TEXT,
            student_name TEXT,
            date TEXT,
            time TEXT,
            amount_status TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade TEXT,
            class_name TEXT,
            teacher_name TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            index_no TEXT,
            student_name TEXT,
            date TEXT,
            reason TEXT
        )
    """)

    conn.commit()
    conn.close()


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "school_name": "Urapola Central College",
        "unit_name": "INNOVATION UNIT",
        "whatsapp_template": (
            "ආයුබෝවන් {name},\n"
            "ඔබගේ ලියාපදිංචිය සාර්ථකයි! 🎉\n\n"
            "🏫 {school} - {unit}\n"
            "🆔 ඔබගේ අංකය: *{index}*"
        ),
    }


@app.route("/")
def index():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    today = datetime.now(ZoneInfo("Asia/Colombo")).strftime("%Y-%m-%d")
    selected_date = request.args.get("date", today)

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (today,))
    present_today = cursor.fetchone()[0]

    absent_today = total_students - present_today

    cursor.execute(
        "SELECT * FROM attendance WHERE date = ? ORDER BY id DESC",
        (selected_date,),
    )
    recent_logs = cursor.fetchall()

    cursor.execute("SELECT * FROM leave_requests WHERE date = ?", (today,))
    absences_today = cursor.fetchall()

    cursor.execute("SELECT DISTINCT date FROM attendance ORDER BY date DESC")
    available_dates = [row["date"] for row in cursor.fetchall()]

    if today not in available_dates:
        available_dates.insert(0, today)

    conn.close()

    return render_template(
        "index.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        logs=recent_logs,
        absences=absences_today,
        available_dates=available_dates,
        selected_date=selected_date,
        today=today,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM classes")
    classes_list = cursor.fetchall()

    cursor.execute("SELECT MAX(id) FROM students")
    max_id = cursor.fetchone()[0]
    next_id_num = (max_id + 1) if max_id else 1
    next_index = f"ST-{next_id_num:04d}"

    newly_added = None

    if request.method == "POST":
        index_no = request.form.get("index_no", "").strip()
        student_name = request.form.get("student_name", "").strip()
        class_name = request.form.get("class_name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()

        if not index_no:
            index_no = next_index

        cursor.execute(
            """
            INSERT INTO students
            (index_no, student_name, class_name, phone, email, address)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (index_no, student_name, class_name, phone, email, address),
        )
        conn.commit()

        newly_added = {
            "index_no": index_no,
            "student_name": student_name,
            "class_name": class_name,
            "phone": phone,
            "email": email,
            "address": address,
        }

        cursor.execute("SELECT MAX(id) FROM students")
        max_id = cursor.fetchone()[0]
        next_id_num = (max_id + 1) if max_id else 1
        next_index = f"ST-{next_id_num:04d}"

    conn.close()

    return render_template(
        "register.html",
        next_index=next_index,
        newly_added=newly_added,
        classes=classes_list,
    )


@app.route("/students")
def students():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, index_no, student_name, class_name,
               phone, email, address
        FROM students
        ORDER BY id DESC
        """
    )
    all_students = cursor.fetchall()

    cursor.execute("SELECT * FROM classes ORDER BY grade, class_name")
    classes_list = cursor.fetchall()

    conn.close()
    return render_template(
        "students.html",
        students=all_students,
        classes=classes_list,
    )


@app.route("/delete_student/<index_no>")
def delete_student(index_no):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE index_no = ?", (index_no,))
    conn.commit()
    conn.close()
    return redirect(url_for("students"))


@app.route("/scanner")
def scanner():
    return render_template("scanner.html")


@app.route("/scan/<index_no>")
def scan_student(index_no):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM students WHERE index_no = ?", (index_no,))
    student = cursor.fetchone()

    if not student:
        conn.close()
        return "Student not found!", 404

    today = datetime.now(ZoneInfo("Asia/Colombo")).strftime("%Y-%m-%d")

    cursor.execute(
        """
        SELECT * FROM attendance
        WHERE index_no = ? AND date = ?
        """,
        (index_no, today),
    )
    existing_attendance = cursor.fetchone()

    cursor.execute(
        """
        SELECT * FROM leave_requests
        WHERE index_no = ? AND date = ?
        """,
        (index_no, today),
    )
    leave_request = cursor.fetchone()

    conn.close()

    return render_template(
        "mark_attendance.html",
        student=student,
        existing_attendance=existing_attendance,
        leave_request=leave_request,
    )


@app.route("/save_attendance", methods=["POST"])
def save_attendance():
    index_no = request.form.get("index_no", "").strip()
    student_name = request.form.get("student_name", "").strip()
    is_paid = request.form.get("is_paid", "no")
    fee_month = request.form.get("fee_month", "")
    fee_amount = request.form.get("fee_amount", "0")

    now = datetime.now(ZoneInfo("Asia/Colombo"))
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%I:%M %p")

    status_text = (
        f"Paid ({fee_month} - LKR {fee_amount})"
        if is_paid == "yes"
        else "Present"
    )

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM attendance
        WHERE index_no = ? AND date = ?
        """,
        (index_no, current_date),
    )
    already_marked = cursor.fetchone()

    if not already_marked:
        cursor.execute(
            "SELECT class_name, phone FROM students WHERE index_no = ?",
            (index_no,),
        )
        res = cursor.fetchone()
        class_name = res[0] if res else ""
        parent_phone = res[1] if res else ""

        cursor.execute(
            """
            INSERT INTO attendance
            (index_no, student_name, class_name, status, date, time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                index_no,
                student_name,
                class_name,
                status_text,
                current_date,
                current_time,
            ),
        )

        if is_paid == "yes":
            cursor.execute(
                """
                INSERT INTO paid_students
                (index_no, student_name, date, time, amount_status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    index_no,
                    student_name,
                    current_date,
                    current_time,
                    f"{fee_month}: LKR {fee_amount}",
                ),
            )

        conn.commit()

        if parent_phone:
            send_whatsapp_msg(
                parent_phone,
                index_no,
                current_time,
                is_paid,
                fee_month,
                fee_amount,
            )

    conn.close()
    return redirect(url_for("index"))


@app.route("/leave", methods=["GET", "POST"])
def leave():
    if request.method == "POST":
        index_no = request.form.get("index_no", "").strip()
        reason = request.form.get("reason", "").strip()
        leave_date = request.form.get("leave_date", "").strip()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT student_name FROM students WHERE index_no = ?",
            (index_no,),
        )
        student = cursor.fetchone()
        student_name = student[0] if student else "Unknown Student"

        cursor.execute(
            """
            INSERT INTO leave_requests
            (index_no, student_name, date, reason)
            VALUES (?, ?, ?, ?)
            """,
            (index_no, student_name, leave_date, reason),
        )

        conn.commit()
        conn.close()

        return redirect(url_for("index"))

    today_date = datetime.now(ZoneInfo("Asia/Colombo")).strftime("%Y-%m-%d")
    return render_template("leave.html", today_date=today_date)


@app.route("/reports", methods=["GET", "POST"])
def reports():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT index_no, student_name FROM students ORDER BY student_name"
    )
    all_students = cursor.fetchall()

    report_data = None
    selected_index = ""
    filter_type = "monthly"

    now = datetime.now(ZoneInfo("Asia/Colombo"))
    current_month = now.strftime("%Y-%m")
    current_year = now.strftime("%Y")

    month_val = current_month
    year_val = current_year

    if request.method == "POST":
        selected_index = request.form.get("index_no", "")
        filter_type = request.form.get("filter_type", "monthly")
        month_val = request.form.get("month_val", current_month)
        year_val = request.form.get("year_val", current_year)

        cursor.execute(
            "SELECT * FROM students WHERE index_no = ?",
            (selected_index,),
        )
        student = cursor.fetchone()

        if student:
            if filter_type == "monthly":
                cursor.execute(
                    """
                    SELECT * FROM attendance
                    WHERE index_no = ? AND date LIKE ?
                    ORDER BY date DESC
                    """,
                    (selected_index, f"{month_val}%"),
                )
                attendance_records = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT * FROM paid_students
                    WHERE index_no = ? AND date LIKE ?
                    ORDER BY date DESC
                    """,
                    (selected_index, f"{month_val}%"),
                )
                fee_records = cursor.fetchall()
            else:
                cursor.execute(
                    """
                    SELECT * FROM attendance
                    WHERE index_no = ? AND date LIKE ?
                    ORDER BY date DESC
                    """,
                    (selected_index, f"{year_val}%"),
                )
                attendance_records = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT * FROM paid_students
                    WHERE index_no = ? AND date LIKE ?
                    ORDER BY date DESC
                    """,
                    (selected_index, f"{year_val}%"),
                )
                fee_records = cursor.fetchall()

            report_data = {
                "student": student,
                "attendance": attendance_records,
                "fees": fee_records,
                "filter_type": filter_type,
                "target": (
                    month_val if filter_type == "monthly" else year_val
                ),
            }

    conn.close()

    return render_template(
        "reports.html",
        students=all_students,
        report_data=report_data,
        selected_index=selected_index,
        filter_type=filter_type,
        month_val=month_val,
        year_val=year_val,
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    success_msg = None
    current_settings = load_settings()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == "POST":
        if "school_name" in request.form:
            current_settings["school_name"] = request.form.get(
                "school_name", ""
            )
            current_settings["unit_name"] = request.form.get(
                "unit_name", ""
            )
            current_settings["whatsapp_template"] = request.form.get(
                "whatsapp_template", ""
            )

            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    current_settings,
                    f,
                    ensure_ascii=False,
                    indent=4,
                )

            success_msg = "✅ සාමාන්‍ය සැකසුම් සාර්ථකව යාවත්කාලීන කළා!"

        action = request.form.get("action")

        if action == "add_class":
            grade = request.form.get("grade", "")
            class_name = request.form.get("class_name", "").strip()
            teacher_name = request.form.get("teacher_name", "").strip()

            if class_name:
                cursor.execute(
                    "SELECT * FROM classes WHERE class_name = ?",
                    (class_name,),
                )

                if not cursor.fetchone():
                    cursor.execute(
                        """
                        INSERT INTO classes
                        (grade, class_name, teacher_name)
                        VALUES (?, ?, ?)
                        """,
                        (grade, class_name, teacher_name),
                    )
                    conn.commit()
                    success_msg = "✅ අලුත් පන්තිය සාර්ථකව එකතු කළා!"
                else:
                    success_msg = "⚠️ මෙම පන්තිය දැනටමත් පවතී!"

        elif action == "delete_class":
            class_id = request.form.get("class_id")
            cursor.execute("DELETE FROM classes WHERE id = ?", (class_id,))
            conn.commit()
            success_msg = "🗑️ පන්තිය පද්ධතියෙන් ඉවත් කළා!"

    cursor.execute("SELECT * FROM classes ORDER BY grade, class_name")
    classes_list = cursor.fetchall()
    conn.close()

    return render_template(
        "settings.html",
        success_msg=success_msg,
        settings=current_settings,
        classes=classes_list,
    )


@app.route("/download/attendance-excel")
def download_attendance_excel():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT index_no as 'Index Number',
               student_name as 'Student Name',
               class_name as 'Class',
               date as 'Date',
               time as 'Time',
               status as 'Status'
        FROM attendance
        ORDER BY id DESC
    """)
    records = cursor.fetchall()
    conn.close()

    data = [dict(row) for row in records]

    if not data:
        data = [{"Index Number": "", "Student Name": "No attendance records found", "Class": "", "Date": "", "Time": "", "Status": ""}]

    df = pd.DataFrame(data)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance Reports")
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="Attendance_Report_2026.xlsx",
    )


# ==========================================
# BATCH QR DOWNLOAD ROUTE
# ==========================================
@app.route("/download-batch-qrs")
def download_batch_qrs():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT index_no, student_name FROM students")
    students = cursor.fetchall()
    conn.close()

    if not students:
        return "No students found to generate QR codes!", 404

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for student in students:
            index_no = student["index_no"]
            name = student["student_name"]

            img = qrcode.make(index_no)
            img_io = io.BytesIO()
            img.save(img_io, 'PNG')
            img_io.seek(0)

            safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip()
            filename = f"{index_no}_{safe_name}.png"
            zf.writestr(filename, img_io.read())

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='All_Students_QRs.zip'
    )


init_db()

if __name__ == "__main__":
    app.run(debug=True)