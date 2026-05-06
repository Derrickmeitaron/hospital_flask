from flask import Flask, request, jsonify
from db import get_db_connection
from flask_cors import CORS
from datetime import datetime
import jwt
import datetime as dt
import bcrypt
from functools import wraps

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

SECRET_KEY = "mysecretkey"

# =========================
# AGE HELPER
# =========================
def calculate_age(dob):
    today = datetime.today()
    birth_date = datetime.strptime(dob, "%Y-%m-%d")
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )

# =========================
# TOKEN MIDDLEWARE
# =========================
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        auth = request.headers.get("Authorization")

        if auth and " " in auth:
            token = auth.split(" ")[1]

        if not token:
            return jsonify({"error": "Token missing"}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user = data
        except:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)

    return decorated

# =========================
# ROLE MIDDLEWARE
# =========================
def role_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(request, "user"):
                return jsonify({"error": "Unauthorized"}), 401

            if request.user.get("role") not in roles:
                return jsonify({"error": "Forbidden"}), 403

            return f(*args, **kwargs)
        return decorated
    return wrapper

# =========================
# LOGIN
# =========================
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        if user.get("status") == "disabled":
            return jsonify({"error": "Account disabled"}), 403

        stored = user["password"]

        if stored.startswith("$2b$"):
            if not bcrypt.checkpw(password.encode(), stored.encode()):
                return jsonify({"error": "Invalid credentials"}), 401
        else:
            if password != stored:
                return jsonify({"error": "Invalid credentials"}), 401

        token = jwt.encode({
            "user_id": user["id"],
            "role": user["role"],
            "exp": dt.datetime.utcnow() + dt.timedelta(hours=3)
        }, SECRET_KEY, algorithm="HS256")

        return jsonify({
            "token": token,
            "role": user["role"]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================
# PATIENTS
# =========================
@app.route('/patients', methods=['GET'])
@token_required
@role_required('doctor', 'reception', 'pharmacy', 'admin')
def get_patients():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patients ORDER BY created_at DESC")
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(data)

# =========================
# SINGLE PATIENT
# =========================
@app.route('/patient/<int:id>')
@token_required
def get_patient(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patients WHERE id=%s", (id,))
    data = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify(data)

# =========================
# SEARCH
# =========================
@app.route('/patients/search')
@token_required
def search_patients():
    q = request.args.get("q", "")

    if not q:
        return jsonify([])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    like = f"%{q}%"

    cursor.execute("""
        SELECT id, first_name, last_name, national_id, guardian_national_id, patient_type
        FROM patients
        WHERE CAST(id AS CHAR) LIKE %s
        OR first_name LIKE %s
        OR last_name LIKE %s
        OR national_id LIKE %s
        OR guardian_national_id LIKE %s
        LIMIT 10
    """, (like, like, like, like, like))

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(data)

# =========================
# ADD PATIENT
# =========================
@app.route('/add_patient', methods=['POST'])
@token_required
@role_required('reception', 'admin')
def add_patient():
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    age = calculate_age(data["date_of_birth"])
    ptype = "ADULT" if age >= 18 else "CHILD"

    cursor.execute("""
        INSERT INTO patients
        (first_name,last_name,gender,phone,date_of_birth,national_id,guardian_national_id,patient_type)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        data["first_name"],
        data["last_name"],
        data["gender"],
        data["phone"],
        data["date_of_birth"],
        data.get("national_id"),
        data.get("guardian_national_id"),
        ptype
    ))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Patient added"})

# =========================
# ADD RECORD
# =========================
@app.route('/add_record', methods=['POST'])
@token_required
@role_required('doctor', 'admin')
def add_record():
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO medical_records
        (patient_id, diagnosis, test_results, prescription, status)
        VALUES (%s,%s,%s,%s,'PENDING')
    """, (
        data["patient_id"],
        data["diagnosis"],
        data.get("test_results"),
        data.get("prescription")
    ))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Record added"})

# =========================
# RECORDS
# =========================
@app.route('/records/<int:patient_id>')
@token_required
def get_records(patient_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM medical_records
        WHERE patient_id=%s
        ORDER BY created_at DESC
    """, (patient_id,))

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(data)

# =========================
# PHARMACY + ADMIN
# =========================
@app.route('/pharmacy/queue')
@token_required
@role_required('pharmacy', 'admin')
def pharmacy_queue():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT m.*, p.first_name, p.last_name
        FROM medical_records m
        JOIN patients p ON p.id = m.patient_id
        WHERE m.status='PENDING'
    """)

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(data)

@app.route('/pharmacy/dispense/<int:id>', methods=['PUT'])
@token_required
@role_required('pharmacy', 'admin')
def dispense(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE medical_records
        SET status='DISPENSED'
        WHERE id=%s
    """, (id,))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Dispensed"})

# =========================
# ADMIN USERS
# =========================
@app.route('/admin/users', methods=['POST'])
@token_required
@role_required('admin')
def create_user():
    data = request.get_json()

    hashed = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (username,password,role,status)
        VALUES (%s,%s,%s,'active')
    """, (data["username"], hashed, data["role"]))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "User created"})

@app.route('/admin/users')
@token_required
@role_required('admin')
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id,username,role,status FROM users")
    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(data)

@app.route('/admin/users/<int:id>', methods=['DELETE'])
@token_required
@role_required('admin')
def disable_user(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET status='disabled' WHERE id=%s", (id,))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "User disabled"})

@app.route("/")
def home():
    return "Server is running"

# =========================
# ADMIN FULL PATIENT VIEW
# =========================
@app.route('/admin/patient/<int:id>')
@token_required
@role_required('admin')
def admin_patient(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patients WHERE id=%s", (id,))
    patient = cursor.fetchone()

    cursor.execute("SELECT * FROM medical_records WHERE patient_id=%s", (id,))
    records = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({"patient": patient, "records": records})

# if __name__ == "__main__":
#     app.run()