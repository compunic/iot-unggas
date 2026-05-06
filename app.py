import sqlite3
import os
from flask import Flask, request, jsonify, render_template

SECRET_PASSWORD = "stadiotoflask"
app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "dhtmq.db")


# =========================
# DATABASE CONNECTION
# =========================
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# INIT DATABASE
# =========================
def init_db():
    conn = get_db()
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

    # INDEX untuk performa multi device
    c.execute("CREATE INDEX IF NOT EXISTS idx_nama_esp ON sensor_data(nama_esp)")

    conn.commit()
    conn.close()


# =========================
# INSERT DATA
# =========================
def insert_data(nama_esp, suhu, kelembaban, amonia):
    conn = get_db()
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

    if not nama_esp:
        return jsonify({"status": "error", "message": "nama_esp wajib"}), 400

    if suhu is None or kelembaban is None:
        return jsonify({"status": "error", "message": "Incomplete data"}), 400

    try:
        insert_data(nama_esp, suhu, kelembaban, amonia)
    except Exception as e:
        print("DB Error:", e)
        return jsonify({"status": "error", "message": "DB error"}), 500

    return jsonify({"status": "success"}), 200


# =========================
# GET DEVICES (LIST KANDANG)
# =========================
@app.route('/devices', methods=['GET'])
def devices():
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT DISTINCT nama_esp FROM sensor_data")
    rows = c.fetchall()

    conn.close()

    return jsonify([row["nama_esp"] for row in rows])


# =========================
# GET LATEST DATA (PER DEVICE)
# =========================
@app.route('/latest', methods=['GET'])
def latest_data():
    nama_esp = request.args.get("nama_esp")

    conn = get_db()
    c = conn.cursor()

    if nama_esp:
        c.execute("""
            SELECT * FROM sensor_data
            WHERE nama_esp = ?
            ORDER BY id DESC LIMIT 1
        """, (nama_esp,))
    else:
        c.execute("""
            SELECT * FROM sensor_data
            ORDER BY id DESC LIMIT 1
        """)

    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "no data"}), 404

    return jsonify(dict(row))


# =========================
# CHART DATA
# =========================
@app.route('/chart-data', methods=['GET'])
def chart_data():
    range_type = request.args.get('range', 'hour')
    nama_esp = request.args.get('nama_esp')

    conn = get_db()
    c = conn.cursor()

    # FILTER WAKTU
    range_map = {
        "minute": "-60 minutes",
        "hour": "-24 hours",
        "weekly": "-7 days",
        "monthly": "-30 days"
    }

    filter_time = range_map.get(range_type, "-1 day")

    if nama_esp:
        c.execute(f"""
            SELECT suhu, kelembaban, amonia, timestamp
            FROM sensor_data
            WHERE nama_esp = ?
            AND timestamp >= datetime('now', '{filter_time}')
            ORDER BY id ASC
        """, (nama_esp,))
    else:
        c.execute(f"""
            SELECT suhu, kelembaban, amonia, timestamp
            FROM sensor_data
            WHERE timestamp >= datetime('now', '{filter_time}')
            ORDER BY id ASC
        """)

    rows = c.fetchall()
    conn.close()

    return jsonify({
        "suhu": [r["suhu"] for r in rows],
        "kelembaban": [r["kelembaban"] for r in rows],
        "amonia": [r["amonia"] for r in rows],
        "waktu": [r["timestamp"][11:16] for r in rows]
    })


# =========================
# ANALYSIS DOC
# =========================
@app.route('/analysis', methods=['GET'])
def analysis():
    nama_esp = request.args.get("nama_esp")

    conn = get_db()
    c = conn.cursor()

    if nama_esp:
        c.execute("""
            SELECT suhu, kelembaban, amonia
            FROM sensor_data
            WHERE nama_esp = ?
            ORDER BY id DESC LIMIT 1
        """, (nama_esp,))
    else:
        c.execute("""
            SELECT suhu, kelembaban, amonia
            FROM sensor_data
            ORDER BY id DESC LIMIT 1
        """)

    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "no data"}), 404

    suhu = row["suhu"]
    hum = row["kelembaban"]
    amonia = row["amonia"]

    kondisi = "AMAN"

    # SUHU
    if suhu >= 32:
        status_suhu = "🔥 Terlalu Panas"
        kondisi = "BAHAYA"
    elif suhu >= 30:
        status_suhu = "👍 Ideal DOC"
    elif suhu >= 28:
        status_suhu = "⚠️ Mulai Dingin"
        kondisi = "WARNING"
    else:
        status_suhu = "❄️ Dingin"
        kondisi = "BAHAYA"

    # KELEMBABAN
    if 50 <= hum <= 70:
        status_hum = "👍 Normal"
    elif hum < 50:
        status_hum = "⚠️ Kering"
    else:
        status_hum = "⚠️ Lembab"

    # AMONIA
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
        "nama_esp": nama_esp,
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
    nama_esp = request.args.get("nama_esp")

    conn = get_db()
    c = conn.cursor()

    if nama_esp:
        c.execute("""
            SELECT suhu, kelembaban, amonia
            FROM sensor_data
            WHERE nama_esp = ?
            ORDER BY id DESC LIMIT 1
        """, (nama_esp,))
    else:
        c.execute("""
            SELECT suhu, kelembaban, amonia
            FROM sensor_data
            ORDER BY id DESC LIMIT 1
        """)

    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "no data"}), 404

    return jsonify({
        "suhu": row["suhu"],
        "kelembaban": row["kelembaban"],
        "amonia": row["amonia"]
    })


# =========================
# DELETE ALL
# =========================
@app.route('/delete-all', methods=['POST'])
def delete_all():
    content = request.json

    if not content or content.get("password") != SECRET_PASSWORD:
        return jsonify({"status": "error"}), 403

    conn = get_db()
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

    conn = get_db()
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
    return "IoT Multi Sensor Server Running 🚀"


# =========================
# MAIN
# =========================
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
