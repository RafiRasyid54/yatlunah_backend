import uuid
from fastapi import FastAPI, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy import text 
from datetime import date, timedelta
from . import models, schemas, auth, database
from pydantic import BaseModel 
from app.database import get_db  # Import fungsi get_db kamu
from typing import Optional # Pastikan import ini ada di bagian atas main.py

app = FastAPI(title="Yatlunah API Gateway")

# Sinkronkan database saat startup
models.Base.metadata.create_all(bind=database.engine)

@app.get("/")
def read_root():
    return {
        "nama_aplikasi": "Yatlunah API",
        "status": "Running",
        "pesan": "Selamat datang di ekosistem Yatlunah!"
    }

# --- 1. AUTHENTICATION ---

@app.post("/register", status_code=status.HTTP_201_CREATED, response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    
    role_name = user.role.lower().strip() if user.role else "santri"
    
    if role_name == "admin":
        r_id = 3
    elif role_name == "adminmitra": # ✅ TAMBAHKAN LOGIKA UNTUK ADMIN MITRA
        r_id = 4
    elif role_name == "guru":
        r_id = 2
    else:
        role_name = "santri"
        r_id = 1

    new_user = models.User(
        nama_lengkap=user.nama_lengkap,
        email=user.email,
        password_hash=auth.hash_password(user.password),
        role=role_name,
        role_id=r_id,
        id_mitra=user.id_mitra # ✅ SIMPAN ID MITRA KE DATABASE
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/login")
def login_user(user: schemas.UserLogin, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Email atau password salah")
    
    clean_role = db_user.role.lower().strip()
    
    return {
        "status": "success", 
        "user_id": str(db_user.user_id), 
        "nama_lengkap": db_user.nama_lengkap,
        "email": db_user.email,
        "role": clean_role,
        "id_mitra": str(db_user.id_mitra) if db_user.id_mitra else None # ✅ TAMBAHKAN BARIS INI
    }

# --- 2. JILID & MATERI ---
@app.get("/jilid/list")
def get_all_jilid(db: Session = Depends(database.get_db)):
    return db.query(models.JilidInfo).order_by(models.JilidInfo.nomor_jilid.asc()).all()

@app.get("/audio/mapping/{jilid_id}/{page}")
def get_audio_for_page(jilid_id: int, page: int, db: Session = Depends(database.get_db)):
    mapping = db.query(models.AudioMapping).filter(
        models.AudioMapping.jilid_id == jilid_id,
        models.AudioMapping.page_start <= page,
        models.AudioMapping.page_end >= page
    ).first()
    
    if not mapping:
        return {"audio_url": None, "judul_materi": "Materi Umum"}
    return {"audio_url": mapping.audio_url, "judul_materi": mapping.judul_materi}

# --- 3. SETORAN & PENILAIAN ---
@app.post("/setoran/tambah")
def tambah_setoran(request: schemas.SetoranCreate, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.user_id == request.user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User tidak ditemukan")
    new_setoran = models.Setoran(
        user_id=request.user_id, nama_lengkap=user.nama_lengkap,
        jilid=request.jilid, halaman=request.halaman, audio_url=request.audio_url, status="pending" 
    )
    db.add(new_setoran)
    db.commit()
    return {"status": "success", "message": "Setoran disimpan!"}

@app.get("/setoran/antrean/{jilid_id}")
def get_antrean_setoran(jilid_id: int, db: Session = Depends(database.get_db)):
    return db.query(models.Setoran).filter(models.Setoran.jilid == jilid_id, models.Setoran.status == "pending").all()

@app.post("/setoran/nilai")
def beri_nilai_setoran(req: schemas.SetoranPenilaian, db: Session = Depends(database.get_db)):
    # 1. Cari data setoran yang dinilai
    setoran = db.query(models.Setoran).filter(models.Setoran.id == req.setoran_id).first()
    if not setoran:
        raise HTTPException(status_code=404, detail="Data setoran tidak ditemukan")
    
    # 2. Ambil data guru penilai
    guru = db.query(models.User).filter(models.User.user_id == req.id_guru_penilai).first()

    # 3. Update data penilaian di tabel setoran
    setoran.nilai = req.nilai
    setoran.catatan = req.catatan
    setoran.id_guru_penilai = req.id_guru_penilai
    setoran.nama_penilai = guru.nama_lengkap if guru else "Guru"
    setoran.status = "dinilai"
    
    # --- LOGIKA OTOMATISASI PROGRESS ---
    # Jika nilai di atas 70 (Anggap Lulus), update jilid & halaman di profil santri
    if req.nilai >= 70:
        # Cari user (santri) yang memiliki setoran ini
        santri = db.query(models.User).filter(models.User.user_id == setoran.user_id).first()
        if santri:
            # Update progress terakhir santri
            santri.last_jilid = setoran.jilid
            santri.last_halaman = setoran.halaman
            print(f"DEBUG: Progress {santri.nama_lengkap} diupdate ke Jilid {setoran.jilid} Hal {setoran.halaman}")

    try:
        db.commit()
        return {"status": "success", "message": "Penilaian berhasil dan progress santri diperbarui"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal update: {str(e)}")

# --- 4. PROGRESS & STATS ---
@app.get("/users/{user_id}/stats", response_model=schemas.UserStatsResponse)
def get_user_stats(user_id: str, db: Session = Depends(database.get_db)):
    last_log = db.query(models.LogBelajar).filter(models.LogBelajar.user_id == user_id).order_by(models.LogBelajar.id.desc()).first()
    if not last_log: return {"current_streak": 0, "last_jilid": 1, "last_halaman": 0, "total_progress": 0.0}
    return {"current_streak": 5, "last_jilid": last_log.jilid, "last_halaman": last_log.halaman, "total_progress": 0.5}

@app.get("/users/{user_id}/riwayat")
def get_riwayat_user(user_id: str, db: Session = Depends(database.get_db)):
    riwayat = db.query(models.Setoran).filter(
        models.Setoran.user_id == user_id
    ).order_by(models.Setoran.created_at.desc()).all()
    return riwayat

# --- 5. MANAGEMENT USER (ADMIN) ---

@app.get("/admin/users/count")
def get_users_count(db: Session = Depends(database.get_db)):
    s = db.query(models.User).filter(models.User.role.ilike("santri")).count()
    g = db.query(models.User).filter(models.User.role.ilike("guru")).count()
    a = db.query(models.User).filter(models.User.role.ilike("admin")).count()
    
    return {
        "santri": s,
        "guru": g,
        "admin": a
    }

@app.get("/admin/users/{role}")
def get_users_by_role(role: str, id_mitra: Optional[str] = None, db: Session = Depends(database.get_db)):
    # Query dasar untuk filter berdasarkan role
    query = db.query(models.User).filter(func.trim(func.lower(models.User.role)) == role.lower().strip())
    
    # ✅ JIKA id_mitra DIKIRIM DARI ANDROID, FILTER DATANYA!
    if id_mitra:
        query = query.filter(models.User.id_mitra == id_mitra)
        
    return query.all()
@app.put("/admin/users/{user_id}/role")
def update_role_admin(user_id: str, new_role: str, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    if new_role not in ["santri", "guru", "admin"]:
        raise HTTPException(status_code=400, detail="Role tidak valid")
        
    user.role = new_role
    db.commit()
    return {"status": "success", "message": f"Role {user.nama_lengkap} berhasil diubah"}

@app.post("/user/update-role")
async def update_role_form(
    id: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(database.get_db)
):
    print(f"DEBUG: Request Masuk -> ID: {id}, Role: {role}")
    user = db.query(models.User).filter(models.User.user_id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    role_input = role.lower().strip()
    
    if role_input in ["santri", "user"]:
        target_role = "santri"
        target_id = 1
    elif role_input == "guru":
        target_role = "guru"
        target_id = 2
    elif role_input == "admin":
        target_role = "admin"
        target_id = 3
    else:
        raise HTTPException(status_code=400, detail=f"Role '{role_input}' tidak dikenal")

    try:
        user.role = target_role      
        user.role_id = target_id      
        db.commit()
        return {"status": "success", "message": f"Role berhasil diubah menjadi {target_role}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Gagal menyimpan ke database")

# --- 6. MANAJEMEN QUOTES ---
# --- MANAJEMEN QUOTES ---

@app.get("/quotes/random", response_model=schemas.QuoteResponse)
def get_random_quote(db: Session = Depends(database.get_db)):
    quote = db.query(models.QuotesHarian).order_by(func.random()).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Database quote kosong")
    return quote

@app.get("/admin/quotes", response_model=list[schemas.QuoteResponse])
def get_all_quotes(db: Session = Depends(database.get_db)):
    return db.query(models.QuotesHarian).all()
# app/main.py

# --- ENDPOINT TAMBAH (POST) ---
@app.post("/admin/quotes", response_model=schemas.QuoteResponse)
def tambah_quote(quote: schemas.QuoteCreate, db: Session = Depends(database.get_db)):
    new_quote = models.QuotesHarian(
        teks_quote=quote.teks_quote,
        sumber=quote.sumber,
        hari=quote.hari  # Menyimpan pilihan hari (Senin, Selasa, dll)
    )
    db.add(new_quote)
    db.commit()
    db.refresh(new_quote)
    return new_quote

# --- ENDPOINT UPDATE (PUT) ---
@app.put("/admin/quotes/{quote_id}")
def update_quote(quote_id: int, quote: schemas.QuoteCreate, db: Session = Depends(database.get_db)):
    db_quote = db.query(models.QuotesHarian).filter(models.QuotesHarian.id == quote_id).first()
    
    if not db_quote:
        raise HTTPException(status_code=404, detail="Quote tidak ditemukan")
    
    # Update semua field termasuk hari
    db_quote.teks_quote = quote.teks_quote
    db_quote.sumber = quote.sumber
    db_quote.hari = quote.hari 
    
    db.commit()
    return {"status": "success", "message": f"Quote hari {quote.hari} berhasil diperbarui"}


@app.get("/admin/quotes/filter", response_model=schemas.QuoteResponse)
def get_quote_by_hari(hari: str, db: Session = Depends(database.get_db)):
    # Gunakan func.lower agar pencarian "Rabu" atau "rabu" tetap ketemu
    quote = db.query(models.QuotesHarian).filter(
        func.lower(models.QuotesHarian.hari) == hari.lower()
    ).first()
    
    if not quote:
        # Jika tidak ada untuk hari tersebut, ambil satu secara acak
        quote = db.query(models.QuotesHarian).order_by(func.random()).first()
        
    if not quote:
        raise HTTPException(status_code=404, detail="Database quote kosong")
        
    return quote

@app.delete("/admin/quotes/{quote_id}")
def delete_quote(quote_id: int, db: Session = Depends(database.get_db)):
    db_quote = db.query(models.QuotesHarian).filter(models.QuotesHarian.id == quote_id).first()
    if not db_quote:
        raise HTTPException(status_code=404, detail="Quote ID tidak ditemukan")
    try:
        db.delete(db_quote)
        db.commit()
        return {"status": "success", "message": f"Quote ID {quote_id} berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Gagal menghapus data")
# --- 7. BIMBINGAN (WORKFLOW GURU & SANTRI) ---

# A. User Mendaftar Bimbingan
@app.post("/rest/v1/bimbingan")
async def buat_bimbingan(data: schemas.BimbinganRequest, db: Session = Depends(database.get_db)):
    try:
        query = text("""
            INSERT INTO bimbingan (user_id, jenis_bimbingan, status, tanggal_daftar)
            VALUES (:u_id, :jenis, :stat, :tgl)
        """)
        db.execute(query, {
            "u_id": data.user_id, 
            "jenis": data.jenis_bimbingan, 
            "stat": data.status,
            "tgl": data.tanggal_daftar
        })
        db.commit()
        return {"status": "success", "message": "Pendaftaran Berhasil!"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


# D. Santri Melihat Riwayat Bimbingannya Sendiri
@app.get("/rest/v1/bimbingan/user/{user_id}")
def get_riwayat_bimbingan_user(user_id: str, db: Session = Depends(database.get_db)):
    try:
        query = text("""
            SELECT id, jenis_bimbingan, status, tanggal_daftar 
            FROM bimbingan 
            WHERE user_id = :uid
            ORDER BY id DESC
        """)
        result = db.execute(query, {"uid": user_id}).fetchall()
        
        riwayat = [{"id": r[0], "jenis_bimbingan": r[1], "status": r[2], "tanggal_daftar": r[3]} for r in result]
        return {"status": "success", "data": riwayat}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/rest/v1/bimbingan/menunggu")
def get_bimbingan_menunggu(db: Session = Depends(database.get_db)):
    try:
        query = text("""
            SELECT b.id, b.user_id, u.nama_lengkap as nama_santri, b.jenis_bimbingan, b.status, b.tanggal_daftar 
            FROM bimbingan b
            JOIN users u ON b.user_id = u.user_id
            WHERE b.status = 'Menunggu'
            ORDER BY b.id ASC
        """)
        result = db.execute(query).fetchall()
        
        daftar_bimbingan = []
        for row in result:
            daftar_bimbingan.append({
                "id": row[0],
                "user_id": row[1],
                "nama_santri": row[2], # <--- Nama Asli Santri masuk di sini!
                "jenis_bimbingan": row[3],
                "status": row[4],
                "tanggal_daftar": row[5]
            })
            
        return {"status": "success", "data": daftar_bimbingan}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================

# ✅ 3. PERBAIKAN RUTE PUT (Menyimpan id_guru ke Database)
@app.put("/rest/v1/bimbingan/{bimbingan_id}")
def update_status_bimbingan(bimbingan_id: int, req: schemas.UpdateStatusRequest, db: Session = Depends(database.get_db)):
    try:
        # Jika status yang dikirim adalah Diterima/Aktif
        if req.status.lower() in ["diterima", "aktif"]:
            
            # Pastikan id_guru dikirim oleh Android
            if not req.id_guru:
                return {"status": "error", "message": "ID Guru tidak boleh kosong saat menerima bimbingan!"}

            # SQL Update ditambahkan "id_guru = :id_guru"
            query = text("""
                UPDATE bimbingan 
                SET status = 'Diterima', id_guru = :id_guru 
                WHERE id = :id AND status = 'Menunggu'
            """)
            result = db.execute(query, {"id_guru": req.id_guru, "id": bimbingan_id})
            db.commit()

            if result.rowcount == 0:
                return {"status": "error", "message": "Maaf, bimbingan ini sudah diambil oleh guru lain."}
                
            return {"status": "success", "message": "Alhamdulillah, bimbingan diterima!"}

        # Jika ditolak
        else:
            query = text("UPDATE bimbingan SET status = :status WHERE id = :id")
            db.execute(query, {"status": req.status, "id": bimbingan_id})
            db.commit()
            return {"status": "success", "message": f"Bimbingan berhasil {req.status}."}

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    
# --- PERBAIKAN STATUS BIMBINGAN (Agar Nama Guru Muncul di Android) ---
@app.get("/rest/v1/bimbingan/status/{user_id}")
def get_status_bimbingan_santri(user_id: str, db: Session = Depends(database.get_db)):
    try:
        query = text("""
            SELECT b.status, u.nama_lengkap as nama_guru
            FROM bimbingan b
            LEFT JOIN users u ON b.id_guru = u.user_id
            WHERE b.user_id = :user_id
            ORDER BY b.tanggal_daftar DESC
            LIMIT 1
        """)
        result = db.execute(query, {"user_id": user_id}).fetchone()
        
        if not result:
            return {"status": "success", "data": []}
            
        return {
            "status": "success", 
            "data": [{
                "status": result[0],
                "nama_guru": result[1] or "Ustadz/ah" # GANTI KEY MENJADI nama_guru
            }]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
@app.post("/latihan-soal", response_model=schemas.LatihanSoalResponse)
def tambah_soal_latihan(soal: schemas.LatihanSoalCreate, db: Session = Depends(database.get_db)):
    try:
        new_soal = models.LatihanSoal(
            jilid_id=soal.jilid_id,
            halaman_target=soal.halaman_target,
            kategori=soal.kategori,
            pertanyaan=soal.pertanyaan,
            pilihan_jawaban=soal.pilihan_jawaban,
            kunci_jawaban=soal.kunci_jawaban
        )
        db.add(new_soal)
        db.commit()
        db.refresh(new_soal)
        return new_soal
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint 2: Untuk Santri mengecek soal di halaman tertentu (PDF Viewer)
@app.get("/latihan-soal/check", response_model=list[schemas.LatihanSoalResponse])
def get_soal_by_mapping(jilid: int, halaman: int, db: Session = Depends(database.get_db)):
    soal_list = db.query(models.LatihanSoal).filter(
        models.LatihanSoal.jilid_id == jilid,
        models.LatihanSoal.halaman_target == halaman
    ).all()
    
    # Akan mengembalikan list kosong [] jika tidak ada soal di halaman tersebut
    return soal_list

# Endpoint 3: Untuk menyimpan hasil skor latihan Santri
@app.post("/latihan-soal/progres")
def simpan_progres_latihan(progres: schemas.ProgresLatihanCreate, db: Session = Depends(database.get_db)):
    # Cek apakah santri sudah pernah mengerjakan latihan di halaman ini
    existing_progres = db.query(models.ProgresLatihan).filter(
        models.ProgresLatihan.user_id == progres.user_id,
        models.ProgresLatihan.jilid_id == progres.jilid_id,
        models.ProgresLatihan.halaman_latihan == progres.halaman_latihan
    ).first()

    if existing_progres:
        # Jika mengulang latihan, update skornya
        existing_progres.skor = progres.skor
    else:
        # Jika baru pertama kali mengerjakan, buat data baru
        new_progres = models.ProgresLatihan(
            user_id=progres.user_id,
            jilid_id=progres.jilid_id,
            halaman_latihan=progres.halaman_latihan,
            skor=progres.skor
        )
        db.add(new_progres)
    
    try:
        db.commit()
        return {"status": "success", "message": "Progres latihan berhasil disimpan"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/latihan-soal/all", response_model=list[schemas.LatihanSoalResponse])
def get_all_soal(db: Session = Depends(database.get_db)):
    return db.query(models.LatihanSoal).all()

@app.delete("/latihan-soal/{soal_id}")
def delete_soal(soal_id: int, db: Session = Depends(database.get_db)):
    soal = db.query(models.LatihanSoal).filter(models.LatihanSoal.id == soal_id).first()
    if not soal:
        raise HTTPException(status_code=404, detail="Soal tidak ditemukan")
    db.delete(soal)
    db.commit()
    return {"message": "Soal berhasil dihapus"}