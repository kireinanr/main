# DEPLOYMENT GUIDE - EAS SIMRS Payment System

## Persiapan Awal

### 1. Pastikan File Siap
```
EAS_SIMRS_PAYMENT-main/
├── Billing_backend.py        ✅
├── Billing_frontend.html     ✅
├── Payment_backend.py        ✅
├── Payment_frontend.html     ✅
├── requirements.txt          ✅ (baru dibuat)
├── Procfile                  ✅ (baru dibuat)
├── .gitignore                ✅ (baru dibuat)
├── .env                      ⚠️  (JANGAN PUSH - lokal only)
└── README.md                 ✅ (baru dibuat)
```

### 2. Update .env (Lokal - JANGAN PUSH)
```
DATABASE_URL=postgresql://user:password@host:5432/database
```

---

## STEP 1: Upload ke GitHub

### A. Buat Repository Baru
1. Buka https://github.com/new
2. Nama: `EAS-SIMRS-Payment-Backend` atau nama lain
3. Visibility: Private (jangan public karena ada credentials)
4. Create Repository

### B. Push dari Local
```powershell
cd "C:\Users\FUJITSU U939\Downloads\EAS_SIMRS_PAYMENT-main"

# Init git (kalau belum)
git init
git add .
git commit -m "Initial commit: Billing & Payment backend"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/EAS-SIMRS-Payment-Backend.git
git push -u origin main
```

---

## STEP 2: Deploy Backend ke Render

### A. Login ke Render
1. Buka https://render.com
2. Sign up atau login pakai GitHub
3. Click "New +" → "Web Service"

### B. Connect GitHub Repo
1. Select repo: `EAS-SIMRS-Payment-Backend`
2. Branch: `main`

### C. Configure
- **Name**: `billing-backend` (atau `eas-simrs-billing`)
- **Environment**: `Python 3`
- **Build Command**: 
  ```
  pip install -r requirements.txt
  ```
- **Start Command**: 
  ```
  gunicorn Billing_backend:app
  ```
- **Instance Type**: Free (untuk testing)

### D. Environment Variables (Render Dashboard)
Click "Environment" dan add:
```
DATABASE_URL = postgresql://user:password@host:5432/database
```

### E. Deploy
Click "Create Web Service" → tunggu ~2-3 menit

### F. Dapatkan URL
Setelah deploy sukses, Render kasih URL seperti:
```
https://billing-backend-xxxx.onrender.com
```
**Salin URL ini!** (akan dipakai di frontend)

---

## STEP 3: Update Frontend

### A. Edit HTML File
Buka `Billing_frontend.html` (atau file HTML manapun yang ada API calls)

Cari line dengan `localhost:5000` atau `API_URL` dan replace dengan:
```javascript
const API_URL = 'https://billing-backend-xxxx.onrender.com';
```

Contoh sebelum:
```javascript
const API_URL = 'http://localhost:5000';
```

Contoh sesudah:
```javascript
const API_URL = 'https://billing-backend-xxxx.onrender.com';
```

### B. Push ke GitHub
```powershell
git add Billing_frontend.html
git commit -m "Update API URL for Render deployment"
git push
```

---

## STEP 4: Deploy Frontend ke Vercel

### A. Buat Repository Frontend Baru
1. Buka https://github.com/new
2. Nama: `EAS-SIMRS-Frontend` atau `billing-portal`
3. Visibility: Public (frontend boleh public)
4. Create repo

### B. Upload File Frontend
```powershell
# Buat folder baru untuk frontend
mkdir "C:\frontend-eas-simrs"
cd "C:\frontend-eas-simrs"

# Copy HTML, CSS, JS files
copy "C:\Users\FUJITSU U939\Downloads\EAS_SIMRS_PAYMENT-main\Billing_frontend.html" index.html
copy "C:\Users\FUJITSU U939\Downloads\EAS_SIMRS_PAYMENT-main\*.html" .

# Init git
git init
git add .
git commit -m "Initial frontend commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/EAS-SIMRS-Frontend.git
git push -u origin main
```

### C. Deploy ke Vercel
1. Buka https://vercel.com
2. Sign up/login pakai GitHub
3. Click "Add New..." → "Project"
4. Import repository: `EAS-SIMRS-Frontend`
5. Click "Deploy"
6. Tunggu ~1 menit

### D. Dapatkan URL
Vercel kasih URL seperti:
```
https://eas-simrs-frontend.vercel.app
```

---

## STEP 5: Testing

### Test Backend
```
https://billing-backend-xxxx.onrender.com/api/patients?q=nama
```

Harusnya return JSON list pasien.

### Test Frontend
```
https://eas-simrs-frontend.vercel.app
```

Harusnya load HTML + bisa search pasien.

---

## Troubleshooting

### ❌ Backend error saat deploy
**Solusi:**
1. Check Render logs: Dashboard → Web Service → Logs
2. Pastikan DATABASE_URL correct
3. Pastikan psycopg2-binary ada di requirements.txt

### ❌ Frontend tidak bisa fetch API
**Solusi:**
1. Buka DevTools (F12) → Console
2. Check error message
3. Pastikan API_URL di HTML sudah update ke Render URL
4. Pastikan backend sudah online

### ❌ CORS error
**Solusi:**
Pastikan di `Billing_backend.py` ada:
```python
from flask_cors import CORS
CORS(app)
```

---

## Monitoring & Logs

### Render
- Dashboard → Web Service → Logs (real-time)

### Vercel
- Dashboard → Project → Deployments → Logs

---

## Next Steps (Opsional)

1. **Custom Domain**: Beli domain (Namecheap, Google Domains) dan point ke Render/Vercel
2. **Database Backup**: Setup automated backups di Supabase
3. **Monitoring**: Pakai Sentry atau LogRocket untuk error tracking
4. **CI/CD**: Render & Vercel auto-deploy saat push ke GitHub

---

**Pertanyaan? Cek logs di Render & Vercel dashboard!**
