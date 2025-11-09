from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from pymongo import MongoClient
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from bson import ObjectId

app = Flask(__name__, static_folder='statics', template_folder='templates')
app.secret_key = os.urandom(24)

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["college_erp_db"]
# Collections
users_collection = db["users"]
attendance_collection = db["attendance"]
grades_collection = db["grades"]
notes_collection = db["notes"]
syllabus_collection = db["syllabus"]
notifications_collection = db["notifications"]
events_collection = db["events"]

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
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_data)
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

@app.route('/dashboard/student')
@login_required
def student_dashboard():
    if current_user.role != "student":
        return redirect(url_for('home'))
    return render_template('student_dashboard.html', user=current_user)
        
@app.route('/student/account', methods=['GET', 'POST'])
@login_required
def student_account():
    if current_user.role != "student":
        return redirect(url_for('home'))
        
    # Get current user data from MongoDB
    user_data = users_collection.find_one({"_id": ObjectId(current_user.id)})
        
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
        users_collection.update_one(
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
    
    # Get counts for dashboard stats
    teacher_id = current_user.id
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
    db_timetable = db.timetable.find_one({"class": student_class})
    
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
    if not note or not note.get('file_path'):
        flash('Note not found or no file available')
        return redirect(url_for('student_notes'))
    
    # In a real application, you would serve the file from storage
    # For now, we'll just redirect back with a message
    flash('Note download started')
    return redirect(url_for('student_notes'))

@app.route('/download/syllabus/<syllabus_id>')
@login_required
def download_syllabus(syllabus_id):
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    syllabus = syllabus_collection.find_one({"_id": ObjectId(syllabus_id)})
    if not syllabus or not syllabus.get('file_path'):
        flash('Syllabus not found or no file available')
        return redirect(url_for('student_syllabus'))
    
    # In a real application, you would serve the file from storage
    # For now, we'll just redirect back with a message
    flash('Syllabus download started')
    return redirect(url_for('student_syllabus'))
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
    
    # Get subjects taught by this teacher
    teacher_id = current_user.id
    subjects = current_user.user_data.get('subjects', [])
    
    return render_template('teacher_grades.html', user=current_user, subjects=subjects)

@app.route('/teacher/notes')
@login_required
def teacher_notes():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    # Get notes uploaded by this teacher
    teacher_id = current_user.id
    notes = list(notes_collection.find({"teacher_id": teacher_id}))
    
    return render_template('teacher_notes.html', user=current_user, notes=notes)

@app.route('/teacher/syllabus')
@login_required
def teacher_syllabus():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    # Get syllabus created by this teacher
    teacher_id = current_user.id
    syllabi = list(syllabus_collection.find({"teacher_id": teacher_id}))
    
    return render_template('teacher_syllabus.html', user=current_user, syllabi=syllabi)

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
    
    # In a real application, save the file to storage and store the path
    # For now, we'll just store the filename
    filename = secure_filename(note_file.filename)
    file_path = f"uploads/notes/{filename}"  # This would be where you save the file
    
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
    
    # In a real application, save the file to storage and store the path
    # For now, we'll just store the filename
    filename = secure_filename(syllabus_file.filename)
    file_path = f"uploads/syllabus/{filename}"  # This would be where you save the file
    
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
    users_collection.update_one(
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
    
    students = list(users_collection.find(
        {"role": "student", "class": class_name},
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
    # Check if admin user exists
    admin = users_collection.find_one({"username": "admin"})
    if not admin:
        # Create admin user
        users_collection.insert_one({
            "username": "admin",
            "password": generate_password_hash("admin123"),
            "role": "admin",
            "name": "Admin User",
            "email": "admin@college.edu"
        })
        
        # Create sample teacher
        teacher_id = users_collection.insert_one({
            "username": "teacher1",
            "password": generate_password_hash("teacher123"),
            "role": "teacher",
            "name": "John Smith",
            "email": "john.smith@college.edu",
            "subjects": ["Mathematics", "Physics"],
            "classes": ["3rd Year - ECE A", "2nd Year - ECE B"]
        }).inserted_id
        
        # Create sample students
        for i in range(1, 6):
            student_id = users_collection.insert_one({
                "username": f"student{i}",
                "password": generate_password_hash(f"student{i}"),
                "role": "student",
                "name": f"Student {i}",
                "roll_number": f"ECE/2023/{i:03d}",
                "email": f"student{i}@college.edu",
                "class": "3rd Year - ECE A"
            }).inserted_id
            
            # Add sample attendance
            attendance_collection.insert_one({
                "student_id": str(student_id),
                "class": "3rd Year - ECE A",
                "date": "2023-10-15",
                "subject": "Mathematics",
                "status": True,
                "teacher_id": str(teacher_id)
            })
            
            # Add sample grades
            grades_collection.insert_one({
                "student_id": str(student_id),
                "class": "3rd Year - ECE A",
                "subject": "Mathematics",
                "exam_type": "Mid Term",
                "marks": 85,
                "teacher_id": str(teacher_id)
            })

# Initialize database on first run
if __name__ == '__main__':
    # Create upload folder if it doesn't exist
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize database with sample data
    init_db()
    
    # Run the application
    app.run(debug=True)

@app.route('/dashboard/teacher')
@login_required
def teacher_dashboard():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    return render_template('teacher_dashboard.html', user=current_user)

# -------------------------------
# Student Routes
# -------------------------------
@app.route('/student/attendance')
@login_required
def student_attendance():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    attendance = attendance_collection.find_one({"student_id": current_user.id})
    return render_template('st_attendence.html', attendance=attendance, user=current_user)

@app.route('/student/grades')
@login_required
def student_grades():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    grades = grades_collection.find({"student_id": current_user.id})
    return render_template('st_subject.html', grades=list(grades), user=current_user)

@app.route('/student/notes')
@login_required
def student_notes():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    notes = notes_collection.find({"class_id": current_user.user_data.get("class_id")})
    return render_template('st_notes.html', notes=list(notes), user=current_user)

@app.route('/student/syllabus')
@login_required
def student_syllabus():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    syllabus = syllabus_collection.find({"class_id": current_user.user_data.get("class_id")})
    return render_template('st_syllabus.html', syllabus=list(syllabus), user=current_user)

@app.route('/student/notifications')
@login_required
def student_notifications():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    notifications = notifications_collection.find({
        "$or": [
            {"target_role": "all"},
            {"target_role": "student"},
            {"target_id": current_user.id}
        ]
    }).sort("created_at", -1)
    
    return render_template('st_notification.html', notifications=list(notifications), user=current_user)

@app.route('/student/timetable')
@login_required
def student_timetable():
    if current_user.role != "student":
        return redirect(url_for('home'))
    
    timetable = db.timetable.find_one({"class_id": current_user.user_data.get("class_id")})
    return render_template('st_timet.html', timetable=timetable, user=current_user)

# -------------------------------
# Teacher Routes
# -------------------------------
# This route is already implemented above with different functionality
# Removing duplicate route to avoid conflicts

@app.route('/teacher/grades', methods=['GET'])
@login_required
def teacher_grades():
    if current_user.role != "teacher":
        return redirect(url_for('home'))

    # Use teacher's assigned classes and subjects from profile
    classes = current_user.user_data.get('classes', [])
    subjects = current_user.user_data.get('subjects', [])

    return render_template('teacher_grades.html', user=current_user, classes=classes, subjects=subjects)

@app.route('/teacher/notes', methods=['GET', 'POST'])
@login_required
def teacher_notes():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        class_id = request.form.get('class_id')
        subject_id = request.form.get('subject_id')
        
        notes_collection.insert_one({
            "title": title,
            "content": content,
            "class_id": class_id,
            "subject_id": subject_id,
            "teacher_id": current_user.id,
            "created_at": datetime.now()
        })
        
        flash('Notes added successfully')
        return redirect(url_for('teacher_notes'))
    
    # Get classes taught by this teacher
    classes = db.classes.find({"teacher_id": current_user.id})
    subjects = db.subjects.find({"teacher_id": current_user.id})
    
    return render_template('tec_class.html', classes=list(classes), subjects=list(subjects), user=current_user)

@app.route('/teacher/syllabus', methods=['GET', 'POST'])
@login_required
def teacher_syllabus():
    if current_user.role != "teacher":
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        class_id = request.form.get('class_id')
        subject_id = request.form.get('subject_id')
        
        syllabus_collection.insert_one({
            "title": title,
            "content": content,
            "class_id": class_id,
            "subject_id": subject_id,
            "teacher_id": current_user.id,
            "created_at": datetime.now()
        })
        
        flash('Syllabus added successfully')
        return redirect(url_for('teacher_syllabus'))
    
    # Get classes taught by this teacher
    classes = db.classes.find({"teacher_id": current_user.id})
    subjects = db.subjects.find({"teacher_id": current_user.id})
    
    return render_template('teach_class.html', classes=list(classes), subjects=list(subjects), user=current_user)

# -------------------------------
# API Routes for AJAX calls
# -------------------------------
@app.route('/api/students/class/<class_id>', methods=['GET'])
@login_required
def get_students_by_class(class_id):
    if current_user.role != "teacher":
        return jsonify({"error": "Unauthorized"}), 403
    
    students = users_collection.find({"role": "student", "class_id": class_id})
    student_list = []
    
    for student in students:
        student_list.append({
            "id": str(student["_id"]),
            "name": student.get("name", ""),
            "username": student["username"]
        })
    
    return jsonify(student_list)

@app.route('/api/notifications/create', methods=['POST'])
@login_required
def create_notification():
    if current_user.role != "teacher":
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    target_role = data.get('target_role', 'all')
    target_id = data.get('target_id', None)
    
    notification = {
        "title": title,
        "content": content,
        "target_role": target_role,
        "created_by": current_user.id,
        "created_at": datetime.now()
    }
    
    if target_id:
        notification["target_id"] = target_id
    
    result = notifications_collection.insert_one(notification)
    
    return jsonify({"success": True, "id": str(result.inserted_id)})

# Initialize database with admin user if not exists
def init_db():
    # Check if admin user exists
    admin = users_collection.find_one({"username": "admin"})
    if not admin:
        # Create admin user
        admin_user = {
            "username": "admin",
            "password": generate_password_hash("admin123"),
            "role": "admin",
            "name": "Administrator",
            "created_at": datetime.now()
        }
        users_collection.insert_one(admin_user)
        print("Admin user created")
    
    # Create test teacher if not exists
    teacher = users_collection.find_one({"username": "teacher1"})
    if not teacher:
        teacher_user = {
            "username": "teacher1",
            "password": generate_password_hash("teacher123"),
            "role": "teacher",
            "name": "Test Teacher",
            "created_at": datetime.now()
        }
        teacher_id = users_collection.insert_one(teacher_user).inserted_id
        
        # Create test class
        class_id = db.classes.insert_one({
            "name": "Class 10A",
            "teacher_id": str(teacher_id),
            "created_at": datetime.now()
        }).inserted_id
        
        # Create test subject
        subject_id = db.subjects.insert_one({
            "name": "Mathematics",
            "class_id": str(class_id),
            "teacher_id": str(teacher_id),
            "created_at": datetime.now()
        }).inserted_id
        
        print("Test teacher and class created")
    
    # Create test student if not exists
    student = users_collection.find_one({"username": "student1"})
    if not student:
        student_user = {
            "username": "student1",
            "password": generate_password_hash("student1"),
            "role": "student",
            "name": "Test Student",
            "class_id": str(class_id) if 'class_id' in locals() else None,
            "created_at": datetime.now()
        }
        student_id = users_collection.insert_one(student_user).inserted_id
        print("Test student created")
# -------------------------------
# Initialize database and run app
# -------------------------------
if __name__ == '__main__':
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    app.run(debug=True)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
