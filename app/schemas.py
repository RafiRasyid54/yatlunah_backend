from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from typing import List, Optional
from uuid import UUID
from datetime import date

# --- USER SCHEMAS ---
class UserBase(BaseModel):
    email: str
    nama_lengkap: str
    role: Optional[str] = "santri"
    id_mitra: Optional[str] = None 

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(UserBase):
    user_id: UUID 
    created_at: Optional[datetime] = None 
    model_config = ConfigDict(from_attributes=True)

# --- SETORAN SCHEMAS ---

# Saat Santri upload setoran
class SetoranCreate(BaseModel):
    user_id: UUID # Menggunakan UUID agar sinkron dengan database
    jilid: int
    halaman: int
    audio_url: str
    nama_lengkap: Optional[str] = None # Bisa dikirim dari Android atau diisi di Backend

# Saat Guru melihat antrean
class SetoranResponse(BaseModel):
    id: int
    user_id: UUID
    nama_lengkap: Optional[str]
    jilid: int
    halaman: int
    audio_url: str
    status: str
    nilai: Optional[int] = None
    catatan: Optional[str] = None
    id_guru_penilai: Optional[UUID] = None # ✅ Disamakan dengan models.py
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Saat Guru mengirim nilai dari Android
# --- Di schemas.py ---

class SetoranPenilaian(BaseModel):
    setoran_id: int 
    nilai: int
    catatan: Optional[str] = None
    id_guru_penilai: UUID    # Pastikan ini UUID sesuai diskusi kita sebelumnya
# --- JILID & STATS ---
class JilidData(BaseModel):
    nomor_jilid: int
    judul_jilid: str
    pdf_url: str
    file_size: Optional[str] = None
    total_halaman: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class UserStatsResponse(BaseModel):
    current_streak: int
    last_jilid: int
    last_halaman: int
    total_progress: float
    model_config = ConfigDict(from_attributes=True)

    # --- QUOTES SCHEMAS ---

class QuoteCreate(BaseModel):
    teks_quote: str
    sumber: str
    hari: Optional[str] = None  # <--- PASTIKAN BARIS INI ADA DAN FILE DISIMPAN (CTRL+S)

class QuoteResponse(BaseModel):
    id: int
    teks_quote: str
    sumber: str
    hari: Optional[str] = None

class Config:
    from_attributes = True

# 2. Schema/Model (Ini yang biasanya ada di models.py)
class BimbinganRequest(BaseModel):
    user_id: str
    jenis_bimbingan: str
    status: str = "Menunggu"
    tanggal_daftar: date

class TerimaBimbinganRequest(BaseModel):
    id_guru: str

class UpdateStatusRequest(BaseModel):
    status: str 
    id_guru: Optional[str] = None  

class LatihanSoalCreate(BaseModel):
    jilid_id: int
    halaman_target: int
    kategori: Optional[str] = None
    pertanyaan: str
    pilihan_jawaban: List[str]
    kunci_jawaban: str

class LatihanSoalResponse(LatihanSoalCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ProgresLatihanCreate(BaseModel):
    user_id: UUID
    jilid_id: int
    halaman_latihan: int
    skor: int