from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, send_file, Response
from pymongo import MongoClient
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from bson import ObjectId
import ssl



app = Flask(__name__, static_folder='statics', template_folder='templates')
app.secret_key = os.urandom(24)

# MongoDB Atlas connection
MONGO_URI = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI") or (
    "mongodb+srv://college_erp:clg_erp@cluster0.l3g4xjz.mongodb.net/"
    "college_erp_db?retryWrites=true&w=majority"
)

client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsAllowInvalidCertificates=True   # IMPORTANT for campus WiFi
)

db = client["college_erp_db"]
# Collections
users_db = client["users_db"]
students_collection = users_db["students"]
teachers_collection = users_db["teachers"]
admins_collection = users_db["admins"]
users_collection = db["users"]
attendance_collection = db["attendance"]
grades_collection = db["grades"]
notes_collection = db["notes"]
syllabus_collection = db["syllabus"]
notifications_collection = db["notifications"]
events_collection = db["events"]
courses_collection = db["courses"]
settings_collection = db["settings"]
timetable_collection = db["timetable"]
classes_collection = db["classes"]

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'student_login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["_id"])
        self.username = user_data["username"]
        self.role = user_data["role"]
        self.name = user_data.get("name", "")
        self.user_data = user_data

@login_manager.user_loader
def load_user(user_id):
    for col, role in (
        (admins_collection, "admin"),
        (teachers_collection, "teacher"),
        (students_collection, "student"),
        (users_collection, None),
    ):
        try:
            doc = col.find_one({"_id": ObjectId(user_id)})
        except Exception:
            doc = None
        if doc:
            if role and not doc.get("role"):
                doc["role"] = role
            return User(doc)
    return None

# -------------------------------
# Authentication Routes
# -------------------------------
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login/student', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = students_collection.find_one({"username": username})
        if not user:
            user = users_collection.find_one({"username": username, "role": "student"})
        if user and check_password_hash(user["password"], password):
            user_obj = User(user)
            login_user(user_obj)
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('st_login.html')

@app.route('/login/teacher', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = teachers_collection.find_one({"username": username})
        if not user:
            user = users_collection.find_one({"username": username, "role": "teacher"})
        if user and check_password_hash(user["password"], password):
            user_obj = User(user)
            login_user(user_obj)
            return redirect(url_for('teacher_dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('teach_login.html')

@app.route('/login/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = admins_collection.find_one({"username": username})
        if not user:
            user = users_collection.find_one({"username": username, "role": "admin"})
        if user and check_password_hash(user["password"], password):
            user_obj = User(user)
            login_user(user_obj)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('admin_login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# -------------------------------
# Dashboard Routes
# -------------------------------
@app.route('/dashboard/admin')
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    return render_template('admin_dashboard.html', user=current_user)

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    role = request.args.get('role')
    q = request.args.get('q', '').strip()
    users = []
    if role == 'admin':
        users = list(admins_collection.find({}))
        for u in users:
            u.setdefault('role', 'admin')
    elif role == 'teacher':
        users = list(teachers_collection.find({}))
        for u in users:
            u.setdefault('role', 'teacher')
    elif role == 'student':
        users = list(students_collection.find({}))
        for u in users:
            u.setdefault('role', 'student')
    else:
        admins = list(admins_collection.find({}))
        for u in admins:
            u.setdefault('role', 'admin')
        teachers = list(teachers_collection.find({}))
        for u in teachers:
            u.setdefault('role', 'teacher')
        students = list(students_collection.find({}))
        for u in students:
            u.setdefault('role', 'student')
        users = admins + teachers + students
    if q:
        users = [u for u in users if q.lower() in (u.get('username','')+u.get('name','')+u.get('email','')).lower()]
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/create', methods=['POST'])
@login_required
def admin_users_create():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    username = request.form.get('username','').strip()
    password = request.form.get('password','').strip()
    role = request.form.get('role','').strip()
    name = request.form.get('name','').strip()
    email = request.form.get('email','').strip()
    if not all([username, password, role, name]):
        flash('Missing required fields', 'danger')
        return redirect(url_for('admin_users'))
    if admins_collection.find_one({"username": username}) or teachers_collection.find_one({"username": username}) or students_collection.find_one({"username": username}):
        flash('Username already exists', 'danger')
        return redirect(url_for('admin_users'))
    doc = {
        "username": username,
        "password": generate_password_hash(password),
        "role": role,
        "name": name,
        "email": email,
        "created_at": datetime.now()
    }
    if role == 'admin':
        admins_collection.insert_one(doc)
    elif role == 'teacher':
        teachers_collection.insert_one(doc)
    elif role == 'student':
        students_collection.insert_one(doc)
    flash('User created', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<user_id>/edit', methods=['POST'])
@login_required
def admin_users_edit(user_id):
    if current_user.role != "admin":
        return redirect(url_for('home'))
    name = request.form.get('name','').strip()
    email = request.form.get('email','').strip()
    role = request.form.get('role','').strip()
    password = request.form.get('password','').strip()
    update = {"name": name, "email": email, "role": role, "updated_at": datetime.now()}
    if password:
        update["password"] = generate_password_hash(password)
    src = None
    current_doc = admins_collection.find_one({"_id": ObjectId(user_id)})
    if current_doc:
        src = 'admin'
    else:
        current_doc = teachers_collection.find_one({"_id": ObjectId(user_id)})
        if current_doc:
            src = 'teacher'
        else:
            current_doc = students_collection.find_one({"_id": ObjectId(user_id)})
            if current_doc:
                src = 'student'
    if not current_doc:
        current_doc = users_collection.find_one({"_id": ObjectId(user_id)})
        src = current_doc.get('role') if current_doc else None
    if not current_doc:
        flash('User not found', 'danger')
        return redirect(url_for('admin_users'))
    if role == src or role is None:
        if src == 'admin':
            admins_collection.update_one({"_id": ObjectId(user_id)}, {"$set": update})
        elif src == 'teacher':
            teachers_collection.update_one({"_id": ObjectId(user_id)}, {"$set": update})
        elif src == 'student':
            students_collection.update_one({"_id": ObjectId(user_id)}, {"$set": update})
        else:
            users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": update})
    else:
        new_doc = current_doc.copy()
        new_doc.update(update)
        new_doc["_id"] = ObjectId(user_id)
        if src == 'admin':
            admins_collection.delete_one({"_id": ObjectId(user_id)})
        elif src == 'teacher':
            teachers_collection.delete_one({"_id": ObjectId(user_id)})
        elif src == 'student':
            students_collection.delete_one({"_id": ObjectId(user_id)})
        else:
            users_collection.delete_one({"_id": ObjectId(user_id)})
        if role == 'admin':
            admins_collection.insert_one(new_doc)
        elif role == 'teacher':
            teachers_collection.insert_one(new_doc)
        elif role == 'student':
            students_collection.insert_one(new_doc)
    flash('User updated', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<user_id>/delete', methods=['POST'])
@login_required
def admin_users_delete(user_id):
    if current_user.role != "admin":
        return redirect(url_for('home'))
    if str(current_user.id) == user_id:
        flash('Cannot delete current admin', 'danger')
        return redirect(url_for('admin_users'))
    if admins_collection.delete_one({"_id": ObjectId(user_id)}).deleted_count:
        pass
    elif teachers_collection.delete_one({"_id": ObjectId(user_id)}).deleted_count:
        pass
    elif students_collection.delete_one({"_id": ObjectId(user_id)}).deleted_count:
        pass
    else:
        users_collection.delete_one({"_id": ObjectId(user_id)})
    flash('User deleted', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/faculty')
@login_required
def admin_faculty():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    teachers = list(teachers_collection.find({}))
    for t in teachers:
        t.setdefault('role', 'teacher')
    return render_template('admin_faculty.html', teachers=teachers)

@app.route('/admin/faculty/create', methods=['POST'])
@login_required
def admin_faculty_create():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    username = request.form.get('username','').strip()
    password = request.form.get('password','').strip()
    name = request.form.get('name','').strip()
    email = request.form.get('email','').strip()
    subjects = [s.strip() for s in request.form.get('subjects','').split(',') if s.strip()]
    classes = [c.strip() for c in request.form.get('classes','').split(',') if c.strip()]
    if not all([username, password, name]):
        flash('Missing required fields', 'danger')
        return redirect(url_for('admin_faculty'))
    if admins_collection.find_one({"username": username}) or teachers_collection.find_one({"username": username}) or students_collection.find_one({"username": username}):
        flash('Username already exists', 'danger')
        return redirect(url_for('admin_faculty'))
    teachers_collection.insert_one({
        "username": username,
        "password": generate_password_hash(password),
        "role": "teacher",
        "name": name,
        "email": email,
        "subjects": subjects,
        "classes": classes,
        "created_at": datetime.now()
    })
    flash('Teacher created', 'success')
    return redirect(url_for('admin_faculty'))

@app.route('/admin/faculty/<teacher_id>/assign', methods=['POST'])
@login_required
def admin_faculty_assign(teacher_id):
    if current_user.role != "admin":
        return redirect(url_for('home'))
    subjects = request.form.get('subjects','').strip()
    classes = request.form.get('classes','').strip()
    subs = [s.strip() for s in subjects.split(',') if s.strip()]
    cls = [c.strip() for c in classes.split(',') if c.strip()]
    teachers_collection.update_one({"_id": ObjectId(teacher_id)}, {"$set": {"subjects": subs, "classes": cls, "updated_at": datetime.now()}})
    flash('Assignments updated', 'success')
    return redirect(url_for('admin_faculty'))

@app.route('/admin/students')
@login_required
def admin_students():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    class_name = request.args.get('class')
    query = {}
    if class_name:
        query["class"] = class_name
    students = list(students_collection.find(query))
    for s in students:
        s.setdefault('role', 'student')
    return render_template('admin_students.html', students=students)

@app.route('/admin/students/create', methods=['POST'])
@login_required
def admin_students_create():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    username = request.form.get('username','').strip()
    password = request.form.get('password','').strip()
    name = request.form.get('name','').strip()
    email = request.form.get('email','').strip()
    class_name = request.form.get('class','').strip()
    roll_number = request.form.get('roll_number','').strip()
    if not all([username, password, name, class_name]):
        flash('Missing required fields', 'danger')
        return redirect(url_for('admin_students'))
    if admins_collection.find_one({"username": username}) or teachers_collection.find_one({"username": username}) or students_collection.find_one({"username": username}):
        flash('Username already exists', 'danger')
        return redirect(url_for('admin_students'))
    students_collection.insert_one({
        "username": username,
        "password": generate_password_hash(password),
        "role": "student",
        "name": name,
        "email": email,
        "class": class_name,
        "roll_number": roll_number,
        "created_at": datetime.now()
    })
    flash('Student created', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/students/<student_id>/edit', methods=['POST'])
@login_required
def admin_students_edit(student_id):
    if current_user.role != "admin":
        return redirect(url_for('home'))
    name = request.form.get('name','').strip()
    email = request.form.get('email','').strip()
    class_name = request.form.get('class','').strip()
    roll_number = request.form.get('roll_number','').strip()
    password = request.form.get('password','').strip()
    update = {"name": name, "email": email, "class": class_name, "roll_number": roll_number, "updated_at": datetime.now()}
    if password:
        update["password"] = generate_password_hash(password)
    students_collection.update_one({"_id": ObjectId(student_id)}, {"$set": update})
    flash('Student updated', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/students/<student_id>/delete', methods=['POST'])
@login_required
def admin_students_delete(student_id):
    if current_user.role != "admin":
        return redirect(url_for('home'))
    students_collection.delete_one({"_id": ObjectId(student_id)})
    flash('Student deleted', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/courses')
@login_required
def admin_courses():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    courses = list(courses_collection.find({}))
    teachers = list(teachers_collection.find({}))
    return render_template('admin_courses.html', courses=courses, teachers=teachers)

@app.route('/admin/courses/create', methods=['POST'])
@login_required
def admin_courses_create():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    code = request.form.get('code','').strip()
    name = request.form.get('name','').strip()
    department = request.form.get('department','').strip()
    credits = request.form.get('credits','').strip()
    semester = request.form.get('semester','').strip()
    description = request.form.get('description','').strip()
    instructors = request.form.getlist('instructors')
    if not all([code, name, department, credits, semester]):
        flash('Missing required fields', 'danger')
        return redirect(url_for('admin_courses'))
    if courses_collection.find_one({"code": code}):
        flash('Course code exists', 'danger')
        return redirect(url_for('admin_courses'))
    courses_collection.insert_one({
        "code": code,
        "name": name,
        "department": department,
        "credits": int(credits),
        "semester": semester,
        "description": description,
        "instructors": [ObjectId(t) for t in instructors if t],
        "created_at": datetime.now()
    })
    flash('Course created', 'success')
    return redirect(url_for('admin_courses'))

@app.route('/admin/courses/<course_id>/edit', methods=['POST'])
@login_required
def admin_courses_edit(course_id):
    if current_user.role != "admin":
        return redirect(url_for('home'))
    name = request.form.get('name','').strip()
    department = request.form.get('department','').strip()
    credits = request.form.get('credits','').strip()
    semester = request.form.get('semester','').strip()
    description = request.form.get('description','').strip()
    instructors = request.form.getlist('instructors')
    update = {
        "name": name,
        "department": department,
        "credits": int(credits) if credits else None,
        "semester": semester,
        "description": description,
        "instructors": [ObjectId(t) for t in instructors if t],
        "updated_at": datetime.now()
    }
    if update["credits"] is None:
        update.pop("credits")
    courses_collection.update_one({"_id": ObjectId(course_id)}, {"$set": update})
    flash('Course updated', 'success')
    return redirect(url_for('admin_courses'))

@app.route('/admin/courses/<course_id>/delete', methods=['POST'])
@login_required
def admin_courses_delete(course_id):
    if current_user.role != "admin":
        return redirect(url_for('home'))
    courses_collection.delete_one({"_id": ObjectId(course_id)})
    flash('Course deleted', 'success')
    return redirect(url_for('admin_courses'))

@app.route('/admin/reports')
@login_required
def admin_reports():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    total_students = students_collection.count_documents({})
    total_teachers = teachers_collection.count_documents({})
    total_admins = admins_collection.count_documents({})
    total_courses = courses_collection.count_documents({})
    attendance_count = attendance_collection.count_documents({})
    grades_count = grades_collection.count_documents({})
    notes_count = notes_collection.count_documents({})
    syllabus_count = syllabus_collection.count_documents({})
    stats = {
        "students": total_students,
        "teachers": total_teachers,
        "admins": total_admins,
        "courses": total_courses,
        "attendance": attendance_count,
        "grades": grades_count,
        "notes": notes_count,
        "syllabus": syllabus_count
    }
    return render_template('admin_reports.html', stats=stats)

@app.route('/admin/reports/export/<export_type>')
@login_required
def admin_reports_export(export_type):
    if current_user.role != "admin":
        return redirect(url_for('home'))
    if export_type == 'users':
        rows = []
        for r in admins_collection.find({}):
            r.setdefault('role', 'admin')
            rows.append(r)
        for r in teachers_collection.find({}):
            r.setdefault('role', 'teacher')
            rows.append(r)
        for r in students_collection.find({}):
            r.setdefault('role', 'student')
            rows.append(r)
        output = 'username,name,email,role\n'
        for r in rows:
            output += f"{r.get('username','')},{r.get('name','')},{r.get('email','')},{r.get('role','')}\n"
        resp = Response(output, mimetype='text/csv')
        resp.headers['Content-Disposition'] = 'attachment; filename=users.csv'
        return resp
    if export_type == 'courses':
        rows = list(courses_collection.find({}))
        output = 'code,name,department,credits,semester\n'
        for r in rows:
            output += f"{r.get('code','')},{r.get('name','')},{r.get('department','')},{r.get('credits','')},{r.get('semester','')}\n"
        resp = Response(output, mimetype='text/csv')
        resp.headers['Content-Disposition'] = 'attachment; filename=courses.csv'
        return resp
    if export_type == 'classes':
        rows = list(classes_collection.find({}))
        output = 'division,department,year\n'
        for r in rows:
            output += f"{r.get('division','')},{r.get('department','')},{r.get('year','')}\n"
        resp = Response(output, mimetype='text/csv')
        resp.headers['Content-Disposition'] = 'attachment; filename=classes.csv'
        return resp
    flash('Unsupported export type', 'danger')
    return redirect(url_for('admin_reports'))

@app.route('/admin/classes')
@login_required
def admin_classes():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    items = list(classes_collection.find({}))
    return render_template('admin_classes.html', classes=items)

@app.route('/admin/classes/create', methods=['POST'])
@login_required
def admin_classes_create():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    division = request.form.get('division','').strip()
    department = request.form.get('department','').strip()
    year = request.form.get('year','').strip()
    if not division:
        flash('Division is required', 'danger')
        return redirect(url_for('admin_classes'))
    if classes_collection.find_one({"division": division, "department": department, "year": year}):
        flash('Class with this division/department/year already exists', 'danger')
        return redirect(url_for('admin_classes'))
    classes_collection.insert_one({
        "division": division,
        "department": department,
        "year": year,
        "created_at": datetime.now()
    })
    flash('Class created', 'success')
    return redirect(url_for('admin_classes'))

@app.route('/admin/timetable', methods=['GET'])
@login_required
def admin_timetable():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    selected_department = request.args.get('department','').strip()
    selected_year = request.args.get('year','').strip()
    selected_div = request.args.get('division','').strip()
    classes = list(classes_collection.find({}, {"department":1, "year":1, "division":1}))
    departments = sorted({c.get('department','') for c in classes if c.get('department')})
    years = sorted({c.get('year','') for c in classes if c.get('year')})
    divisions = sorted({c.get('division') for c in classes if c.get('department') == selected_department and c.get('year') == selected_year and c.get('division')})
    timetable = None
    if selected_department and selected_year and selected_div:
        label = f"{selected_year} - {selected_department} {selected_div}"
        timetable = timetable_collection.find_one({"class": label})
    return render_template('admin_timetable.html', departments=departments, years=years, divisions=divisions, timetable=timetable, selected_department=selected_department, selected_year=selected_year, selected_div=selected_div)

@app.route('/admin/timetable/update_slots', methods=['POST'])
@login_required
def admin_timetable_update_slots():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    department = request.form.get('department','').strip()
    year = request.form.get('year','').strip()
    division = request.form.get('division','').strip()
    slots_raw = request.form.get('time_slots','').strip()
    time_slots = [s.strip() for s in slots_raw.split(',') if s.strip()]
    if not department or not year or not division:
        flash('Please select department, year and division', 'danger')
        return redirect(url_for('admin_timetable', department=department, year=year, division=division))
    label = f"{year} - {department} {division}"
    timetable_collection.update_one(
        {"class": label},
        {"$set": {"class": label, "time_slots": time_slots, "updated_at": datetime.now()}},
        upsert=True
    )
    flash('Time slots updated', 'success')
    return redirect(url_for('admin_timetable', department=department, year=year, division=division))

@app.route('/admin/timetable/add_entry', methods=['POST'])
@login_required
def admin_timetable_add_entry():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    department = request.form.get('department','').strip()
    year = request.form.get('year','').strip()
    division = request.form.get('division','').strip()
    day = request.form.get('day','').strip()
    time_slot = request.form.get('time_slot','').strip()
    subject = request.form.get('subject','').strip()
    teacher = request.form.get('teacher','').strip()
    room = request.form.get('room','').strip()
    if not all([department, year, division, day, time_slot, subject]):
        flash('Missing required fields', 'danger')
        return redirect(url_for('admin_timetable', department=department, year=year, division=division))
    label = f"{year} - {department} {division}"
    timetable_collection.update_one(
        {"class": label},
        {"$set": {"class": label}, "$push": {"classes": {"day": day, "time_slot": time_slot, "subject": subject, "teacher": teacher, "room": room}}, "$set": {"updated_at": datetime.now()}},
        upsert=True
    )
    flash('Entry added', 'success')
    return redirect(url_for('admin_timetable', department=department, year=year, division=division))

@app.route('/admin/timetable/delete_entry', methods=['POST'])
@login_required
def admin_timetable_delete_entry():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    department = request.form.get('department','').strip()
    year = request.form.get('year','').strip()
    division = request.form.get('division','').strip()
    index_str = request.form.get('index','').strip()
    try:
        idx = int(index_str)
    except Exception:
        flash('Invalid entry index', 'danger')
        return redirect(url_for('admin_timetable', department=department, year=year, division=division))
    label = f"{year} - {department} {division}"
    doc = timetable_collection.find_one({"class": label})
    if not doc or not isinstance(doc.get('classes'), list) or idx < 0 or idx >= len(doc['classes']):
        flash('Entry not found', 'danger')
        return redirect(url_for('admin_timetable', department=department, year=year, division=division))
    updated = doc['classes'][:idx] + doc['classes'][idx+1:]
    timetable_collection.update_one({"_id": doc["_id"]}, {"$set": {"classes": updated, "updated_at": datetime.now()}})
    flash('Entry deleted', 'success')
    return redirect(url_for('admin_timetable', department=department, year=year, division=division))

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if current_user.role != "admin":
        return redirect(url_for('home'))
    if request.method == 'POST':
        site_name = request.form.get('site_name','').strip()
        registration_enabled = request.form.get('registration_enabled','off') == 'on'
        backup_cron = request.form.get('backup_cron','').strip()
        settings_collection.update_one({}, {"$set": {"site_name": site_name, "registration_enabled": registration_enabled, "backup_cron": backup_cron}}, upsert=True)
        flash('Settings updated', 'success')
        return redirect(url_for('admin_settings'))
    doc = settings_collection.find_one({}) or {}
    return render_template('admin_settings.html', settings=doc)

@app.route('/notifications/manage', methods=['GET', 'POST'])
@login_required
def manage_notifications():
    if current_user.role not in ["admin", "teacher"]:
        return redirect(url_for('home'))
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        message = request.form.get('message','').strip()
        audience = request.form.get('audience','all').strip()
        class_name = request.form.get('class','').strip()
        priority = request.form.get('priority','normal').strip()
        expires = request.form.get('expires_at','').strip()
        expires_at = None
        if expires:
            try:
                expires_at = datetime.strptime(expires, '%Y-%m-%d')
            except Exception:
                expires_at = None
        notifications_collection.insert_one({
            "title": title,
            "message": message,
            "audience": audience,
            "class": class_name,
            "priority": priority,
            "expires_at": expires_at,
            "created_by": current_user.id,
            "creator_role": current_user.role,
            "created_at": datetime.now()
        })
        flash('Notification created', 'success')
        return redirect(url_for('manage_notifications'))
    items = list(notifications_collection.find({}).sort("created_at", -1))
    return render_template('manage_notifications.html', notifications=items)

@app.route('/notifications/<notif_id>/edit', methods=['POST'])
@login_required
def edit_notification(notif_id):
    if current_user.role not in ["admin", "teacher"]:
        return redirect(url_for('home'))
    title = request.form.get('title','').strip()
    message = request.form.get('message','').strip()
    audience = request.form.get('audience','all').strip()
    class_name = request.form.get('class','').strip()
    priority = request.form.get('priority','normal').strip()
    expires = request.form.get('expires_at','').strip()
    expires_at = None
    if expires:
        try:
            expires_at = datetime.strptime(expires, '%Y-%m-%d')
        except Exception:
            expires_at = None
    notifications_collection.update_one({"_id": ObjectId(notif_id)}, {"$set": {
        "title": title,
        "message": message,
        "audience": audience,
        "class": class_name,
        "priority": priority,
        "expires_at": expires_at,
        "updated_at": datetime.now()
    }})
    flash('Notification updated', 'success')
    return redirect(url_for('manage_notifications'))

@app.route('/notifications/<notif_id>/delete', methods=['POST'])
@login_required
def delete_notification(notif_id):
    if current_user.role not in ["admin", "teacher"]:
        return redirect(url_for('home'))
    notifications_collection.delete_one({"_id": ObjectId(notif_id)})
    flash('Notification deleted', 'success')
    return redirect(url_for('manage_notifications'))

@app.route('/student/notifications')
@login_required
def student_notifications():
    if current_user.role != "student":
        return redirect(url_for('home'))
    now = datetime.now()
    items = []
    for n in notifications_collection.find({}).sort("created_at", -1):
        exp = n.get('expires_at')
        if exp and exp < now:
            continue
        aud = n.get('audience')
        if aud == 'all' or aud == 'students' or (aud == 'class' and n.get('class') == current_user.user_data.get('class')):
            items.append(n)
    return render_template('student_notifications.html', notifications=items, user=current_user)

@app.route('/dashboard/student')
@login_required
def student_dashboard():
    if current_user.role != "student":
        return redirect(url_for('home'))
    now = datetime.now()
    items = []
    for n in notifications_collection.find({}).sort("created_at", -1):
        exp = n.get('expires_at')
        if exp and exp < now:
            continue
        aud = n.get('audience')
        if aud == 'all' or aud == 'students' or (aud == 'class' and n.get('class') == current_user.user_data.get('class')):
            items.append(n)
    return render_template('student_dashboard.html', user=current_user, notifications=items[:5])
        
@app.route('/student/account', methods=['GET', 'POST'])
@login_required
def student_account():
    if current_user.role != "student":
        return redirect(url_for('home'))
        
    # Get current user data from MongoDB
    user_data = students_collection.find_one({"_id": ObjectId(current_user.id)})
        
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        date_of_birth = request.form.get('date_of_birth')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        
        # Only verify password if trying to change it
        if new_password:
            if not current_password or not check_password_hash(user_data["password"], current_password):
                flash('Current password is incorrect', 'danger')
                return redirect(url_for('student_account'))
        
        # Update user data
        update_data = {
            "email": email,
            "phone": phone,
            "address": address,
            "date_of_birth": date_of_birth
        }
        
        # Update password if provided
        if new_password:
            update_data["password"] = generate_password_hash(new_password)
        
        # Update in MongoDB
        students_collection.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$set": update_data}
        )
        flash('Account information updated successfully', 'success')
        return redirect(url_for('student_account'))
    
    return render_template('student_account.html', user=user_data)

@app.route('/dashboard/teacher')
@login_required
def teacher_dashboard():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    now = datetime.now()
    items = []
    classes = current_user.user_data.get('classes', [])
    for n in notifications_collection.find({}).sort("created_at", -1):
        exp = n.get('expires_at')
        if exp and exp < now:
            continue
        aud = n.get('audience')
        if aud == 'all' or (aud == 'class' and n.get('class') in classes):
            items.append(n)
    return render_template('teacher_dashboard.html', user=current_user, notifications=items[:5])
    notes_count = notes_collection.count_documents({"teacher_id": teacher_id})
    syllabus_count = syllabus_collection.count_documents({"teacher_id": teacher_id})
    
    # Get recent activities
    recent_notes = list(notes_collection.find({"teacher_id": teacher_id}).sort("upload_date", -1).limit(3))
    recent_syllabus = list(syllabus_collection.find({"teacher_id": teacher_id}).sort("upload_date", -1).limit(3))
    
    # Combine and sort activities
    activities = []
    for note in recent_notes:
        activities.append({
            "type": "note",
            "subject": note.get("subject"),
            "date": note.get("upload_date"),
            "description": f"Uploaded notes for {note.get('subject')}"
        })
    
    for syllabus in recent_syllabus:
        activities.append({
            "type": "syllabus",
            "subject": syllabus.get("subject"),
            "date": syllabus.get("upload_date"),
            "description": f"Uploaded syllabus for {syllabus.get('subject')}"
        })
    
    # Sort activities by date
    activities.sort(key=lambda x: x["date"], reverse=True)
    
    return render_template('teacher_dashboard.html', 
                          user=current_user,
                          notes_count=notes_count,
                          syllabus_count=syllabus_count,
                          activities=activities[:5])

@app.route('/student/attendance')
@login_required
def student_attendance():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    # Get student's attendance records
    student_id = current_user.id
    attendance_records = list(attendance_collection.find({"student_id": student_id}))
    
    # Calculate attendance percentages
    subjects = {}
    total_classes = 0
    present_classes = 0
    
    for record in attendance_records:
        subject = record.get('subject', 'subjects')
        status = record.get('status', False)
        
        if subject not in subjects:
            subjects[subject] = {"present": 0, "total": 0}
        
        subjects[subject]["total"] += 1
        total_classes += 1
        
        if status:
            subjects[subject]["present"] += 1
            present_classes += 1
    
    # Format data for template
    subject_data = []
    for subject_name, data in subjects.items():
        percentage = (data["present"] / data["total"]) * 100 if data["total"] > 0 else 0
        subject_data.append({
            "name": subject_name,
            "percentage": round(percentage, 1)
        })
    
    overall_percentage = (present_classes / total_classes) * 100 if total_classes > 0 else 0
    
    # Format attendance records for display
    formatted_records = []
    for record in attendance_records:
        formatted_records.append({
            "date": record.get('date', 'Unknown'),
            "subject": record.get('subject', 'Unknown'),
            "status": record.get('status', False)
        })
    
    return render_template('student_attendance.html', 
                          user=current_user,
                          attendance_records=formatted_records,
                          subjects=subject_data,
                          overall_percentage=round(overall_percentage, 1))

@app.route('/student/grades')
@login_required
def student_grades():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    # Get student's grades
    student_id = current_user.id
    grades = list(grades_collection.find({"student_id": student_id}))
    
    return render_template('student_grades.html', user=current_user, grades=grades)

@app.route('/student/notes')
@login_required
def student_notes():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    # Get notes available for student's class
    student_class = current_user.user_data.get('class', '')
    notes = list(notes_collection.find({"class": student_class}))
    
    return render_template('student_notes.html', user=current_user, notes=notes)

@app.route('/student/syllabus')
@login_required
def student_syllabus():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    # Get syllabus for student's class
    student_class = current_user.user_data.get('class', '')
    syllabus = list(syllabus_collection.find({"class": student_class}))
    
    return render_template('student_syllabus.html', user=current_user, syllabus=syllabus)

@app.route('/student/chatbot')
@login_required
def student_chatbot():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    # Get syllabus for student's class
    student_class = current_user.user_data.get('class', '')
    chatbot = list(syllabus_collection.find({"class": student_class}))
    
    return render_template('student_chatbot.html', user=current_user, chatbot=chatbot)

@app.route('/student/timetable')
@login_required
def student_timetable():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    # Get timetable for student's class
    student_class = current_user.user_data.get('class', '')
    
    # Try to get timetable from database
    db_timetable = timetable_collection.find_one({"class": student_class})
    
    # If no timetable found in database, create a sample one
    if not db_timetable:
        timetable = {
            "time_slots": ["9:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00", "12:00 - 1:00", "1:00 - 2:00", "2:00 - 3:00", "3:00 - 4:00"],
            "classes": [
                {"day": "Monday", "time_slot": "9:00 - 10:00", "subject": "Mathematics", "teacher": "Dr. Smith", "room": "101"},
                {"day": "Monday", "time_slot": "10:00 - 11:00", "subject": "Physics", "teacher": "Dr. Johnson", "room": "102"},
                {"day": "Tuesday", "time_slot": "9:00 - 10:00", "subject": "Chemistry", "teacher": "Dr. Williams", "room": "103"},
                {"day": "Wednesday", "time_slot": "11:00 - 12:00", "subject": "Computer Science", "teacher": "Dr. Brown", "room": "104"},
                {"day": "Thursday", "time_slot": "2:00 - 3:00", "subject": "English", "teacher": "Dr. Davis", "room": "105"},
                {"day": "Friday", "time_slot": "1:00 - 2:00", "subject": "History", "teacher": "Dr. Miller", "room": "106"}
            ]
        }
    else:
        timetable = db_timetable
    
    # Get current day for highlighting in the timetable
    current_day = datetime.now().strftime("%A")
    
    return render_template('student_timetable.html', user=current_user, timetable=timetable, current_day=current_day)

# -------------------------------
# Download Routes
# -------------------------------
@app.route('/download/note/<note_id>')
@login_required
def download_note(note_id):
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    note = notes_collection.find_one({"_id": ObjectId(note_id)})
    if not note:
        flash('Note not found')
        return redirect(url_for('student_notes'))
    
    file_path = note.get('file_path')
    if not file_path or not os.path.exists(file_path):
        flash('File not found on server')
        return redirect(url_for('student_notes'))
    
    return send_file(file_path, as_attachment=True)

@app.route('/download/syllabus/<syllabus_id>')
@login_required
def download_syllabus(syllabus_id):
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    syllabus = syllabus_collection.find_one({"_id": ObjectId(syllabus_id)})
    if not syllabus:
        flash('Syllabus not found')
        return redirect(url_for('student_syllabus'))
    
    file_path = syllabus.get('file_path')
    if not file_path or not os.path.exists(file_path):
        flash('File not found on server')
        return redirect(url_for('student_syllabus'))
    
    return send_file(file_path, as_attachment=True)
from werkzeug.utils import secure_filename
    


@app.route('/teacher/attendance', methods=['GET', 'POST'])
@login_required
def teacher_attendance():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    # Get classes taught by this teacher from their profile
    teacher_id = current_user.id
    classes = current_user.user_data.get('classes', [])
    
    if request.method == 'POST':
        # Here, class_id actually contains the class name from the form
        class_name = request.form.get('class_id')
        date = request.form.get('date')
        
        # Process attendance data
        for key, value in request.form.items():
            if key.startswith('student_'):
                student_id = key.replace('student_', '')
                status_bool = True if value == 'present' else False
                # Save attendance to database using real student IDs
                attendance_collection.insert_one({
                    "student_id": student_id,
                    "class": class_name,
                    "date": date,
                    "status": status_bool,
                    "marked_by": teacher_id,
                    "updated_at": datetime.now()
                })
        
        flash("Attendance marked successfully!")
        return redirect(url_for('teacher_attendance'))
    
    return render_template('teach_attend.html', user=current_user, classes=classes)

@app.route('/teacher/grades')
@login_required
def teacher_grades():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    # Get classes and subjects taught by this teacher from their profile
    teacher_id = current_user.id
    subjects = current_user.user_data.get('subjects', [])
    classes = current_user.user_data.get('classes', [])
    
    return render_template('teacher_grades.html', user=current_user, subjects=subjects, classes=classes)

@app.route('/teacher/notes')
@login_required
def teacher_notes():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    # Get notes uploaded by this teacher
    teacher_id = current_user.id
    notes = list(notes_collection.find({"teacher_id": teacher_id}))
    subjects = current_user.user_data.get('subjects', [])
    classes = current_user.user_data.get('classes', [])
    return render_template('teacher_notes.html', user=current_user, notes=notes, subjects=subjects, classes=classes)

@app.route('/teacher/syllabus')
@login_required
def teacher_syllabus():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    # Get syllabus created by this teacher
    teacher_id = current_user.id
    syllabi = list(syllabus_collection.find({"teacher_id": teacher_id}))
    subjects = current_user.user_data.get('subjects', [])
    classes = current_user.user_data.get('classes', [])
    return render_template('teacher_syllabus.html', user=current_user, syllabi=syllabi, subjects=subjects, classes=classes)

@app.route('/teacher/profile')
@login_required
def teacher_profile():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    return render_template('teacher_profile.html', user=current_user)

@app.route('/teacher/upload/notes', methods=['POST'])
@login_required
def teacher_upload_notes():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    subject = request.form.get('subject')
    class_name = request.form.get('class')
    description = request.form.get('description')
    note_file = request.files.get('note_file')
    
    if not all([subject, class_name, description, note_file]):
        flash('All fields are required', 'danger')
        return redirect(url_for('teacher_notes'))
    
    # Save the uploaded file to disk under uploads/notes
    filename = secure_filename(note_file.filename)
    notes_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'notes')
    os.makedirs(notes_dir, exist_ok=True)
    file_path = os.path.join(notes_dir, filename)
    note_file.save(file_path)
    
    # Insert note record into database
    note_id = notes_collection.insert_one({
        "subject": subject,
        "class": class_name,
        "description": description,
        "file_name": filename,
        "file_path": file_path,
        "teacher_id": current_user.id,
        "teacher_name": current_user.name,
        "upload_date": datetime.now()
    }).inserted_id
    
    flash('Note uploaded successfully', 'success')
    return redirect(url_for('teacher_notes'))

@app.route('/delete/note/<note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    # Check if note exists and belongs to this teacher
    note = notes_collection.find_one({"_id": ObjectId(note_id), "teacher_id": current_user.id})
    
    if not note:
        flash('Note not found or you do not have permission to delete it', 'danger')
        return redirect(url_for('teacher_notes'))
    
    # Delete note from database
    notes_collection.delete_one({"_id": ObjectId(note_id)})
    
    flash('Note deleted successfully', 'success')
    return redirect(url_for('teacher_notes'))

@app.route('/upload/syllabus', methods=['POST'])
@login_required
def upload_syllabus():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    subject = request.form.get('subject')
    course_code = request.form.get('course_code')
    credits = request.form.get('credits')
    class_name = request.form.get('class')
    description = request.form.get('description')
    units = request.form.get('units')
    reference_books = request.form.get('reference_books')
    syllabus_file = request.files.get('syllabus_file')
    
    if not all([subject, course_code, credits, class_name, description, units, reference_books, syllabus_file]):
        flash('All fields are required', 'danger')
        return redirect(url_for('teacher_syllabus'))
    
    # Save the uploaded file to disk under uploads/syllabus
    filename = secure_filename(syllabus_file.filename)
    syllabus_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'syllabus')
    os.makedirs(syllabus_dir, exist_ok=True)
    file_path = os.path.join(syllabus_dir, filename)
    syllabus_file.save(file_path)
    
    # Insert syllabus record into database
    syllabus_id = syllabus_collection.insert_one({
        "subject": subject,
        "course_code": course_code,
        "credits": int(credits),
        "class": class_name,
        "description": description,
        "units": units.split(','),
        "reference_books": reference_books.split(','),
        "file_name": filename,
        "file_path": file_path,
        "teacher_id": current_user.id,
        "teacher_name": current_user.name,
        "upload_date": datetime.now()
    }).inserted_id
    
    flash('Syllabus uploaded successfully', 'success')
    return redirect(url_for('teacher_syllabus'))

@app.route('/delete/syllabus/<syllabus_id>', methods=['POST'])
@login_required
def delete_syllabus(syllabus_id):
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    # Check if syllabus exists and belongs to this teacher
    syllabus = syllabus_collection.find_one({"_id": ObjectId(syllabus_id), "teacher_id": current_user.id})
    
    if not syllabus:
        flash('Syllabus not found or you do not have permission to delete it', 'danger')
        return redirect(url_for('teacher_syllabus'))
    
    # Delete syllabus from database
    syllabus_collection.delete_one({"_id": ObjectId(syllabus_id)})
    
    flash('Syllabus deleted successfully', 'success')
    return redirect(url_for('teacher_syllabus'))

@app.route('/update/teacher/profile', methods=['POST'])
@login_required
def update_teacher_profile():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    phone = request.form.get('phone')
    address = request.form.get('address')
    city = request.form.get('city')
    state = request.form.get('state')
    postal_code = request.form.get('postal_code')
    
    # Update user profile in database
    teachers_collection.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {
            "phone": phone,
            "address": address,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "updated_at": datetime.now()
        }}
    )
    
    flash('Profile updated successfully', 'success')
    return redirect(url_for('teacher_profile'))

# -------------------------------
# API Endpoints
# -------------------------------

# Get students by class
@app.route('/api/students/<class_name>', methods=['GET'])
@login_required
def get_students_by_class(class_name):
    if current_user.role != "teacher":
        return jsonify({"error": "Unauthorized"}), 403
    
    students = list(students_collection.find(
        {"class": class_name},
        {"_id": 1, "name": 1, "roll_number": 1}
    ))
    
    # Convert ObjectId to string for JSON serialization
    for student in students:
        student["_id"] = str(student["_id"])
    
    return jsonify({"students": students})

@app.route('/api/students/class/<class_id>', methods=['GET'])
@login_required
def get_students_by_class_id(class_id):
    if current_user.role != "teacher":
        return jsonify({"error": "Unauthorized"}), 403
    
    # Sample student data - in production, fetch from database
    sample_students = {
        "class1": [
            {"id": "s1", "name": "Rahul Patil"},
            {"id": "s2", "name": "Priya Rao"},
            {"id": "s3", "name": "Amith Shetty"}
        ],
        "class2": [
            {"id": "s4", "name": "Sneha Sharma"},
            {"id": "s5", "name": "Karthik Reddy"},
            {"id": "s6", "name": "Divya Patel"}
        ],
        "class3": [
            {"id": "s7", "name": "Vikram Singh"},
            {"id": "s8", "name": "Meera Nair"},
            {"id": "s9", "name": "Arjun Kumar"}
        ]
    }
    
    students = sample_students.get(class_id, [])
    return jsonify(students)

# Update attendance
@app.route('/api/attendance/update', methods=['POST'])
@login_required
def update_attendance():
    if current_user.role != "teacher":
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    class_name = data.get('class')
    date = data.get('date')
    subject = data.get('subject')
    attendance_data = data.get('attendance', [])
    
    # Validate required fields
    if not all([class_name, date, subject, attendance_data]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Update attendance records
    for record in attendance_data:
        student_id = record.get('student_id')
        status = record.get('status', False)
        
        # Find if record already exists
        existing = attendance_collection.find_one({
            "student_id": student_id,
            "date": date,
            "subject": subject
        })
        
        if existing:
            # Update existing record
            attendance_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {"status": status}}
            )
        else:
            # Create new record
            attendance_collection.insert_one({
                "student_id": student_id,
                "class": class_name,
                "date": date,
                "subject": subject,
                "status": status,
                "teacher_id": current_user.id,
                "updated_at": datetime.now()
            })
    
    return jsonify({"success": True, "message": "Attendance updated successfully"})

# Update grades
@app.route('/api/grades/update', methods=['POST'])
@login_required
def update_grades():
    if current_user.role != "teacher":
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    class_name = data.get('class')
    subject = data.get('subject')
    exam_type = data.get('exam_type')
    grades_data = data.get('grades', [])
    
    # Validate required fields
    if not all([class_name, subject, exam_type, grades_data]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Update grades records
    for record in grades_data:
        student_id = record.get('student_id')
        marks = record.get('marks')
        
        if student_id is None or marks is None:
            continue
        
        # Find if record already exists
        existing = grades_collection.find_one({
            "student_id": student_id,
            "subject": subject,
            "exam_type": exam_type
        })
        
        if existing:
            # Update existing record
            grades_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {"marks": marks}}
            )
        else:
            # Create new record
            grades_collection.insert_one({
                "student_id": student_id,
                "class": class_name,
                "subject": subject,
                "exam_type": exam_type,
                "marks": marks,
                "teacher_id": current_user.id,
                "updated_at": datetime.now()
            })
    
    return jsonify({"success": True, "message": "Grades updated successfully"})

# Upload notes
@app.route('/api/notes/upload', methods=['POST'])
@login_required
def upload_notes():
    if current_user.role != "teacher":
        return jsonify({"error": "Unauthorized"}), 403
    
    title = request.form.get('title')
    description = request.form.get('description')
    class_name = request.form.get('class')
    subject = request.form.get('subject')
    
    # Validate required fields
    if not all([title, class_name, subject]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Handle file upload
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Save file to appropriate location
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    # Create notes record
    notes_collection.insert_one({
        "title": title,
        "description": description,
        "class": class_name,
        "subject": subject,
        "file_path": file_path,
        "teacher_id": current_user.id,
        "created_at": datetime.now()
    })
    
    return jsonify({"success": True, "message": "Notes uploaded successfully"})

# Initialize database with sample data
def init_db():
    admin = admins_collection.find_one({"username": "admin"})
    if not admin:
        admins_collection.insert_one({
            "username": "admin",
            "password": generate_password_hash("admin123"),
            "role": "admin",
            "name": "Admin User",
            "email": "admin@college.edu"
        })
        teacher_id = teachers_collection.insert_one({
            "username": "teacher1",
            "password": generate_password_hash("teacher123"),
            "role": "teacher",
            "name": "John Smith",
            "email": "john.smith@college.edu",
            "subjects": ["Mathematics", "Physics"],
            "classes": ["3rd Year - ECE A", "2nd Year - ECE B"]
        }).inserted_id
        for i in range(1, 6):
            student_id = students_collection.insert_one({
                "username": f"student{i}",
                "password": generate_password_hash(f"student{i}"),
                "role": "student",
                "name": f"Student {i}",
                "roll_number": f"ECE/2023/{i:03d}",
                "email": f"student{i}@college.edu",
                "class": "3rd Year - ECE A"
            }).inserted_id
            attendance_collection.insert_one({
                "student_id": str(student_id),
                "class": "3rd Year - ECE A",
                "date": "2023-10-15",
                "subject": "Mathematics",
                "status": True,
                "teacher_id": str(teacher_id)
            })
            grades_collection.insert_one({
                "student_id": str(student_id),
                "class": "3rd Year - ECE A",
                "subject": "Mathematics",
                "exam_type": "Mid Term",
                "marks": 85,
                "teacher_id": str(teacher_id)
            })
    extra_teachers = [
        {
            "username": "teacher2",
            "password": generate_password_hash("teacher2123"),
            "role": "teacher",
            "name": "Jane Smith",
            "email": "jane.smith@college.edu",
            "subjects": ["Chemistry", "Electronics"],
            "classes": ["CSE Year 2", "EEE Year 1"]
        },
        {
            "username": "teacher3",
            "password": generate_password_hash("teacher3123"),
            "role": "teacher",
            "name": "Robert Brown",
            "email": "robert.brown@college.edu",
            "subjects": ["Mechanics", "Civil Drawing"],
            "classes": ["ME Year 1", "CE Year 1"]
        }
    ]
    for t in extra_teachers:
        if not teachers_collection.find_one({"username": t["username"]}):
            teachers_collection.insert_one(t)

# Initialize database on first run
if __name__ == '__main__':
    # Create upload folder if it doesn't exist
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize database with sample data
    init_db()
    
    # Run the application
if __name__ == "__main__":
    init_db()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

