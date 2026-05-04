from flask import Flask, request, jsonify
from db import get_db_connection
from flask_cors import CORS

# caculation for age
from datetime import datetime

def calculate_age(dob):
    today = datetime.today()
    birth_date = datetime.strptime(dob, "%Y-%m-%d")
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ---------------------------
# LOGIN ROUTE (SAFE)
# ---------------------------
@app.route('/login', methods=['POST'])
def login():
    try:
        import jwt
        import datetime

        data = request.get_json()

        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Missing credentials"}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        # ✅ plain text comparison
        if user["password"] != password:
            return jsonify({"error": "Invalid credentials"}), 401

        token = jwt.encode(
            {
                "user_id": user["id"],
                "role": user["role"],
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=3)
            },
            "mysecretkey",
            algorithm="HS256"
        )

        if isinstance(token, bytes):
            token = token.decode("utf-8")

        return jsonify({
            "token": token,
            "role": user["role"]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ---------------------------
# ADD MEDICAL RECORD
# ---------------------------


# ---------------------------
# GET ALL PATIENTS
# ---------------------------
@app.route('/patients', methods=['GET'])
def get_patients():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM patients ORDER BY id DESC")
        patients = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(patients), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
# GET SINGLE PATIENT
# ---------------------------
@app.route('/patient/<int:id>', methods=['GET'])
def get_patient(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM patients WHERE id = %s", (id,))
        patient = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify(patient), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
# GET MEDICAL RECORDS
# ---------------------------
@app.route('/records/<int:patient_id>', methods=['GET'])
def get_records(patient_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM medical_records
            WHERE patient_id = %s
            ORDER BY id DESC
        """, (patient_id,))

        records = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(records), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
# PHARMACY: GET RECORDS
# ---------------------------
@app.route('/pharmacy/records/nid/<national_id>', methods=['GET'])
def pharmacy_records_by_nid(national_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Get patient by national ID
        cursor.execute("""
            SELECT * FROM patients WHERE national_id = %s
        """, (national_id,))
        patient = cursor.fetchone()

        if not patient:
            return jsonify({"error": "Patient not found"}), 404

        # 2. Get ONLY pending records
        cursor.execute("""
            SELECT id, diagnosis, prescription, status, created_at
            FROM medical_records
            WHERE patient_id = %s AND status = 'PENDING'
            ORDER BY id DESC
        """, (patient['id'],))

        records = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "patient": patient,
            "records": records
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------
# PHARMACY: DISPENSE
# ---------------------------
@app.route('/pharmacy/dispense/<int:record_id>', methods=['PUT'])
def dispense_medication(record_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE medical_records
            SET status = 'DISPENSED'
            WHERE id = %s
        """, (record_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Medication dispensed"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# queue route
@app.route('/pharmacy/queue', methods=['GET'])
def pharmacy_queue():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
    SELECT 
        m.id,
        m.diagnosis,
        m.prescription,
        m.status,
        m.created_at,
        p.first_name,
        p.last_name,
        p.national_id
    FROM medical_records m
    JOIN patients p ON m.patient_id = p.id
    WHERE m.status = 'PENDING'
    ORDER BY m.created_at DESC
""")

        queue = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(queue), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
# SEARCH BY NATIONAL ID
# ---------------------------
@app.route('/patient/search/<national_id>', methods=['GET'])
def search_patient_by_nid(national_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM patients WHERE national_id = %s
        """, (national_id,))
        patient = cursor.fetchone()

        if not patient:
            return jsonify({"error": "Patient not found"}), 404

        cursor.execute("""
            SELECT * FROM medical_records
            WHERE patient_id = %s
            ORDER BY id DESC
        """, (patient['id'],))
        records = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "patient": patient,
            "records": records
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
# ADD PATIENT (RECEPTION)
# ---------------------------
@app.route('/add_patient', methods=['POST'])
def add_patient():
    try:
        data = request.get_json(force=True)

        # =========================
        # EXTRACT DATA
        # =========================
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        gender = data.get('gender')
        phone = data.get('phone')
        date_of_birth = data.get('date_of_birth')

        national_id = data.get('national_id')
        guardian_id = data.get('guardian_national_id')

        # =========================
        # VALIDATION
        # =========================
        if not first_name or not last_name:
            return jsonify({"error": "First name and last name are required"}), 400

        if not date_of_birth:
            return jsonify({"error": "Date of birth is required"}), 400

        # =========================
        # AUTO DETECT PATIENT TYPE
        # =========================
        age = calculate_age(date_of_birth)

        if age < 18:
            patient_type = "CHILD"
        else:
            patient_type = "ADULT"

        # =========================
        # BUSINESS RULES
        # =========================
        if patient_type == "ADULT":
            if not national_id:
                return jsonify({"error": "Adult must have national ID"}), 400
            guardian_id = None

        if patient_type == "CHILD":
            if not guardian_id:
                return jsonify({"error": "Child must have guardian national ID"}), 400
            national_id = None

        # =========================
        # INSERT
        # =========================
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO patients 
            (first_name, last_name, gender, phone, date_of_birth, national_id, guardian_national_id, patient_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            first_name,
            last_name,
            gender,
            phone,
            date_of_birth,
            national_id,
            guardian_id,
            patient_type
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "message": "Patient registered successfully",
            "patient_type": patient_type,
            "age": age
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# add record route
@app.route('/add_record', methods=['POST'])
def add_record():
    try:
        data = request.get_json(force=True)

        if not data:
            return jsonify({"error": "No data received"}), 400

        patient_id = data.get('patient_id')
        diagnosis = data.get('diagnosis')
        test_results = data.get('test_results')
        prescription = data.get('prescription')

        if not patient_id:
            return jsonify({"error": "patient_id is required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # ✅ IMPORTANT: status is set to PENDING by default
        cursor.execute("""
            INSERT INTO medical_records 
            (patient_id, diagnosis, test_results, prescription, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            patient_id,
            diagnosis,
            test_results,
            prescription,
            "PENDING"
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Record added successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ⚠️ DO NOT USE app.run() ON ALWAYSDATA
# if __name__ == '__main__':
#     app.run(debug=True)