"""SLF Digital Analyzer v0.2 - penilaian aset penghidupan (5 modal) berbasis tabel kuesioner."""
import io
from pathlib import Path

import pandas as pd
import streamlit as st

from slf_engine import SLFError, buat_dummy, buat_excel, buat_png_pentagon, hitung_semua, muat_tabel, validasi_tabel

HERE = Path(__file__).resolve().parent
st.set_page_config(page_title="SLF Digital Analyzer", page_icon="🌿", layout="wide")


def cari_tabel_default():
    """Cari tabel kuesioner bawaan di folder aplikasi atau folder induknya."""
    for folder in [HERE / "kuesioner", HERE.parent / "kuesioner", HERE, HERE.parent]:
        if folder.exists():
            ketemu = sorted(folder.glob("Kuesioner_SLF*.xlsx"))
            if ketemu:
                return ketemu[-1]
    return None


@st.cache_data(show_spinner=False)
def baca_tabel(isi: bytes):
    """Baca tabel kuesioner dari bytes (di-cache agar tidak dibaca ulang tiap interaksi)."""
    return muat_tabel(io.BytesIO(isi))


def baca_data(file) -> pd.DataFrame:
    """Baca jawaban responden dari Excel atau CSV."""
    if file.name.lower().endswith(".csv"):
        try:
            return pd.read_csv(file)
        except UnicodeDecodeError:
            file.seek(0)
            return pd.read_csv(file, encoding="latin-1")
    return pd.read_excel(file)


def ke_xlsx(df: pd.DataFrame) -> bytes:
    """Ubah DataFrame menjadi bytes file Excel."""
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


# ------------------------------------------------------------------ judul & sidebar
st.title("🌿 SLF Digital Analyzer")
st.caption("v0.2 | Penilaian aset penghidupan lima modal (Sustainable Livelihoods Framework) berbasis tabel kuesioner")

with st.sidebar:
    st.header("1. Tabel kuesioner")
    tabel_up = st.file_uploader("Ganti tabel kuesioner (opsional)", type=["xlsx"], key="tabel")
    st.header("2. Data responden")
    data_up = st.file_uploader("Unggah Excel/CSV hasil Google Form", type=["xlsx", "xls", "csv"], key="data")
    pakai_contoh = st.checkbox("Pakai data simulasi", value=False)
    n_contoh = st.number_input("Jumlah responden simulasi", min_value=5, max_value=500, value=35, step=5)
    st.header("3. Pengaturan")
    abaikan = st.checkbox("Lanjutkan walau ada jawaban tak cocok (dianggap kosong)", value=False)
    st.warning("Hindari mengunggah data pribadi yang tidak perlu. Nama responden tidak dipakai dalam perhitungan "
               "dan tidak ikut ke Excel hasil.")

# ------------------------------------------------------------------ tabel kuesioner
if tabel_up is not None:
    isi_tabel = tabel_up.getvalue()
else:
    jalur = cari_tabel_default()
    if jalur is None:
        st.error("Tabel kuesioner bawaan tidak ditemukan. Unggah file Kuesioner_SLF_*.xlsx di sidebar.")
        st.stop()
    isi_tabel = jalur.read_bytes()

try:
    kues, pil, wil = baca_tabel(isi_tabel)
except SLFError as e:
    st.error(str(e))
    st.stop()
masalah_tabel = validasi_tabel(kues, pil)
if masalah_tabel:
    st.error("Tabel kuesioner bermasalah:\n\n" + "\n".join(f"- {m}" for m in masalah_tabel))
    st.stop()
nama_wilayah = str(wil.get("nama_wilayah", ""))
if nama_wilayah:
    st.subheader(nama_wilayah)

# ------------------------------------------------------------------ data responden
if data_up is not None:
    try:
        df = baca_data(data_up)
    except Exception as e:
        st.error(f"File gagal dibaca: {e}")
        st.stop()
elif pakai_contoh:
    df = buat_dummy(kues, pil, int(n_contoh))
    st.info("Menampilkan DATA SIMULASI, bukan data lapangan.")
else:
    st.markdown("### Cara pakai")
    st.markdown(
        "1. Di Google Form: **Respons → Tautkan ke Spreadsheet**, lalu **File → Unduh → Microsoft Excel**.\n"
        "2. Unggah file itu di sidebar.\n"
        "3. Pentagon, skor per rumah tangga, dan modul tematik muncul otomatis. Unduh hasilnya di tab **Unduh**.\n\n"
        "Judul kolom di data harus sama dengan kolom `Pertanyaan_Form` di tabel kuesioner. "
        "Mau mencoba dulu? Centang **Pakai data simulasi** di sidebar."
    )
    k1, k2 = st.columns(2)
    k1.download_button("Unduh tabel kuesioner (Excel)", data=isi_tabel, file_name="Kuesioner_SLF.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_tabel")
    k2.download_button("Unduh contoh data simulasi (Excel)", data=ke_xlsx(buat_dummy(kues, pil, 35)),
                       file_name="data_simulasi_slf.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_contoh")
    st.stop()

# ------------------------------------------------------------------ hitung
try:
    h = hitung_semua(df, kues, pil, wil)
except SLFError as e:
    st.error(str(e))
    st.stop()

if len(h.masalah) and not abaikan:
    st.error("Ada jawaban yang tidak cocok dengan tabel kuesioner. Perbaiki data atau Kata_Kunci di tabel, "
             "atau centang 'Lanjutkan walau ada jawaban tak cocok' di sidebar.")
    st.dataframe(h.masalah)
    st.stop()
if len(h.masalah):
    st.warning(f"{len(h.masalah)} pertanyaan punya jawaban tak cocok yang dianggap kosong (lihat tab Pemeriksaan Data).")

JUDUL = f"Pentagon Aset Penghidupan Rumah Tangga\n{nama_wilayah}".strip()
tab_desa, tab_modul, tab_rt, tab_ind, tab_cek, tab_unduh = st.tabs(
    ["Pentagon Desa", "Modul Tematik", "Per Rumah Tangga", "Indikator", "Pemeriksaan Data", "Unduh"])

# ------------------------------------------------------------------ tab pentagon desa
with tab_desa:
    rata = h.rata_desa
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Responden", f"{h.n:,}")
    c2.metric("Skor total desa", f"{rata.mean():.2f}")
    if rata.notna().any():
        c3.metric("Modal terendah", f"{rata.idxmin()} ({rata.min():.2f})")
        c4.metric("Modal tertinggi", f"{rata.idxmax()} ({rata.max():.2f})")
    kiri, kanan = st.columns([3, 2])
    with kiri:
        st.image(buat_png_pentagon(rata, h.n, JUDUL, dpi=110))
    with kanan:
        st.dataframe(rata.rename("Rata-rata").round(2).to_frame())
        if h.luas_ha is not None and h.luas_ha.notna().any():
            st.metric("Rata-rata luas lahan garapan (ha)", f"{h.luas_ha.mean():.2f}")
        st.caption("Skor 0,00-1,00. Indikator numerik dinormalisasi Min-Max antar responden, jadi skor bersifat relatif "
                   "terhadap sampel penelitian, bukan standar mutlak. Banjir dan risiko kerugian memakai arah invers.")

# ------------------------------------------------------------------ tab modul tematik
with tab_modul:
    if h.modul_ringkas.empty:
        st.info("Tidak ada modul tematik yang ditemukan di data.")
    else:
        st.caption("Rata-rata hanya dari responden yang menjalankan usaha tersebut. Yang tidak mengisi modul dikosongkan, bukan 0.")
        st.dataframe(h.modul_ringkas.round(3))
        daftar = list(h.modul_pentagon.items())
        for i in range(0, len(daftar), 2):
            kolom = st.columns(2)
            for kol, (nama, seri) in zip(kolom, daftar[i:i + 2]):
                n_pelaku = int(h.modul_ringkas.loc[h.modul_ringkas["Modul"] == nama, "N_Pelaku"].iloc[0])
                with kol:
                    st.markdown(f"**{nama}** (n = {n_pelaku})")
                    if n_pelaku == 0:
                        st.info("Belum ada responden yang mengisi modul ini.")
                    else:
                        st.image(buat_png_pentagon(seri, n_pelaku, nama, dpi=100, subjudul=f"n = {n_pelaku} pelaku"))
                        if n_pelaku < 5:
                            st.caption("n kecil: hasil belum stabil.")

# ------------------------------------------------------------------ tab per rumah tangga
with tab_rt:
    per_rt = h.skor_modal.copy()
    per_rt["Jawaban_Wajib_Kosong"] = h.kosong_wajib
    per_rt = per_rt.merge(h.modul_rt, on="ID_Responden")
    st.dataframe(per_rt.round(3))

# ------------------------------------------------------------------ tab indikator
with tab_ind:
    ind = h.peta[h.peta["Kolom_di_Data"] != "(tidak ditemukan)"][["Kode", "Paket", "Modal", "Pertanyaan_Form"]].copy()
    ind["N_Valid"] = [int(h.skor_indikator[k].notna().sum()) for k in ind["Kode"]]
    ind["Rata_Skor"] = [h.skor_indikator[k].mean() for k in ind["Kode"]]
    ind["SD_Skor"] = [h.skor_indikator[k].std() for k in ind["Kode"]]
    st.dataframe(ind.round(3))
    st.caption("Rata-rata skor per indikator (0-1). Indikator terendah = kandidat prioritas intervensi.")
    st.bar_chart(ind.set_index("Kode")["Rata_Skor"])

# ------------------------------------------------------------------ tab pemeriksaan
with tab_cek:
    st.markdown("**Pencocokan pertanyaan tabel dengan kolom data**")
    st.dataframe(h.peta)
    tidak = h.peta[h.peta["Kolom_di_Data"] == "(tidak ditemukan)"]
    if len(tidak):
        st.warning(f"{len(tidak)} pertanyaan tidak ditemukan di data (modul tanpa kolom dilewati).")
    st.markdown("**Jawaban yang tidak cocok**")
    if h.masalah.empty:
        st.success("Semua jawaban cocok dengan tabel.")
    else:
        st.dataframe(h.masalah)
    st.markdown("**Jawaban paket wajib yang kosong per responden**")
    st.write(f"Responden dengan minimal satu jawaban wajib kosong: {int((h.kosong_wajib > 0).sum())} dari {h.n}.")

# ------------------------------------------------------------------ tab unduh
with tab_unduh:
    st.download_button("Unduh hasil lengkap (Excel)", data=buat_excel(h, kues, pil, nama_wilayah),
                       file_name="Hasil_SLF.xlsx", key="dl_excel",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    pilihan = {"Pentagon Desa": (h.rata_desa, h.n, JUDUL)}
    for nama, seri in h.modul_pentagon.items():
        n_p = int(h.modul_ringkas.loc[h.modul_ringkas["Modul"] == nama, "N_Pelaku"].iloc[0])
        pilihan[nama] = (seri, n_p, nama)
    pilih = st.selectbox("Pentagon yang diunduh (PNG 300 DPI, siap cetak)", list(pilihan.keys()))
    seri, n_p, judul = pilihan[pilih]
    nama_file = "Pentagon_Aset_" + pilih.replace(" ", "_") + ".png"
    st.download_button("Unduh PNG", data=buat_png_pentagon(seri, n_p, judul, dpi=300), file_name=nama_file,
                       mime="image/png", key="dl_png")
