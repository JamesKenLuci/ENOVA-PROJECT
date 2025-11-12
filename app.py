from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'minddue_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================================
# DATABASE MODELS
# ==========================================================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(100))
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    priority = db.Column(db.String(20), default="Medium")
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # ✅ each task belongs to a user


# ==========================================================
# AUTH ROUTES (REGISTER / LOGIN / LOGOUT)
# ==========================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()

        if existing_user:
            flash("Username or email already exists!", "danger")
            return redirect(url_for('register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


# ==========================================================
# DASHBOARD (Require Login)
# ==========================================================
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    now = datetime.now(timezone.utc)
    user_id = session['user_id']

    total = Task.query.filter_by(user_id=user_id).count()
    done = Task.query.filter_by(user_id=user_id, completed=True).count()
    overdue = Task.query.filter(
        Task.user_id == user_id,
        Task.due_date < now,
        Task.completed == False,
        Task.due_date != None
    ).count()

    upcoming = Task.query.filter(
        Task.user_id == user_id,
        Task.due_date >= now
    ).order_by(Task.due_date).limit(5).all()

    not_done = Task.query.filter_by(user_id=user_id, completed=False).order_by(Task.due_date).limit(5).all()

    return render_template(
        'index.html',
        total=total,
        done=done,
        overdue=overdue,
        upcoming=upcoming,
        not_done=not_done
    )


# ==========================================================
# TASK ROUTES (Require Login)
# ==========================================================
@app.route('/task/new', methods=['GET', 'POST'])
def new_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        subject = request.form.get('subject')
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        priority = request.form.get('priority', 'Medium')

        due_dt = datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc) if due_date else None

        task = Task(
            title=title,
            subject=subject,
            description=description,
            due_date=due_dt,
            priority=priority,
            user_id=session['user_id']
        )
        db.session.add(task)
        db.session.commit()

        flash("Task added successfully!", "success")
        return redirect(url_for('tasks'))

    return render_template('task_form.html', task=None)


@app.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
def edit_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    task = Task.query.get_or_404(task_id)
    if task.user_id != session['user_id']:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('tasks'))

    if request.method == 'POST':
        task.title = request.form['title']
        task.subject = request.form.get('subject')
        task.description = request.form.get('description')
        due_date = request.form.get('due_date')
        task.priority = request.form.get('priority', 'Medium')
        task.completed = (request.form.get('completed') == 'on')

        task.due_date = datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc) if due_date else None

        db.session.commit()
        flash("Task updated!", "success")
        return redirect(url_for('tasks'))

    return render_template('task_form.html', task=task)


@app.route('/task/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    task = Task.query.get_or_404(task_id)
    if task.user_id != session['user_id']:
        flash("Unauthorized delete attempt!", "danger")
        return redirect(url_for('tasks'))

    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for('tasks'))


@app.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    all_tasks = Task.query.filter_by(user_id=user_id).order_by(Task.due_date).all()
    return render_template('tasks.html', tasks=all_tasks)


# ==========================================================
# OTHER PAGES
# ==========================================================
@app.route('/calendar')
def calendar_view():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    tasks = Task.query.filter(
        Task.user_id == user_id,
        Task.due_date != None
    ).order_by(Task.due_date).all()
    return render_template('calendar.html', tasks=tasks)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash("Message received! Thank you.", "success")
        return redirect(url_for('contact'))
    return render_template('contact.html')


# ==========================================================
# RUN APP
# ==========================================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
