from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_file
import sqlite3, io, pandas as pd
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
DB = 'helpdesk.db'


# ---------------------------------------------------
# DATABASE SETUP
# ---------------------------------------------------
def init_db():
    with sqlite3.connect(DB) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE,
                        password TEXT,
                        role TEXT,
                        created_at TEXT
                      )''')
        con.execute('''CREATE TABLE IF NOT EXISTS tickets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        description TEXT,
                        status TEXT,
                        created_by INTEGER,
                        assigned_to INTEGER,
                        created_at TEXT,
                        FOREIGN KEY(created_by) REFERENCES users(id),
                        FOREIGN KEY(assigned_to) REFERENCES users(id)
                      )''')
    with sqlite3.connect(DB) as con:
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
        if cur.fetchone()[0] == 0:
            pw = generate_password_hash('admin123')
            con.execute("INSERT INTO users (username,password,role,created_at) VALUES (?,?,?,?)",
                        ('admin', pw, 'admin', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            con.commit()
init_db()


# ---------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------
def query_db(query, args=(), one=False):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    con.commit()
    con.close()
    return (rv[0] if rv else None) if one else rv

def current_user():
    if 'user_id' not in session:
        return None
    return query_db("SELECT id, username, role FROM users WHERE id=?", (session['user_id'],), one=True)

# ---------------------------------------------------
# AUTH DECORATORS
# ---------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in.", "warning")
                return redirect(url_for('login'))
            user = query_db("SELECT role FROM users WHERE id=?", (session['user_id'],), one=True)
            if not user or user[0] not in allowed_roles:
                flash("You do not have permission.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ---------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form.get('role', 'user')
        if not username or not password:
            flash("Username and password required.", "warning")
            return redirect(url_for('register'))
        hashed = generate_password_hash(password)
        try:
            with sqlite3.connect(DB) as con:
                con.execute("INSERT INTO users (username,password,role,created_at) VALUES (?,?,?,?)",
                            (username, hashed, role, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                con.commit()
            flash("Registered successfully.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger")
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = query_db("SELECT id,password FROM users WHERE username=?", (username,), one=True)
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            flash("Logged in successfully.", "success")
            return redirect(url_for('dashboard'))
        flash("Invalid credentials.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for('login'))


# ---------------------------------------------------
# DASHBOARD
# ---------------------------------------------------
@app.route('/')
@login_required
def dashboard():
    user = current_user()
    if user[2] in ('admin', 'technician'):
        tickets = query_db("""SELECT t.id,t.title,t.description,t.status,t.created_at,u.username,a.username
                              FROM tickets t
                              LEFT JOIN users u ON t.created_by=u.id
                              LEFT JOIN users a ON t.assigned_to=a.id
                              ORDER BY t.id DESC""")
    else:
        tickets = query_db("""SELECT t.id,t.title,t.description,t.status,t.created_at,u.username,a.username
                              FROM tickets t
                              LEFT JOIN users u ON t.created_by=u.id
                              LEFT JOIN users a ON t.assigned_to=a.id
                              WHERE t.created_by=? ORDER BY t.id DESC""", (user[0],))

    open_count = query_db("SELECT COUNT(*) FROM tickets WHERE status='Open'", one=True)[0]
    progress_count = query_db("SELECT COUNT(*) FROM tickets WHERE status='In Progress'", one=True)[0]
    closed_count = query_db("SELECT COUNT(*) FROM tickets WHERE status='Closed'", one=True)[0]
    users = query_db("SELECT id,username FROM users")
    return render_template('dashboard.html', tickets=tickets,
                           open_count=open_count, progress_count=progress_count,
                           closed_count=closed_count, users=users, user=user)


# ---------------------------------------------------
# TICKET ROUTES
# ---------------------------------------------------
@app.route('/new', methods=['GET', 'POST'])
@login_required
def new_ticket():
    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['description']
        assignee = request.form.get('assigned_to') or None
        with sqlite3.connect(DB) as con:
            con.execute("""INSERT INTO tickets
                           (title,description,status,created_by,assigned_to,created_at)
                           VALUES (?,?,?,?,?,?)""",
                        (title, desc, 'Open', session['user_id'],
                         assignee if assignee else None,
                         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            con.commit()
        flash("Ticket created.", "success")
        return redirect(url_for('dashboard'))
    users = query_db("SELECT id,username FROM users")
    return render_template('new_ticket.html', users=users, user=current_user())

@app.route('/update_status', methods=['POST'])
@login_required
def update_status():
    ticket_id = request.form['id']
    new_status = request.form['status']
    user = current_user()
    ticket = query_db("SELECT created_by FROM tickets WHERE id=?", (ticket_id,), one=True)
    if not ticket:
        return jsonify({'success': False, 'error': 'Ticket not found'}), 404
    if user[2] in ('admin', 'technician') or user[0] == ticket[0]:
        with sqlite3.connect(DB) as con:
            con.execute("UPDATE tickets SET status=? WHERE id=?", (new_status, ticket_id))
            con.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Permission denied'}), 403

@app.route('/assign_ticket', methods=['POST'])
@role_required('admin', 'technician')
def assign_ticket():
    ticket_id = request.form['ticket_id']
    assigned_to = request.form.get('assigned_to') or None
    with sqlite3.connect(DB) as con:
        con.execute("UPDATE tickets SET assigned_to=? WHERE id=?",
                    (assigned_to if assigned_to else None, ticket_id))
        con.commit()
    flash("Ticket assigned.", "success")
    return redirect(url_for('dashboard'))


# ---------------------------------------------------
# EXPORT ROUTES
# ---------------------------------------------------
@app.route('/export/csv')
@role_required('admin', 'technician')
def export_csv():
    con = sqlite3.connect(DB)
    df = pd.read_sql_query("""
        SELECT t.id,t.title,t.description,t.status,t.created_at,
               u.username AS created_by,a.username AS assigned_to
        FROM tickets t
        LEFT JOIN users u ON t.created_by=u.id
        LEFT JOIN users a ON t.assigned_to=a.id
        ORDER BY t.id DESC
    """, con)
    con.close()
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()),
                     mimetype='text/csv',
                     as_attachment=True,
                     download_name='tickets.csv')

@app.route('/export/xlsx')
@role_required('admin', 'technician')
def export_excel():
    con = sqlite3.connect(DB)
    df = pd.read_sql_query("""
        SELECT t.id,t.title,t.description,t.status,t.created_at,
               u.username AS created_by,a.username AS assigned_to
        FROM tickets t
        LEFT JOIN users u ON t.created_by=u.id
        LEFT JOIN users a ON t.assigned_to=a.id
        ORDER BY t.id DESC
    """, con)
    con.close()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Tickets')
    output.seek(0)
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name='tickets.xlsx')


# ---------------------------------------------------
# USER MANAGEMENT (ADMIN)
# ---------------------------------------------------
@app.route('/manage_users')
@role_required('admin')
def manage_users():
    users = query_db("SELECT id,username,role,created_at FROM users ORDER BY id")
    return render_template('manage_users.html', users=users, user=current_user())

@app.route('/change_role', methods=['POST'])
@role_required('admin')
def change_role():
    user_id = request.form['user_id']
    new_role = request.form['role']
    with sqlite3.connect(DB) as con:
        con.execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))
        con.commit()
    flash("Role updated.", "success")
    return redirect(url_for('manage_users'))


# ---------------------------------------------------
# RUN
# ---------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
