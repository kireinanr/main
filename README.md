# EAS SIMRS Payment System

Backend API untuk sistem billing & asuransi SIMRS.

## Setup Lokal

```bash
pip install -r requirements.txt
python Billing_backend.py
```

Server akan jalan di `http://localhost:5000`

## Environment Variables

Buat file `.env`:
```
DATABASE_URL=postgresql://user:password@host:5432/database
```

## Deploy ke Render

1. Push ke GitHub
2. Di Render: New Web Service
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn Billing_backend:app`
5. Add Environment Variables di Settings

## API Endpoints

- `GET /` - Frontend HTML
- `GET /api/patients` - Cari pasien
- `GET /api/insurances` - List asuransi
- `POST /api/create-invoice` - Buat invoice
