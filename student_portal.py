import sqlite3
from flask import Flask, render_template, request

app = Flask(__name__)

# Leave Request Route (Public Facing)
@app.route('/', methods=['GET', 'POST'])
def request_leave():
    success_msg = None
    if request.method == 'POST':
        index_no = request.form.get('index_no')
        date = request.form.get('date')
        reason = request.form.get('reason')
        
        # Main ඇප් එකේ Database එකටම කනෙක්ට් වීම
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # ශිෂ්‍යයාගේ නම හොයාගන්නවා
        cursor.execute("SELECT student_name FROM students WHERE index_no = ?", (index_no,))
        res = cursor.fetchone()
        student_name = res[0] if res else "Unknown Student"
        
        # නිවාඩුව සේව් කිරීම
        cursor.execute('''
            INSERT INTO leave_requests (index_no, student_name, date, reason)
            VALUES (?, ?, ?, ?)
        ''', (index_no, student_name, date, reason))
        
        conn.commit()
        conn.close()
        
        success_msg = "✅ ඔබගේ නිවාඩු දැනුවත් කිරීම සාර්ථකයි! ආයතනය ඒ බව සටහන් කරගන්නා ලදී."
        
    return render_template('leave_form.html', success_msg=success_msg)

if __name__ == '__main__':
    # මේක වෙනම Port එකක (5001) රන් වෙනවා, ඒ නිසා Main ඇප් එකත් එක්ක ගැටෙන්නේ නෑ
    app.run(debug=True, port=5001)