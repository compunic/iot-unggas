import sqlite3 os
from flask import Flask, request, jsonify, render_template

SECRET_PASSWORD = "stadiotoflask"
app = Flask(__name__)

DB_NAME = "dhtmq.db"

# =========================
# INIT DATABASE
# =========================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_esp TEXT,
            suhu REAL,
            kelembaban REAL,
            amonia REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# =========================
# INSERT DATA
# =========================
def insert_data(nama_esp, suhu, kelembaban, amonia):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO sensor_data (nama_esp, suhu, kelembaban, amonia) VALUES (?, ?, ?, ?)",
        (nama_esp, suhu, kelembaban, amonia)
    )
    conn.commit()
    conn.close()


# =========================
# RECEIVE DATA FROM ESP
# =========================
@app.route('/receive', methods=['POST'])
def receive_data():
    content = request.json

    if not content:
        return jsonify({"status": "error", "message": "No JSON"}), 400

    if content.get("password") != SECRET_PASSWORD:
        return jsonify({"status": "error", "message": "Invalid password"}), 403

    nama_esp = content.get("nama_esp")
    suhu = content.get("suhu")
    kelembaban = content.get("kelembaban")
    amonia = content.get("amonia")

    if nama_esp is None or suhu is None or kelembaban is None:
        return jsonify({"status": "error", "message": "Incomplete data"}), 400

    try:
        insert_data(nama_esp, suhu, kelembaban, amonia)
    except Exception as e:
        print("DB Error:", e)
        return jsonify({"status": "error", "message": "DB error"}), 500

    return jsonify({"status": "success"}), 200


# =========================
# GET LATEST DATA
# =========================
@app.route('/latest', methods=['GET'])
def latest_data():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, nama_esp, suhu, kelembaban, amonia, timestamp
        FROM sensor_data ORDER BY id DESC LIMIT 1
    """)
    row = c.fetchone()
    conn.close()

    if row:
        return jsonify({
            "id": row[0],
            "nama_esp": row[1],
            "suhu": row[2],
            "kelembaban": row[3],
            "amonia": row[4],
            "timestamp": row[5]
        })
    return jsonify({"status": "no data"}), 404


# =========================
# CHART DATA (MULTI RANGE)
# =========================
@app.route('/chart-data', methods=['GET'])
def chart_data():
    range_type = request.args.get('range', 'hour')

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if range_type == 'minute':
        filter_time = "-60 minutes"
    elif range_type == 'hour':
        filter_time = "-24 hours"
    elif range_type == 'weekly':
        filter_time = "-7 days"
    elif range_type == 'monthly':
        filter_time = "-30 days"
    else:
        filter_time = "-1 day"

    query = f"""
        SELECT suhu, kelembaban, amonia, timestamp
        FROM sensor_data
        WHERE timestamp >= datetime('now', '{filter_time}')
        ORDER BY id ASC
    """

    c.execute(query)
    rows = c.fetchall()
    conn.close()

    return jsonify({
        "suhu": [r[0] for r in rows],
        "kelembaban": [r[1] for r in rows],
        "amonia": [r[2] for r in rows],
        "waktu": [r[3][11:16] for r in rows]
    })


# =========================
# ANALYSIS DOC
# =========================
@app.route('/analysis', methods=['GET'])
def analysis():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT suhu, kelembaban, amonia
        FROM sensor_data
        ORDER BY id DESC LIMIT 1
    """)
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "no data"}), 404

    suhu, hum, amonia = row

    # ===== SUHU =====
    if suhu >= 32:
        status_suhu = "🔥 Terlalu Panas"
        kondisi = "BAHAYA"
    elif suhu >= 30:
        status_suhu = "👍 Ideal DOC"
        kondisi = "AMAN"
    elif suhu >= 28:
        status_suhu = "⚠️ Mulai Dingin"
        kondisi = "WARNING"
    else:
        status_suhu = "❄️ Dingin"
        kondisi = "BAHAYA"

    # ===== KELEMBABAN =====
    if 50 <= hum <= 70:
        status_hum = "👍 Normal"
    elif hum < 50:
        status_hum = "⚠️ Kering"
    else:
        status_hum = "⚠️ Lembab"

    # ===== AMONIA =====
    if amonia is None:
        status_amonia = "Tidak terbaca"
    elif amonia < 20:
        status_amonia = "👍 Aman"
    elif amonia < 55:
        status_amonia = "⚠️ Tinggi"
        kondisi = "WARNING"
    else:
        status_amonia = "🔥 Berbahaya"
        kondisi = "BAHAYA"

    return jsonify({
        "suhu": suhu,
        "kelembaban": hum,
        "amonia": amonia,
        "status_suhu": status_suhu,
        "status_kelembaban": status_hum,
        "status_amonia": status_amonia,
        "kondisi": kondisi
    })


# =========================
# STATUS SIMPLE
# =========================
@app.route('/status', methods=['GET'])
def status():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT suhu, kelembaban, amonia
        FROM sensor_data
        ORDER BY id DESC LIMIT 1
    """)
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "no data"}), 404

    suhu, hum, amonia = row

    return jsonify({
        "suhu": suhu,
        "kelembaban": hum,
        "amonia": amonia
    })


# =========================
# DELETE ALL
# =========================
@app.route('/delete-all', methods=['POST'])
def delete_all():
    content = request.json

    if not content or content.get("password") != SECRET_PASSWORD:
        return jsonify({"status": "error"}), 403

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM sensor_data")
    conn.commit()
    conn.close()

    return jsonify({"status": "success"})


# =========================
# RESET DB
# =========================
@app.route('/reset-db', methods=['POST'])
def reset_db():
    content = request.json

    if not content or content.get("password") != SECRET_PASSWORD:
        return jsonify({"status": "error"}), 403

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS sensor_data")
    conn.commit()
    conn.close()

    init_db()

    return jsonify({"status": "success"})


# =========================
# DASHBOARD
# =========================
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard2.html')


@app.route('/')
def home():
    return "IoT Server Running"


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)