# --- 0. Imports ---
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

# --- 1. Setup ---
app = Flask(__name__)
# CRUCIAL: Change this secret key!
app.config['SECRET_KEY'] = 'your_super_secret_key_here'
DATABASE = 'database.db'

# FLASK-LOGIN SETUP
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'


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
    # This block ensures an admin user exists for testing CRUD operations
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
    """User model for Flask-Login."""

    def __init__(self, id, username, role, password_hash):
        self.id = id
        self.username = username
        self.role = role
        self.password_hash = password_hash


@login_manager.user_loader
def load_user(user_id):
    """Callback to reload the user object from the user ID stored in the session."""
    conn = get_db_connection()
    user_data = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_data:
        # Pass all necessary data to the User model
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
    """Handles user login."""
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
            # Redirect to the page the user was trying to access, or index
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Handles user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    # Redirecting to login after logout
    return redirect(url_for('login'))


# --- 6. Event Management Routes (Index is now here) ---

def get_event_by_id(event_id):
    """Fetches a single event by ID."""
    conn = get_db_connection()
    event = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
    conn.close()
    return event


@app.route('/')
@login_required
def index():
    """Main dashboard showing the list of scheduled events."""
    conn = get_db_connection()
    events = conn.execute('SELECT * FROM events ORDER BY date, time').fetchall()
    conn.close()
    return render_template('index.html', events=events)


@app.route('/event/<int:event_id>')
@login_required
def event_detail(event_id):
    """Displays the detail page for a single event."""
    event = get_event_by_id(event_id)
    if event is None:
        flash('Event not found.', 'danger')
        return redirect(url_for('index'))
    return render_template('event_detail.html', event=event)


@app.route('/add_event', methods=('POST',))
@login_required
def add_event():
    """Handles adding a new event (Admin only)."""
    if current_user.role != 'admin':
        flash('Permission denied. Only admins can add events.', 'warning')
        return redirect(url_for('index'))

    title = request.form['title']
    date = request.form['date']
    time = request.form['time']
    location = request.form['location']
    description = request.form.get('description', '')

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


@app.route('/edit_event/<int:event_id>', methods=('GET', 'POST'))
@login_required
def edit_event(event_id):
    """Handles editing an existing event (Admin only)."""
    event = get_event_by_id(event_id)
    if event is None:
        flash('Event not found.', 'danger')
        return redirect(url_for('index'))

    if current_user.role != 'admin':
        flash('Permission denied. Only admins can edit events.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form['title']
        date = request.form['date']
        time = request.form['time']
        location = request.form['location']
        description = request.form.get('description', '')

        if not title or not date or not location:
            flash('Missing required fields.', 'danger')
            return redirect(url_for('edit_event', event_id=event_id))

        conn = get_db_connection()
        conn.execute(
            'UPDATE events SET title = ?, date = ?, time = ?, location = ?, description = ? WHERE id = ?',
            (title, date, time, location, description, event_id)
        )
        conn.commit()
        conn.close()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('edit_event.html', event=event)


@app.route('/delete_event/<int:event_id>', methods=('POST',))
@login_required
def delete_event(event_id):
    """Handles deleting an event (Admin only)."""
    if current_user.role != 'admin':
        flash('Permission denied. Only admins can delete events.', 'warning')
        return redirect(url_for('index'))

    conn = get_db_connection()
    conn.execute('DELETE FROM events WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('index'))


# --- 7. Navigation Routes (Fixes BuildError from navigation bar) ---

@app.route('/services')
@login_required
def services():
    """Renders the Services page."""
    return render_template('services.html')


@app.route('/gallery')
@login_required
def gallery():
    """Renders the Gallery page."""
    return render_template('gallery.html')


@app.route('/packages')
@login_required
def packages():
    """Renders the Packages page."""
    return render_template('packages.html')


@app.route('/contact', methods=['GET', 'POST'])
@login_required
def contact():
    """Renders the Contact page and handles form submissions."""
    if request.method == 'POST':
        # Add actual contact form logic (e.g., save to DB, send email) here
        flash('Message received! We will be in touch shortly.', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html')


@app.route('/booking')
@login_required
def booking():
    """Renders the Booking page."""
    return render_template('booking.html')


# --- 8. Run Server ---
if __name__ == '__main__':
    app.run(debug=True)