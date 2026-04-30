from flask import *
from db import *
from flask_cors import CORS


app = Flask(__name__)
CORS(app)



@app.route('/add_patient', methods=['POST'])
def add_patient():
    try:
        data = request.json
        print("Received data:", data)

        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        INSERT INTO patients (first_name, last_name, gender, phone, national_id)
        VALUES (%s, %s, %s, %s, %s)
        """

        values = (
            data.get('first_name'),
            data.get('last_name'),
            data.get('gender'),
            data.get('phone'),
            data.get('national_id')
        )

        cursor.execute(sql, values)
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Patient added successfully"})

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500



@app.route('/patients', methods=['GET'])
def get_patients():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patients ORDER BY id DESC")
    patients = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(patients)


@app.route('/patient/<int:patient_id>', methods=['GET'])
def get_patient(patient_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patients WHERE id = %s", (patient_id,))
    patient = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify(patient)


if __name__ == '__main__':
    app.run(debug=True)