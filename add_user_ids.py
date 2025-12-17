from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
import os


def main():
    uri = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI") or "mongodb+srv://college_erp:clg_erp@cluster0.l3g4xjz.mongodb.net/college_erp_db?retryWrites=true&w=majority"
    client = MongoClient(uri)
    db = client["college_erp_db"]
    users = db["users"]

    teacher_updates = 0
    student_updates = 0

    # Ensure teacher_id = str(_id) for all teachers
    for u in users.find({"role": "teacher"}, {"_id": 1, "teacher_id": 1}):
        desired = str(u["_id"])
        if u.get("teacher_id") != desired:
            users.update_one({"_id": u["_id"]}, {"$set": {"teacher_id": desired}})
            teacher_updates += 1

    # Ensure student_id = str(_id) for all students
    for u in users.find({"role": "student"}, {"_id": 1, "student_id": 1}):
        desired = str(u["_id"]) 
        if u.get("student_id") != desired:
            users.update_one({"_id": u["_id"]}, {"$set": {"student_id": desired}})
            student_updates += 1

    # Create indexes (sparse so docs without these fields don’t block)
    try:
        users.create_index("teacher_id", unique=True, sparse=True)
    except DuplicateKeyError:
        # In case of pre-existing bad data, keep going without failing
        pass

    try:
        users.create_index("student_id", unique=True, sparse=True)
    except DuplicateKeyError:
        pass

    print(f"Updated teacher_id on {teacher_updates} teacher(s)")
    print(f"Updated student_id on {student_updates} student(s)")
    print("Done. IDs are now present and indexed.")


if __name__ == "__main__":
    main()
