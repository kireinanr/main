import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import uuid

app = Flask(__name__)
CORS(app)

# --- DATABASE CONNECTION ---
def get_db_connection():
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("❌ ERROR: DATABASE_URL is missing!")
            return None
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"❌ DB Connection Error: {e}")
        return None

@app.route('/')
def home():
    return "Billing Server is Running & Ready!"

# --- API 1: CARI PASIEN ---
@app.route('/api/patients', methods=['GET'])
def search_patients():
    query = request.args.get('q', '')
    conn = get_db_connection()
    if not conn: return jsonify([]), 500
    
    try:
        cur = conn.cursor()
        sql = """
            SELECT id, full_name, mr_no, address 
            FROM patients 
            WHERE full_name ILIKE %s OR mr_no ILIKE %s 
            LIMIT 10
        """
        search_term = f"%{query}%"
        cur.execute(sql, (search_term, search_term))
        results = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify([]), 500

# --- API 2: LIST ASURANSI ---
@app.route('/api/insurances', methods=['GET'])
def get_insurances():
    conn = get_db_connection()
    if not conn: return jsonify([]), 500

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT i.id, i.name, COALESCE(ic.coverage_percentage, 0) as pct
            FROM insurances i
            LEFT JOIN insurance_coverages ic ON i.id = ic.insurance_id
            WHERE i.is_active = true 
            ORDER BY i.name ASC
        """)
        results = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify([]), 500

# --- API 3: TARIK RESEP (UPDATE: HURUF KECIL 'processed' -> 'billed') ---
@app.route('/api/get-prescription', methods=['GET'])
def get_prescription():
    patient_id = request.args.get('patient_id')
    conn = get_db_connection()
    if not conn: return jsonify({'found': False, 'message': 'DB Error'}), 500

    try:
        cur = conn.cursor()
        
        # 1. Cari resep yang statusnya 'processed' (HURUF KECIL SESUAI DATABASE)
        cur.execute("""
            SELECT id FROM prescriptions 
            WHERE patient_id = %s AND status = 'processed'
            ORDER BY created_at DESC LIMIT 1
        """, (patient_id,))
        
        presc = cur.fetchone()
        
        if not presc:
            return jsonify({'found': False, 'message': 'Tidak ada resep siap bayar (processed) untuk pasien ini.'})

        # 2. Ambil detail obat
        presc_id = presc['id']
        cur.execute("""
            SELECT 
                m.name, 
                m.drug_category, 
                pd.qty, 
                pd.price_snapshot as price,
                m.kfa_code as code
            FROM prescription_details pd
            JOIN medicines m ON pd.medicine_id = m.id
            WHERE pd.prescription_id = %s
        """, (presc_id,))
        
        items = cur.fetchall()
        
        # 3. Update status menjadi 'billed' (HURUF KECIL JUGA BIAR KONSISTEN)
        cur.execute("UPDATE prescriptions SET status = 'billed' WHERE id = %s", (presc_id,))
        conn.commit()
        
        cur.close()
        conn.close()
        return jsonify({'found': True, 'items': items})

    except Exception as e:
        return jsonify({'found': False, 'message': str(e)}), 500

# --- API 4: INPUT ITEM MANUAL (ICD-9 & ICD-10) ---
@app.route('/api/master-data', methods=['GET'])
def search_master_data():
    query = request.args.get('q', '').lower()
    conn = get_db_connection()
    if not conn: return jsonify([]), 500

    try:
        cur = conn.cursor()
        search_term = f"%{query}%"
        results = []
        
        # 1. Cari ICD-10 (Diagnosa)
        try:
            cur.execute("""
                SELECT name, price, 'icd10' as type, code 
                FROM tariff_icd10 
                WHERE name ILIKE %s OR code ILIKE %s LIMIT 5
            """, (search_term, search_term))
            results.extend(cur.fetchall())
        except Exception: pass

        # 2. Cari ICD-9 (Prosedur/Tindakan)
        try:
            cur.execute("""
                SELECT name, price, 'icd9' as type, code 
                FROM tariff_icd9 
                WHERE name ILIKE %s OR code ILIKE %s LIMIT 5
            """, (search_term, search_term))
            results.extend(cur.fetchall())
        except Exception: pass

        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify([]), 500

# --- API 5: CREATE INVOICE (FIX: HAPUS SUBTOTAL DARI INSERT) ---
@app.route('/api/create-invoice', methods=['POST'])
def create_invoice():
    data = request.json
    patient_id = data.get('patient_id')
    items = data.get('items', [])
    total_final = data.get('total_final', 0)

    if not patient_id or not items:
        return jsonify({'success': False, 'error': 'Data tidak lengkap'}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # 1. Header Invoice
        invoice_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO invoices (id, patient_id, status, created_at, total_amount)
            VALUES (%s, %s, 'unpaid', NOW(), %s)
        """, (invoice_id, patient_id, total_final))
        
        # 2. Detail Invoice
        for item in items:
            price = float(item['price'])
            qty = int(item['qty'])
            # subtotal dihitung otomatis oleh database, jadi TIDAK PERLU dikirim
            
            cur.execute("""
                INSERT INTO invoice_details (id, invoice_id, item_type, item_code, item_name, price, qty)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), invoice_id, item.get('type', 'manual'),
                item.get('code', '-'), item['name'], price, qty
            ))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'success': True, 'invoice_id': invoice_id})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)