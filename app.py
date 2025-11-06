from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

app = Flask(__name__)
app.config['SECRET_KEY'] = 'minddue_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ==========================================================
# DATABASE MODEL
# ==========================================================
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(100))
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    priority = db.Column(db.String(20), default="Medium")
    completed = db.Column(db.Boolean, default=False)


# ==========================================================
# DASHBOARD
# ==========================================================
@app.route('/')
def index():
    now = datetime.now(timezone.utc)  # ✅ timezone-aware datetime

    total = Task.query.count()
    done = Task.query.filter_by(completed=True).count()

    overdue = Task.query.filter(
        Task.due_date < now,
        Task.completed == False,
        Task.due_date != None
    ).count()

    upcoming = Task.query.filter(
        Task.due_date >= now
    ).order_by(Task.due_date).limit(5).all()

    not_done = Task.query.filter_by(completed=False).order_by(Task.due_date).limit(5).all()

    return render_template(
        'index.html',
        total=total,
        done=done,
        overdue=overdue,
        upcoming=upcoming,
        not_done=not_done
    )


# ==========================================================
# NEW TASK
# ==========================================================
@app.route('/task/new', methods=['GET', 'POST'])
def new_task():
    if request.method == 'POST':
        title = request.form['title']
        subject = request.form.get('subject')
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        priority = request.form.get('priority', 'Medium')

        # ✅ Convert ISO date to timezone-aware datetime
        due_dt = datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc) if due_date else None

        task = Task(
            title=title,
            subject=subject,
            description=description,
            due_date=due_dt,
            priority=priority
        )
        db.session.add(task)
        db.session.commit()

        flash("Task added successfully!", "success")
        return redirect(url_for('tasks'))

    return render_template('task_form.html', task=None)


# ==========================================================
# EDIT TASK
# ==========================================================
@app.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)

    if request.method == 'POST':
        task.title = request.form['title']
        task.subject = request.form.get('subject')
        task.description = request.form.get('description')
        due_date = request.form.get('due_date')
        task.priority = request.form.get('priority', 'Medium')
        task.completed = (request.form.get('completed') == 'on')

        # ✅ Proper handling of date
        task.due_date = (
            datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc)
            if due_date else None
        )

        db.session.commit()
        flash("Task updated!", "success")
        return redirect(url_for('tasks'))

    return render_template('task_form.html', task=task)


# ==========================================================
# DELETE TASK
# ==========================================================
@app.route('/task/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)

    db.session.delete(task)
    db.session.commit()

    flash("Task deleted.", "info")
    return redirect(url_for('tasks'))


# ==========================================================
# TASK LIST PAGE
# ==========================================================
@app.route('/tasks')
def tasks():
    all_tasks = Task.query.order_by(Task.due_date).all()
    return render_template('tasks.html', tasks=all_tasks)


# ==========================================================
# CALENDAR PAGE
# ==========================================================
@app.route('/calendar')
def calendar_view():
    tasks = Task.query.filter(Task.due_date != None).order_by(Task.due_date).all()
    return render_template('calendar.html', tasks=tasks)


# ==========================================================
# ABOUT PAGE
# ==========================================================
@app.route('/about')
def about():
    return render_template('about.html')


# ==========================================================
# CONTACT PAGE
# ==========================================================
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
    app.run(debug=True)
