# app.py (Fixed and Updated with Registration)

# --- 0. Imports ---
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

# --- 1. Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_here'  # CRUCIAL: Change this secret key!
DATABASE = 'database.db'

# FLASK-LOGIN SETUP
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# --- 2. Database Functions ---

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the database tables (users and events)."""
    conn = get_db_connection()

    # 1. Events Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT
        )
    ''')
    # 2. Users Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')

    # Seed an Admin user (username: 'admin', password: 'adminpass')
    if not conn.execute("SELECT * FROM users WHERE role='admin'").fetchone():
        hashed_password = generate_password_hash('adminpass', method='pbkdf2:sha256')
        conn.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            ('admin', hashed_password, 'admin')
        )

    conn.commit()
    conn.close()


# --- 3. Initial DB Call ---
init_db()


# --- 4. User Model and Loader ---

class User(UserMixin):
    def __init__(self, id, username, role, password_hash):
        self.id = id
        self.username = username
        self.role = role
        self.password_hash = password_hash


@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['role'], user_data['password_hash'])
    return None


# --- 5. Authentication Routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        if not username or not password:
            flash('Both username and password are required.', 'danger')
            return redirect(url_for('register'))

        conn = get_db_connection()
        # Check if the username already exists
        existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()

        if existing_user:
            conn.close()
            flash('That username is already taken. Please choose another.', 'danger')
            return redirect(url_for('register'))

        # Hash the password and insert the new user with default 'user' role
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        conn.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            (username, hashed_password, 'user')
        )
        conn.commit()
        conn.close()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user_data and check_password_hash(user_data['password_hash'], password):
            user = load_user(user_data['id'])
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# --- 6. Event Management Routes ---

@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    events = conn.execute('SELECT * FROM events ORDER BY date, time').fetchall()
    conn.close()
    return render_template('index.html', events=events)


@app.route('/add_event', methods=('POST',))
@login_required
def add_event():
    if current_user.role != 'admin':
        flash('Permission denied. Only admins can add events.', 'warning')
        return redirect(url_for('index'))

    title = request.form['title']
    date = request.form['date']
    time = request.form['time']
    location = request.form['location']
    description = request.form['description']

    if not title or not date or not location:
        flash('Missing required fields', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO events (title, date, time, location, description) VALUES (?, ?, ?, ?, ?)',
        (title, date, time, location, description)
    )
    conn.commit()
    conn.close()
    flash('Event added successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/delete_event/<int:event_id>', methods=('POST',))
@login_required
def delete_event(event_id):
    if current_user.role != 'admin':
        flash('Permission denied. Only admins can delete events.', 'warning')
        return redirect(url_for('index'))

    conn = get_db_connection()
    conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('index'))


# --- 7. Run Server ---
if __name__ == '__main__':
    app.run(debug=True)