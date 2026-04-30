from flask import *
from db import *

app = Flask(__name__)



@app.route('/add_patient', methods=['POST'])
def add_patient():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
    INSERT INTO patients (first_name, last_name, gender, phone, national_id)
    VALUES (%s, %s, %s, %s, %s)
    """

    values = (
        data['first_name'],
        data['last_name'],
        data.get('gender'),
        data.get('phone'),
        data.get('national_id')
    )

    cursor.execute(sql, values)
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "Patient added successfully"})


@app.route('/patients', methods=['GET'])
def get_patients():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patients")
    patients = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(patients)




if __name__ == '__main__':
    app.run(debug=True)