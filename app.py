import os
import sys
import json
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

# Import the MySQL extension
from flask_mysqldb import MySQL
import MySQLdb.cursors

# --- 1. Setup ---
app = Flask(__name__)

# CRUCIAL: Set a strong secret key using environment variables in production
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your_super_secret_key_here')

# --- MYSQL CONFIGURATION ---
# IMPORTANT: Replace these values with your actual MySQL server details.
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # Enter your MySQL password here
app.config['MYSQL_DB'] = 'enova_pro_db'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'  # Returns rows as dictionaries

mysql = MySQL(app)
# --- END MYSQL CONFIGURATION ---

# FLASK-LOGIN SETUP
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'


# --- Custom Decorators ---

def admin_required(f):
    """Decorator to restrict access to administrators only."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# --- 2. Database Functions ---

def init_db():
    """Initializes the database tables (users, events, and bookings) using MySQL syntax."""

    try:
        conn = mysql.connection
        cursor = conn.cursor()
    except Exception as e:
        print("-" * 60)
        print("!!! CRITICAL ERROR: Could not get database connection for initialization. !!!")
        print("Error details:", e)
        print("Action required: Ensure the database 'enova_pro_db' exists in phpMyAdmin and server is running.")
        print("-" * 60)
        return

    # 1. Events Table (UPDATED to include 'price' for internal cost tracking)
    # NOTE: In production, use ALTER TABLE to add columns if table exists.
    # For simplicity in this development environment, this assumes the table is being created.
    # If you run into errors after the first run, drop and recreate the 'events' table.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INT PRIMARY KEY AUTO_INCREMENT,
            title VARCHAR(100) NOT NULL,
            date VARCHAR(50) NOT NULL,
            time VARCHAR(50) NOT NULL,
            location VARCHAR(255) NOT NULL,
            description TEXT,
            price DECIMAL(10, 2) NOT NULL DEFAULT 0.00  -- NEW: Estimated internal cost
        )
    ''')

    # 2. Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(10) NOT NULL DEFAULT 'user'
        )
    ''')

    # 3. Bookings Table (Already includes pricing fields from previous schema update)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            event_package VARCHAR(50),      
            preferred_dates VARCHAR(255),
            guest_count INT,
            budget VARCHAR(50),             
            base_price DECIMAL(10, 2),      
            addon_total DECIMAL(10, 2),     
            total_estimated DECIMAL(10, 2), 
            vision TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'Pending',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Seed an Admin user (username: 'admin', password: 'adminpass')
    cursor.execute("SELECT id FROM users WHERE role='admin'")
    if not cursor.fetchone():
        hashed_password = generate_password_hash('adminpass', method='pbkdf2:sha256')
        cursor.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)',
            ('admin', hashed_password, 'admin')
        )

    conn.commit()
    cursor.close()
    print("MySQL tables created and Admin user seeded (admin/adminpass).")


# --- 3. Initial DB Call ---
with app.app_context():
    init_db()


# --- 4. User Model and Loader ---

class User(UserMixin):
    """User model for Flask-Login."""

    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

    def __repr__(self):
        return f"User(id={self.id}, username='{self.username}', role='{self.role}')"


@login_manager.user_loader
def load_user(user_id):
    """Callback to reload the user object from the user ID stored in the session."""
    try:
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT id, username, role FROM users WHERE id = %s', (user_id,))
        user_data = cursor.fetchone()
        cursor.close()
        if user_data:
            return User(user_data['id'], user_data['username'], user_data['role'])
        return None
    except Exception as e:
        print(f"ERROR in load_user: {e}")
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

        try:
            cursor = mysql.connection.cursor()
            cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
            existing_user = cursor.fetchone()

            if existing_user:
                cursor.close()
                flash('That username is already taken. Please choose another.', 'danger')
                return redirect(url_for('register'))

            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

            cursor.execute(
                'INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)',
                (username, hashed_password, 'user')
            )
            mysql.connection.commit()
            cursor.close()

            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            flash('An error occurred during registration. Check MySQL connection.', 'danger')
            print(f"Error during registration: {e}")
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            cursor = mysql.connection.cursor()
            cursor.execute('SELECT id, password_hash, role FROM users WHERE username = %s', (username,))
            user_data = cursor.fetchone()
            cursor.close()

            if user_data and check_password_hash(user_data['password_hash'], password):
                user = load_user(user_data['id'])
                login_user(user)

                flash('Login successful!', 'success')

                if user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))

                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                flash('Invalid username or password.', 'danger')

        except Exception as e:
            flash('An error occurred during login. Check MySQL connection.', 'danger')
            print(f"Error during login: {e}")

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Handles user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# --- 6. Event Management Routes (Admin & Public) ---

def get_event_by_id(event_id):
    """Fetches a single event by ID."""
    try:
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM events WHERE id = %s', (event_id,))
        event = cursor.fetchone()
        cursor.close()
        return event
    except Exception as e:
        print(f"Error fetching event ID {event_id}: {e}")
        return None


def get_booking_by_id(booking_id):
    """
    NEW: Fetches a single booking by ID with all pricing fields and client username.
    Used for the view_receipt placeholder.
    """
    try:
        cursor = mysql.connection.cursor()
        query = """
        SELECT 
            b.*, 
            u.username AS client_username 
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE b.id = %s
        """
        cursor.execute(query, (booking_id,))
        booking = cursor.fetchone()
        cursor.close()
        return booking
    except Exception as e:
        print(f"Error fetching booking ID {booking_id}: {e}")
        return None


def get_event_booking_stats(event_id):
    """Fetches booking statistics (counts by status) for a specific event ID."""
    stats = {
        'total': 0,
        'Pending': 0,
        'Approved': 0,
        'Rejected': 0,
    }
    try:
        cursor = mysql.connection.cursor()
        event_title = None
        cursor.execute('SELECT title FROM events WHERE id = %s', (event_id,))
        event_data = cursor.fetchone()

        if not event_data:
            cursor.close()
            return stats

        event_title = event_data['title']

        query = """
        SELECT status, COUNT(id) AS count
        FROM bookings
        WHERE event_type = %s
        GROUP BY status
        """
        cursor.execute(query, (event_title,))
        results = cursor.fetchall()

        total = 0
        for row in results:
            status = row['status']
            count = row['count']
            if status in stats:
                stats[status] = count
            total += count
        stats['total'] = total

        cursor.close()
        return stats
    except Exception as e:
        print(f"Error fetching event booking stats for event ID {event_id}: {e}")
        return stats


@app.route('/')
@login_required
def index():
    """Main dashboard showing the list of scheduled events, or redirects admin."""
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))

    events = []
    try:
        cursor = mysql.connection.cursor()
        # Ordering by date and time (as strings) to show upcoming events first
        cursor.execute('SELECT * FROM events ORDER BY date ASC, time ASC')
        events = cursor.fetchall()
        cursor.close()
    except Exception as e:
        flash('Could not load events. Database connection failed.', 'danger')
        print(f"Error loading events for index: {e}")

    return render_template('index.html', events=events)


@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    """
    Dedicated route for the admin dashboard, showing summary statistics,
    upcoming events, and recent bookings with pricing details.
    """
    stats = {
        'total_bookings': 0,
        'pending_bookings': 0,
        'upcoming_events': 0,
        'total_users': 0
    }
    # Initialize lists
    recent_bookings = []
    events = []  # NEW: Events list for the schedule table

    # Get today's date string for comparison
    today_str = datetime.now().strftime('%Y-%m-%d')

    try:
        cursor = mysql.connection.cursor()

        # 1. Fetch Summary Stats (Existing Logic)
        cursor.execute('SELECT COUNT(id) AS total FROM bookings')
        stats['total_bookings'] = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(id) AS pending_count FROM bookings WHERE status = 'Pending'")
        stats['pending_bookings'] = cursor.fetchone()['pending_count']

        cursor.execute("SELECT COUNT(id) AS upcoming_count FROM events WHERE date >= %s", (today_str,))
        stats['upcoming_events'] = cursor.fetchone()['upcoming_count']

        cursor.execute('SELECT COUNT(id) AS user_count FROM users')
        stats['total_users'] = cursor.fetchone()['user_count']

        # 2. Fetch Upcoming Events (NEW: For the internal schedule table)
        query_events = "SELECT id, title, date, time, location, price FROM events ORDER BY date ASC, time ASC"
        cursor.execute(query_events)
        events = cursor.fetchall()

        # 3. Fetch Recent Bookings (UPDATED: Added pricing fields)
        query_bookings = """
        SELECT 
            b.id, 
            u.username AS client_username, 
            b.event_type, 
            b.event_package,
            b.preferred_dates, 
            b.status,
            b.base_price,        
            b.addon_total,       
            b.total_estimated    
        FROM 
            bookings b
        JOIN 
            users u ON b.user_id = u.id 
        ORDER BY 
            b.id DESC
        LIMIT 10;
        """
        cursor.execute(query_bookings)
        recent_bookings = cursor.fetchall()

        cursor.close()
    except Exception as e:
        flash('Could not load dashboard statistics or recent bookings. Database connection failed.', 'danger')
        print(f"Error loading admin dashboard data: {e}")

    # Pass the stats, events, AND the recent_bookings list (renamed to 'bookings' for the template)
    return render_template(
        'admin_dashboard.html',
        stats=stats,
        events=events,
        bookings=recent_bookings
    )


@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    """Admin route to view all submitted booking requests with user details."""
    bookings = []
    try:
        cursor = mysql.connection.cursor()

        # Join to fetch booking details, username, package, and pricing
        query = """
        SELECT 
            b.id, b.event_type, b.event_package, b.preferred_dates, b.guest_count, 
            b.base_price, b.addon_total, b.total_estimated, b.vision, b.status,
            u.username AS client_username
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        ORDER BY 
            CASE b.status
                WHEN 'Pending' THEN 1  -- Put pending first
                ELSE 2
            END,
            b.id DESC  -- Then order by newest ID
        """
        cursor.execute(query)
        bookings = cursor.fetchall()
        cursor.close()
    except Exception as e:
        flash('Could not load bookings. Database connection failed.', 'danger')
        print(f"Error loading admin bookings: {e}")

    return render_template('admin_bookings.html', bookings=bookings)


@app.route('/admin/booking/update/<int:booking_id>', methods=['POST'])
@admin_required
def update_booking_status(booking_id):
    """Allows admin to update the status of a booking (e.g., 'Confirmed')."""
    new_status = request.form.get('new_status')

    valid_statuses = ['Pending', 'Approved', 'Rejected']

    if new_status not in valid_statuses:
        flash('Invalid status provided.', 'danger')
        return redirect(url_for('admin_bookings'))

    try:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE bookings SET status = %s WHERE id = %s", (new_status, booking_id))
        mysql.connection.commit()
        cur.close()
        flash(f'Booking {booking_id} status updated to {new_status}.', 'success')
    except Exception as e:
        flash('Could not update booking status.', 'danger')
        print(f"Error updating booking {booking_id}: {e}")

    return redirect(url_for('admin_bookings'))


@app.route('/event/<int:event_id>')
@login_required
def event_detail(event_id):
    """Displays the detail page for a single event."""
    event = get_event_by_id(event_id)
    if event is None:
        flash('Event not found or database connection failed.', 'danger')
        return redirect(url_for('index'))

    # Fetch booking statistics for this event
    stats = get_event_booking_stats(event_id)

    return render_template('event_detail.html', event=event, stats=stats)


@app.route('/add_event', methods=('POST',))
@admin_required
def add_event():
    """
    Handles adding a new event (Admin only).
    UPDATED: Now handles 'event_title', 'event_date', 'event_time',
    'event_location', 'event_description', and 'event_price'.
    """

    # Fetching field names from the updated dashboard form
    title = request.form['event_title']
    date = request.form['event_date']
    time = request.form['event_time']
    location = request.form['event_location']
    description = request.form.get('event_description', '')
    price_str = request.form.get('event_price', '0.00')

    try:
        price = float(price_str)
    except ValueError:
        flash('Invalid price format for event cost.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if not title or not date or not time or not location:
        flash('Missing required fields', 'danger')
        return redirect(url_for('admin_dashboard'))

    try:
        cursor = mysql.connection.cursor()
        cursor.execute(
            # UPDATED: Added price field
            'INSERT INTO events (title, date, time, location, description, price) VALUES (%s, %s, %s, %s, %s, %s)',
            (title, date, time, location, description, price)
        )
        mysql.connection.commit()
        cursor.close()
        flash('Event added successfully!', 'success')
    except Exception as e:
        flash('Could not add event. Database connection failed.', 'danger')
        print(f"Error adding event: {e}")

    return redirect(url_for('admin_dashboard'))


@app.route('/edit_event/<int:event_id>', methods=('GET', 'POST'))
@admin_required
def edit_event(event_id):
    """Handles editing an existing event (Admin only)."""
    event = get_event_by_id(event_id)
    if event is None:
        flash('Event not found or database connection failed.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form['title']
        date = request.form['date']
        time = request.form['time']
        location = request.form['location']
        description = request.form.get('description', '')
        price_str = request.form.get('price', '0.00')  # NEW: Fetch price

        try:
            price = float(price_str)
        except ValueError:
            flash('Invalid price format for event cost.', 'danger')
            return redirect(url_for('edit_event', event_id=event_id))

        if not title or not date or not location:
            flash('Missing required fields.', 'danger')
            return redirect(url_for('edit_event', event_id=event_id))

        try:
            cursor = mysql.connection.cursor()
            # UPDATED: Added price field
            cursor.execute(
                'UPDATE events SET title = %s, date = %s, time = %s, location = %s, description = %s, price = %s WHERE id = %s',
                (title, date, time, location, description, price, event_id)
            )
            mysql.connection.commit()
            cursor.close()
            flash('Event updated successfully!', 'success')
        except Exception as e:
            flash('Could not update event. Database connection failed.', 'danger')
            print(f"Error updating event: {e}")

        return redirect(url_for('admin_dashboard'))

    return render_template('edit_event.html', event=event)


@app.route('/delete_event/<int:event_id>', methods=('POST',))
@admin_required
def delete_event(event_id):
    """Handles deleting an event (Admin only)."""
    try:
        cursor = mysql.connection.cursor()
        cursor.execute('DELETE FROM events WHERE id = %s', (event_id,))
        mysql.connection.commit()
        cursor.close()
        flash('Event deleted successfully!', 'success')
    except Exception as e:
        flash('Could not delete event. Database connection failed.', 'danger')
        print(f"Error deleting event: {e}")

    return redirect(url_for('admin_dashboard'))


# --- NEW: Receipt/Booking Management Routes ---

@app.route('/view_receipt/<int:booking_id>')
@admin_required
def view_receipt(booking_id):
    """Placeholder route for viewing a detailed receipt/invoice."""
    booking = get_booking_by_id(booking_id)
    if not booking:
        flash(f'Booking {booking_id} not found.', 'danger')
        return redirect(url_for('admin_dashboard'))

    flash(f"Displaying detailed receipt for Booking ID: {booking_id} (Client: {booking['client_username']}).", 'info')
    # In a full application, you would render a receipt_detail.html template here
    # For now, we redirect to prevent an immediate template error.
    return redirect(url_for('admin_dashboard'))


@app.route('/manage_booking/<int:booking_id>')
@admin_required
def manage_booking(booking_id):
    """Redirects to the admin bookings list to manage the booking status."""
    flash(f"Management required for Booking ID {booking_id}. Please use the Admin Bookings page.", 'info')
    return redirect(url_for('admin_bookings'))


# --- 7. Navigation Routes & Booking Logic ---

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
        # In a real app, save contact details to a 'contacts' table or send an email
        flash('Message received! We will be in touch shortly.', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html')


@app.route('/booking', methods=['GET', 'POST'])
@login_required
def booking():
    """Renders the Booking page and handles form submissions (POST)."""
    if request.method == 'POST':
        user_id = current_user.id
        event_type = request.form.get('event_type')
        event_package = request.form.get('event_package')
        preferred_dates = request.form.get('preferred_dates')
        guest_count = request.form.get('guest_count')

        # --- Pricing Fields (These come from hidden/calculated fields in the booking form) ---
        base_price = request.form.get('base_price_hidden', 0)
        addon_total = request.form.get('addon_total_hidden', 0)

        try:
            total_estimated = float(base_price) + float(addon_total)
        except ValueError:
            total_estimated = 0.0
        # --- End Pricing Fields ---

        budget = None  # Assuming this is not used/set in the form anymore
        base_vision = request.form.get('vision')

        # --- Handle Dynamic Fields and combine into vision ---
        dynamic_details = []

        # Helper to safely append details
        def add_detail(label, key):
            value = request.form.get(key)
            if value and value.strip():
                dynamic_details.append(f"{label}: {value}")

        # Note: These keys must match the form fields in your 'booking.html'
        add_detail("Age", 'birthday_age')
        add_detail("Theme", 'birthday_theme')
        add_detail("Cake", 'birthday_cake')

        add_detail("Venue Type", 'wedding_venue_type')
        add_detail("Ideal Month", 'wedding_months')

        add_detail("Goal", 'gala_purpose')
        add_detail("Dress Code", 'gala_dress_code')

        add_detail("Product", 'product_name')
        add_detail("Audience", 'launch_audience')

        add_detail("Other Details", 'other_details')

        # Combine base vision and dynamic details
        full_vision_list = []
        if base_vision and base_vision.strip(): full_vision_list.append(f"Client Vision: {base_vision}")
        if dynamic_details:
            full_vision_list.append("\n--- Event-Specific Details ---\n" + "\n".join(dynamic_details))

        final_vision = "\n\n".join(filter(None, full_vision_list))
        # --- End Dynamic Fields Handling ---

        if not event_type or not event_package:
            flash('Please select a valid event type and a planning package.', 'danger')
            return redirect(url_for('booking'))

        # Save to database (using MySQL)
        try:
            cursor = mysql.connection.cursor()
            cursor.execute(
                """
                INSERT INTO bookings 
                (user_id, event_type, event_package, preferred_dates, guest_count, budget, base_price, addon_total, total_estimated, vision) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, event_type, event_package, preferred_dates, guest_count, budget, base_price, addon_total,
                 total_estimated, final_vision)
            )
            mysql.connection.commit()
            cursor.close()

            flash('Your booking request has been submitted successfully! We will contact you soon.', 'success')
            return redirect(url_for('index'))

        except Exception as e:
            flash(
                'An error occurred during submission to MySQL. Please check your database is running and the schema is updated.',
                'danger')
            print(f"Error during booking submission: {e}")
            return redirect(url_for('booking'))

    # GET request handler (Renders the booking form)
    return render_template('booking.html')


# --- 8. Run Server ---
if __name__ == '__main__':
    print(f"Flask app configured to use MySQL database: {app.config['MYSQL_DB']} at {app.config['MYSQL_HOST']}")
    app.run(debug=True)