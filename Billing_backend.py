from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
import os
import decimal

app = Flask(__name__)
CORS(app)

# --- ROOT ROUTE ---
@app.route('/')
def home():
    return send_file('Billing_frontend.html') 

class Database:
    def __init__(self):
        self.db_host = "aws-1-ap-south-1.pooler.supabase.com"
        self.db_port = "5432"
        self.db_name = "postgres"
        self.db_user = "postgres.esmhvcfemenpmpciiucz"
        self.db_pass = "SEMOGADAPATA"
    
    def get_connection(self):
        dsn = f"postgresql://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}?sslmode=require"
        return psycopg2.connect(dsn)

# API CARI PASIEN
@app.route('/api/patients', methods=['GET'])
def search_patients():
    q = request.args.get('q', '')
    conn = Database().get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT id, full_name, mr_no FROM patients WHERE full_name ILIKE %s OR mr_no ILIKE %s LIMIT 5", (f"%{q}%", f"%{q}%"))
        return jsonify(cur.fetchall())
    finally:
        conn.close()

# API CARI ICD (MANUAL)
@app.route('/api/master-data', methods=['GET'])
def search_master():
    q = request.args.get('q', '')
    conn = Database().get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        sql = "SELECT id::text, code, name, price, 'icd10' as type FROM tariff_icd10 WHERE name ILIKE %s OR code ILIKE %s UNION ALL SELECT id::text, code, name, price, 'icd9' as type FROM tariff_icd9 WHERE name ILIKE %s OR code ILIKE %s LIMIT 20"
        wildcard = f"%{q}%"
        cur.execute(sql, (wildcard, wildcard, wildcard, wildcard))
        
        raw_items = cur.fetchall()
        clean_items = []
        for item in raw_items:
            i = dict(item)
            i['price'] = float(i['price']) if i['price'] else 0.0
            clean_items.append(i)
        return jsonify(clean_items)
    finally:
        conn.close()

# --- FIX FINAL: GET RESEP (Dengan Kategori Obat) ---
@app.route('/api/get-prescription', methods=['GET'])
def get_patient_prescription():
    patient_id = request.args.get('patient_id')
    conn = Database().get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # UPDATE SQL: Kita ambil kolom 'm.drug_category'
        sql = """
            SELECT 
                m.kfa_code as code, 
                m.name, 
                m.drug_category,   -- INI YANG KITA TAMBAHKAN
                pd.qty,
                pd.subtotal,       
                pd.price_snapshot, 
                m.selling_price,    
                'drug' as type
            FROM prescriptions p
            JOIN visits v ON p.visit_id = v.id
            JOIN prescription_details pd ON p.id = pd.prescription_id
            JOIN medicines m ON pd.medicine_id = m.id
            WHERE v.patient_id = %s AND p.status = 'WAITING PAYMENT'
        """
        cur.execute(sql, (patient_id,))
        items = cur.fetchall()
        
        safe_items = []
        for i in items:
            row = dict(i)
            qty = int(row['qty']) if row['qty'] and row['qty'] > 0 else 1
            final_unit_price = 0.0

            # Logika Harga (Subtotal -> Snapshot -> Master)
            if row['subtotal'] is not None and float(row['subtotal']) > 0:
                final_unit_price = float(row['subtotal']) / qty
            elif row['price_snapshot'] is not None and float(row['price_snapshot']) > 0:
                 final_unit_price = float(row['price_snapshot'])
            elif row['selling_price'] is not None:
                final_unit_price = float(row['selling_price'])
            
            row['price'] = final_unit_price
            row['qty'] = qty
            
            # Pastikan kategori ada (default 'non-generik' jika kosong)
            if not row.get('drug_category'):
                row['drug_category'] = 'non-generik'
            
            # Bersihkan data mentah
            row.pop('subtotal', None); row.pop('price_snapshot', None); row.pop('selling_price', None)
            safe_items.append(row)

        if not safe_items: 
            return jsonify({"found": False, "message": "Tidak ada resep WAITING PAYMENT."})
            
        return jsonify({"found": True, "items": safe_items})
    finally:
        conn.close()

# API ASURANSI
@app.route('/api/insurances', methods=['GET'])
def get_insurances():
    conn = Database().get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT i.id, i.name, COALESCE(ic.coverage_percentage, 100) as pct FROM insurances i LEFT JOIN insurance_coverages ic ON i.id = ic.insurance_id")
        return jsonify(cur.fetchall())
    finally:
        conn.close()

# API SIMPAN TAGIHAN
# --- FUNGSI SIMPAN TAGIHAN (FIX: Subtotal Otomatis by Database) ---
@app.route('/api/create-invoice', methods=['POST'])
def create_invoice():
    data = request.json
    conn = Database().get_connection()
    cur = conn.cursor()
    try:
        # 1. Buat ID Invoice & Detail ID
        new_id = str(uuid.uuid4())
        
        # 2. Simpan Header Invoice
        cur.execute("""
            INSERT INTO invoices (id, patient_id, total_amount, status) 
            VALUES (%s, %s, %s, 'unpaid')
        """, (new_id, data['patient_id'], data['total_final']))
        
        # 3. Simpan Detail Item (TANPA SUBTOTAL)
        # Database akan menghitung subtotal sendiri: price * qty
        for item in data['items']:
            detail_id = str(uuid.uuid4())
            safe_price = float(item['price']) if item['price'] else 0.0
            qty = int(item['qty'])

            # HAPUS 'subtotal' DARI SINI
            cur.execute("""
                INSERT INTO invoice_details 
                (id, invoice_id, item_type, item_code, item_name, price, qty) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (detail_id, new_id, item['type'], item['code'], item['name'], safe_price, qty))
        
        conn.commit()
        return jsonify({"success": True, "invoice_id": new_id})

    except Exception as e:
        conn.rollback()
        print(f"❌ ERROR SAVE: {e}") 
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    print("🚀 SERVER BILLING (Port 5000)...")
    app.run(port=5000, debug=True)