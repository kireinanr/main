import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import uuid

app = Flask(__name__)
CORS(app)

# Database Connection
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
        # Ambil data asuransi dan persentase coverage (default 0 jika null)
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

# --- API 3: TARIK RESEP DARI DOKTER (PENTING!) ---
@app.route('/api/get-prescription', methods=['GET'])
def get_prescription():
    patient_id = request.args.get('patient_id')
    conn = get_db_connection()
    if not conn: return jsonify({'found': False, 'message': 'DB Error'}), 500

    try:
        cur = conn.cursor()
        # 1. Cari Resep Terakhir Pasien yang Statusnya 'WAITING PAYMENT'
        cur.execute("""
            SELECT id FROM prescriptions 
            WHERE patient_id = %s AND status = 'WAITING PAYMENT'
            ORDER BY created_at DESC LIMIT 1
        """, (patient_id,))
        
        presc = cur.fetchone()
        
        if not presc:
            return jsonify({'found': False, 'message': 'Tidak ada resep baru untuk pasien ini.'})

        # 2. Ambil Detail Obatnya
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
        
        # 3. Update Status Resep jadi 'PROCESSED' agar tidak ditarik 2 kali
        cur.execute("UPDATE prescriptions SET status = 'PROCESSED' WHERE id = %s", (presc_id,))
        conn.commit()
        
        cur.close()
        conn.close()
        return jsonify({'found': True, 'items': items})

    except Exception as e:
        print(e)
        return jsonify({'found': False, 'message': str(e)}), 500

# --- API 4: CARI ITEM MANUAL (Master Data) ---
@app.route('/api/master-data', methods=['GET'])
def search_master_data():
    query = request.args.get('q', '').lower()
    conn = get_db_connection()
    if not conn: return jsonify([]), 500

    try:
        cur = conn.cursor()
        search_term = f"%{query}%"
        
        results = []
        
        # A. Cari Obat
        cur.execute("""
            SELECT name, selling_price as price, 'drug' as type, kfa_code as code 
            FROM medicines 
            WHERE name ILIKE %s AND is_active = true LIMIT 5
        """, (search_term,))
        results.extend(cur.fetchall())
        
        # B. Cari Tindakan (ICD 10 Tariff)
        cur.execute("""
            SELECT name, price, 'procedure' as type, code 
            FROM tariff_icd10 
            WHERE name ILIKE %s LIMIT 5
        """, (search_term,))
        results.extend(cur.fetchall())
        
        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify([]), 500

# --- API 5: BUAT INVOICE ---
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
            VALUES (%s, %s, 'paid', NOW(), %s)
        """, (invoice_id, patient_id, total_final))
        
        # 2. Detail Invoice
        for item in items:
            # Pastikan harga dan qty aman
            price = float(item['price'])
            qty = int(item['qty'])
            subtotal = price * qty
            
            cur.execute("""
                INSERT INTO invoice_details (id, invoice_id, item_type, item_code, item_name, price, qty, subtotal)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), 
                invoice_id, 
                item.get('type', 'drug'),
                item.get('code', '-'), 
                item['name'], 
                price, 
                qty, 
                subtotal
            ))

        # 3. Simpan Pembayaran (Langsung Lunas)
        cur.execute("""
            INSERT INTO payments (id, invoice_id, amount, method, created_at)
            VALUES (%s, %s, %s, 'CASH', NOW())
        """, (str(uuid.uuid4()), invoice_id, total_final))

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