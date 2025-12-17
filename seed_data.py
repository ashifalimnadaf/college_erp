from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from datetime import datetime
import os


def main():
    uri = "mongodb+srv://college_erp:clg_erp@cluster0.l3g4xjz.mongodb.net/college_erp_db?retryWrites=true&w=majority"
    client = MongoClient(uri)
    db = client["college_erp_db"]

    users = db["users"]
    attendance = db["attendance"]

    # Create Admin
    if not users.find_one({"username": "admin", "role": "admin"}):
        users.insert_one({
            "username": "admin",
            "password": generate_password_hash("admin123"),
            "role": "admin",
            "name": "Administrator",
            "email": "admin@college.edu",
            "created_at": datetime.now(),
        })
        print("Admin user created (admin/admin123)")
    else:
        print("Admin user already exists")

    # Create Teacher
    teacher = users.find_one({"username": "teacher1", "role": "teacher"})
    if not teacher:
        teacher_id = users.insert_one({
            "username": "teacher1",
            "password": generate_password_hash("teacher123"),
            "role": "teacher",
            "name": "John Smith",
            "email": "john.smith@college.edu",
            # Used by /teacher/grades route and template
            "subjects": ["Mathematics", "Physics"],
            "classes": ["3rd Year - ECE A"],
            "created_at": datetime.now(),
        }).inserted_id
        users.update_one({"_id": teacher_id}, {"$set": {"teacher_id": str(teacher_id)}})
        print("Teacher created (teacher1/teacher123)")
        teacher = users.find_one({"_id": teacher_id})
    else:
        # Ensure teacher_id field exists
        users.update_one({"_id": teacher["_id"]}, {"$set": {"teacher_id": str(teacher["_id"])}})
        print("Teacher already exists")

    # Create Students in class '3rd Year - ECE A'
    class_name = "3rd Year - ECE A"
    created_count = 0
    for i in range(1, 11):
        uname = f"student{i}"
        existing = users.find_one({"username": uname, "role": "student"})
        if existing:
            # Ensure student_id field exists
            users.update_one({"_id": existing["_id"]}, {"$set": {"student_id": str(existing["_id"])}})
            continue

        student_id = users.insert_one({
            "username": uname,
            "password": generate_password_hash(uname),  # password = username
            "role": "student",
            "name": f"Student {i}",
            "roll_number": f"ECE/2023/{i:03d}",
            "email": f"{uname}@college.edu",
            "class": class_name,
            "created_at": datetime.now(),
        }).inserted_id
        users.update_one({"_id": student_id}, {"$set": {"student_id": str(student_id)}})

        # Add sample attendance doc
        attendance.update_one(
            {"student_id": str(student_id)},
            {"$set": {"student_id": str(student_id), "total": 100, "present": 92}},
            upsert=True,
        )
        created_count += 1

    print(f"Created {created_count} new students in '{class_name}'.")
    print("Seeding complete. You can now log in:")
    print(" - Admin: admin / admin123")
    print(" - Teacher: teacher1 / teacher123")
    print(" - Students: student1..student10 (password = username)")


if __name__ == "__main__":
    main()
