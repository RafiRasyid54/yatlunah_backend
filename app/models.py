from sqlalchemy import Column, Integer, String, TIMESTAMP, text, ForeignKey, Date, Boolean, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID 
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from .database import Base

# --- 1. TABEL USERS ---
class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    nama_lengkap = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(Integer, default=1) # 1: Peserta, 2: Guru, 3: Admin
    role = Column(String, default="peserta") # 'peserta', 'guru', 'admin', 'mitra'
    id_mitra = Column(UUID(as_uuid=True), ForeignKey("mitra.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

# --- 2. TABEL MITRA ---
class Mitra(Base):
    __tablename__ = "mitra"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    nama_lembaga = Column(String(255), nullable=False)
    kota = Column(String(100))
    paket = Column(String(50)) # Contoh: 'Premium', 'Lengkap'
    status_sertifikasi = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

# --- 3. TABEL LOG BELAJAR (PROGRESS) ---
class LogBelajar(Base):
    __tablename__ = "log_belajar"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"))
    jilid = Column(Integer)
    halaman = Column(Integer)
    tanggal_belajar = Column(Date, server_default=func.current_date())

# --- 4. TABEL JILID INFO ---
class JilidInfo(Base):
    __tablename__ = "jilid_info"

    nomor_jilid = Column(Integer, primary_key=True, index=True)
    judul_jilid = Column(String(100), nullable=False)
    pdf_url = Column(Text, nullable=False)
    file_size = Column(String(20))
    total_halaman = Column(Integer)

# --- 5. TABEL AUDIO MAPPING (MATERI) ---
class AudioMapping(Base):
    __tablename__ = "audio_mapping"

    id = Column(Integer, primary_key=True, index=True)
    jilid_id = Column(Integer, ForeignKey("jilid_info.nomor_jilid", ondelete="CASCADE"))
    page_start = Column(Integer, nullable=False)
    page_end = Column(Integer, nullable=False)
    audio_url = Column(Text, nullable=False)
    judul_materi = Column(String(100))

# --- 6. TABEL SETORAN (FITUR PENILAIAN) ---
class Setoran(Base):
    __tablename__ = "setoran"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"))
    nama_lengkap = Column(String(255)) # Denormalisasi nama santri agar list cepat
    jilid = Column(Integer, nullable=False)
    halaman = Column(Integer, nullable=False)
    audio_url = Column(Text, nullable=False)
    status = Column(String(50), default="pending") # 'pending' atau 'dinilai'
    nilai = Column(Integer, nullable=True)
    catatan = Column(Text, nullable=True)
    
    # ID Guru yang melakukan penilaian (UUID)
    id_guru_penilai = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# --- 7. TABEL QUOTES HARIAN ---
class QuotesHarian(Base):
    __tablename__ = "quotes_harian"
    id = Column(Integer, primary_key=True, index=True)
    teks_quote = Column(String)
    sumber = Column(String)
    hari = Column(String, nullable=True)

# --- 8. TABEL LATIHAN SOAL (Dikeluarkan dari QuotesHarian) ---
class LatihanSoal(Base):
    __tablename__ = "latihan_soal"
    id = Column(Integer, primary_key=True, index=True) # Pastikan id ada di sini
    jilid_id = Column(Integer, nullable=False)
    halaman_target = Column(Integer, nullable=False)
    kategori = Column(String, nullable=True)
    pertanyaan = Column(String, nullable=False)
    pilihan_jawaban = Column(JSONB, nullable=False) 
    kunci_jawaban = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

# --- 9. TABEL PROGRES LATIHAN ---
class ProgresLatihan(Base):
    __tablename__ = "progres_latihan"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    jilid_id = Column(Integer, nullable=False)
    halaman_latihan = Column(Integer, nullable=False)
    skor = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())