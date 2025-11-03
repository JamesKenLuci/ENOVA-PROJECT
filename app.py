from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "minddue_secret"

# ✅ In-memory storage (NO DATABASE)
users = {}
tasks = []
exams = []       # ✅ New: Stores upcoming exams
next_user_id = 1
next_task_id = 1
next_exam_id = 1


# ✅ HOME PAGE (Landing Page)
@app.route("/")
def home():
    return render_template("home.html")


# ✅ ABOUT PAGE
@app.route("/about")
def about():
    return render_template("about.html")


# ✅ CONTACT PAGE
@app.route("/contact")
def contact():
    return render_template("contact.html")


# ✅ REGISTER PAGE (auto-login)
@app.route("/register", methods=["GET", "POST"])
def register():
    global next_user_id

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        users[next_user_id] = {
            "username": username,
            "password": password
        }

        session["user_id"] = next_user_id
        next_user_id += 1

        return redirect("/dashboard")

    return render_template("register.html")


# ✅ DASHBOARD PAGE
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/register")

    # Tasks for logged-in user
    user_tasks = [t for t in tasks if t["user_id"] == session["user_id"]]

    # Exams for logged-in user
    user_exams = [e for e in exams if e["user_id"] == session["user_id"]]

    # ✅ Count tasks per subject
    subject_counts = {}
    for t in user_tasks:
        subject = t["subject"]
        subject_counts[subject] = subject_counts.get(subject, 0) + 1

    return render_template(
        "dashboard.html",
        tasks=user_tasks,
        exams=user_exams,
        subject_counts=subject_counts
    )


# ✅ ADD TASK
@app.route("/add", methods=["POST"])
def add():
    global next_task_id

    if "user_id" not in session:
        return redirect("/register")

    subject = request.form["subject"]
    title = request.form["title"]
    deadline = request.form["deadline"]

    tasks.append({
        "id": next_task_id,
        "user_id": session["user_id"],
        "subject": subject,
        "title": title,
        "deadline": deadline
    })

    next_task_id += 1
    return redirect("/dashboard")


# ✅ DELETE TASK
@app.route("/delete/<int:task_id>")
def delete(task_id):
    global tasks

    tasks = [
        t for t in tasks
        if not (t["id"] == task_id and t["user_id"] == session["user_id"])
    ]
    return redirect("/dashboard")


# ✅ ✅ ADD EXAM (NEW)
@app.route("/add_exam", methods=["POST"])
def add_exam():
    global next_exam_id

    if "user_id" not in session:
        return redirect("/register")

    subject = request.form["subject"]
    exam_title = request.form["exam"]
    date = request.form["date"]

    exams.append({
        "id": next_exam_id,
        "user_id": session["user_id"],
        "subject": subject,
        "exam": exam_title,
        "date": date
    })

    next_exam_id += 1
    return redirect("/dashboard")


# ✅ LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/register")


# ✅ RUN APP
if __name__ == "__main__":
    app.run(debug=True)
