"""Mesin penilaian SLF: membaca tabel kuesioner (xlsx) + jawaban responden, lalu menghitung skor 0,00-1,00.

Mesin ini tidak tahu apa pun soal wilayah tertentu. Semua aturan (pertanyaan, pilihan, skor, arah) ada di tabel kuesioner.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

MODAL = ["Manusia", "Alam", "Sosial", "Fisik", "Finansial"]  # urutan sumbu pentagon
TIPE_SKOR = ["angka", "likert", "pilihan", "centang_hitung", "centang_tingkat"]  # tipe yang diskor
TIPE_OPSI = ["pilihan", "centang_hitung", "centang_tingkat"]  # tipe yang butuh daftar pilihan
TIPE_VALID = TIPE_SKOR + ["teks", "penentu_modul", "belum_ditentukan"]
KOLOM_KUES = ["Kode", "Paket", "Modal", "Pertanyaan_Form", "Tipe", "Arah"]
KOLOM_PILIHAN = ["Kode", "Urutan", "Label", "Skor", "Dihitung", "Kata_Kunci"]
KOLOM_MULTIBARIS = ["Pilihan", "Kata_Kunci"]  # kolom sel berisi beberapa baris


class SLFError(Exception):
    """Kesalahan yang pesannya layak ditampilkan langsung ke pengguna."""


def norm(teks) -> str:
    """Normalisasi teks untuk pencocokan: huruf kecil, tanpa spasi/titik/koma, tanda hubung seragam."""
    t = str(teks).lower().replace("–", "-").replace("—", "-")
    return re.sub(r"[\s.,]", "", t)


def kosong(seri: pd.Series) -> pd.Series:
    """True untuk sel kosong (NaN atau hanya spasi)."""
    return seri.isna() | seri.astype(str).str.strip().eq("")


def ke_angka(seri: pd.Series) -> pd.Series:
    """Ubah teks seperti '2,5' atau 'Rp 3' menjadi angka; gagal -> NaN."""
    teks = seri.astype(str).str.replace(r"[^\d,.\-]", "", regex=True).str.replace(",", ".", regex=False)
    x = pd.to_numeric(teks, errors="coerce")
    x[kosong(seri)] = np.nan
    return x


# ----------------------------------------------------------------------------- tabel kuesioner
def muat_tabel(sumber):
    """Baca tabel kuesioner. Kembalikan (kuesioner, pilihan, wilayah_dict)."""
    try:
        xl = pd.ExcelFile(sumber)
    except Exception as e:  # file rusak / bukan xlsx
        raise SLFError(f"Tabel kuesioner tidak bisa dibaca: {e}")
    if "Kuesioner" not in xl.sheet_names:
        raise SLFError("Sheet 'Kuesioner' tidak ada di tabel kuesioner.")
    kues = xl.parse("Kuesioner", dtype=str).fillna("")
    for kol in kues.columns:  # kolom multi-baris tidak di-strip agar barisnya tetap sejajar
        if kol not in KOLOM_MULTIBARIS:
            kues[kol] = kues[kol].str.strip()
    hilang = [k for k in KOLOM_KUES if k not in kues.columns]
    if hilang:
        raise SLFError(f"Sheet Kuesioner kekurangan kolom: {hilang}")
    kues = kues[kues["Kode"] != ""].reset_index(drop=True)

    wilayah = {}
    for nama in ("Pengaturan", "Wilayah"):  # nama sheet baru atau lama
        if nama in xl.sheet_names:
            w = xl.parse(nama).iloc[:, :2].dropna()
            wilayah = dict(zip(w.iloc[:, 0].astype(str).str.strip(), w.iloc[:, 1]))
            break

    if "Pilihan" not in xl.sheet_names:  # format baru: pilihan ada di sel kolom Pilihan
        if "Pilihan" not in kues.columns:
            raise SLFError("Kolom 'Pilihan' tidak ada di sheet Kuesioner (format satu sheet).")
        return kues, _urai_pilihan(kues), wilayah

    pil = xl.parse("Pilihan")  # format lama: sheet Pilihan terpisah
    if pil.shape[1] < 6:
        raise SLFError("Sheet Pilihan harus punya 6 kolom: Kode, Urutan, Label, Skor, Dihitung, Kata_Kunci.")
    pil = pil.iloc[:, :6].copy()
    pil.columns = KOLOM_PILIHAN
    pil["Kode"] = pil["Kode"].astype(str).str.strip()
    pil = pil[~pil["Kode"].isin(["", "nan"])].copy()
    pil["Urutan"] = pd.to_numeric(pil["Urutan"], errors="coerce")
    pil["Skor"] = pd.to_numeric(pil["Skor"], errors="coerce")
    pil["Dihitung"] = pil["Dihitung"].fillna("").astype(str).str.strip()
    pil["Kata_Kunci"] = pil["Kata_Kunci"].fillna("").astype(str).str.strip().str.lower()
    pil["Label"] = pil["Label"].fillna("").astype(str)
    return kues, pil.reset_index(drop=True), wilayah


def _urai_pilihan(kues: pd.DataFrame) -> pd.DataFrame:
    """Ubah kolom Pilihan / Kata_Kunci / Tidak_Dihitung (format satu sheet) menjadi tabel pilihan.

    Pilihan: satu opsi per baris, urut dari skor TERENDAH ke TERTINGGI.
    Kata_Kunci (opsional): satu baris per opsi, sejajar dengan Pilihan; baris kosong = pakai teks pilihan itu sendiri.
    Tidak_Dihitung (opsional, centang_hitung): nomor urut opsi yang tidak dihitung, mis. '6' atau '1,3'.
    """
    baris = []
    for q in kues.to_dict("records"):
        if q["Tipe"] not in TIPE_OPSI:
            continue
        label = [t.strip() for t in str(q.get("Pilihan", "")).splitlines() if t.strip()]
        kata = [t.strip().lower() for t in str(q.get("Kata_Kunci", "")).splitlines()]
        abaikan = {int(x) for x in re.findall(r"\d+", str(q.get("Tidak_Dihitung", "")))}
        n = len(label)
        for i, teks in enumerate(label):
            kw = kata[i] if i < len(kata) and kata[i] else norm(teks)
            skor = np.nan if q["Tipe"] == "centang_hitung" else (i / (n - 1) if n > 1 else np.nan)
            baris.append(dict(Kode=q["Kode"], Urutan=i + 1, Label=teks, Skor=skor,
                              Dihitung="Tidak" if (i + 1) in abaikan else "Ya", Kata_Kunci=kw))
    return pd.DataFrame(baris, columns=KOLOM_PILIHAN)


def validasi_tabel(kues: pd.DataFrame, pil: pd.DataFrame) -> list[str]:
    """Periksa konsistensi tabel. Kembalikan daftar pesan masalah (kosong = aman)."""
    masalah = []
    ganda = kues["Kode"][kues["Kode"].duplicated()].unique()
    if len(ganda):
        masalah.append(f"Kode pertanyaan ganda: {list(ganda)}")
    for q in kues.to_dict("records"):
        k, tipe = q["Kode"], q["Tipe"]
        if tipe not in TIPE_VALID:
            masalah.append(f"{k}: tipe '{tipe}' tidak dikenal (pilih: {', '.join(TIPE_VALID)}).")
            continue
        if tipe in TIPE_SKOR and q["Modal"] not in MODAL:
            masalah.append(f"{k}: kolom Modal harus salah satu dari {MODAL}.")
        if tipe in TIPE_SKOR and not q["Paket"]:
            masalah.append(f"{k}: kolom Paket kosong.")
        if tipe in TIPE_OPSI:
            opsi = pil[pil["Kode"] == k]
            if opsi.empty:
                masalah.append(f"{k}: belum ada pilihan jawaban (isi kolom Pilihan, satu opsi per baris).")
                continue
            if tipe in ("pilihan", "centang_tingkat") and len(opsi) < 2:
                masalah.append(f"{k}: butuh minimal 2 pilihan untuk menghitung skor.")
            if (opsi["Kata_Kunci"] == "").any():
                masalah.append(f"{k}: ada pilihan tanpa Kata_Kunci.")
            if tipe in ("pilihan", "centang_tingkat") and opsi["Skor"].isna().any():
                masalah.append(f"{k}: ada pilihan tanpa Skor.")
            if tipe == "centang_hitung" and not (opsi["Dihitung"].str.lower() == "ya").any():
                masalah.append(f"{k}: tidak ada pilihan dengan Dihitung = Ya.")
    return masalah


def _opsi_list(pil_kode: pd.DataFrame) -> list[dict]:
    """Ubah baris pilihan satu pertanyaan menjadi daftar dict."""
    return [
        dict(label=r.Label, skor=r.Skor, dihitung=r.Dihitung.lower() == "ya",
             kws=[k for k in r.Kata_Kunci.split("|") if k])
        for r in pil_kode.sort_values("Urutan").itertuples()
    ]


# ----------------------------------------------------------------------------- skor satu pertanyaan
def skor_pertanyaan(seri: pd.Series, q: dict, opsi: list[dict]):
    """Hitung skor 0-1 satu pertanyaan. Kembalikan (Series skor, daftar masalah)."""
    tipe, invers = q["Tipe"], q["Arah"].lower() == "invers"
    kos = kosong(seri)
    skor = pd.Series(np.nan, index=seri.index, dtype=float)
    tak_cocok: dict[str, int] = {}
    jenis = "Jawaban tidak cocok dengan tabel"

    if tipe == "angka":
        jenis = "Bukan angka"
        x = ke_angka(seri)
        for j, c in seri[~kos & x.isna()].astype(str).value_counts().items():
            tak_cocok[j] = int(c)
        valid = x.dropna()
        if len(valid):
            lo, hi = valid.min(), valid.max()
            skor = (x - lo) / (hi - lo) if hi > lo else x * 0.0  # semua nilai sama -> 0
        if invers:
            skor = 1 - skor

    elif tipe == "likert":
        jenis = "Nilai di luar skala 1-5"
        d = pd.to_numeric(seri.astype(str).str.extract(r"(\d+)")[0], errors="coerce")
        d[kos] = np.nan
        salah = (~kos) & (d.isna() | ~d.between(1, 5))
        for j, c in seri[salah].astype(str).value_counts().items():
            tak_cocok[j] = int(c)
        d[~d.between(1, 5)] = np.nan
        skor = (d - 1) / 4
        if invers:
            skor = 1 - skor

    elif tipe in TIPE_OPSI:
        hasil: dict[str, float] = {}
        for j in seri[~kos].astype(str).unique():
            n = norm(j)
            if tipe == "pilihan":  # kata kunci terpanjang menang
                terbaik, panjang = None, 0
                for o in opsi:
                    for k in o["kws"]:
                        if k in n and len(k) > panjang:
                            terbaik, panjang = o, len(k)
                hasil[j] = terbaik["skor"] if terbaik else np.nan
            else:
                kena = [o for o in opsi if any(k in n for k in o["kws"])]
                if not kena:
                    hasil[j] = np.nan
                elif tipe == "centang_hitung":
                    pembagi = max(sum(o["dihitung"] for o in opsi), 1)
                    hasil[j] = min(1.0, sum(o["dihitung"] for o in kena) / pembagi)
                else:  # centang_tingkat
                    hasil[j] = max(o["skor"] for o in kena)
        skor[~kos] = seri[~kos].astype(str).map(hasil)
        for j, c in seri[~kos][skor[~kos].isna()].astype(str).value_counts().items():
            tak_cocok[j] = int(c)

    masalah = []
    if tak_cocok:
        detail = "; ".join(f"'{j}' ({c}x)" for j, c in list(tak_cocok.items())[:8])
        masalah.append(dict(Kode=q["Kode"], Pertanyaan=q["Pertanyaan_Form"], Jenis=jenis, Detail=detail))
    return skor, masalah


# ----------------------------------------------------------------------------- seluruh data
@dataclass
class Hasil:
    n: int
    ids: pd.Series
    skor_indikator: pd.DataFrame  # per RT x kode pertanyaan
    skor_modal: pd.DataFrame  # ID, 5 modal, Skor_Total (paket wajib)
    rata_desa: pd.Series  # rata-rata 5 modal seluruh responden
    kosong_wajib: pd.Series  # jumlah indikator wajib yang kosong per RT
    modul_rt: pd.DataFrame  # skor tiap modul tematik per RT (NaN = tidak mengisi)
    modul_ringkas: pd.DataFrame
    modul_pentagon: dict  # nama modul -> Series 5 modal (rata-rata pelaku)
    masalah: pd.DataFrame
    peta: pd.DataFrame
    luas_ha: pd.Series | None


def hitung_semua(df: pd.DataFrame, kues: pd.DataFrame, pil: pd.DataFrame, wilayah: dict | None = None) -> Hasil:
    """Hitung skor semua responden dari tabel jawaban `df`."""
    wilayah = wilayah or {}
    df = df.loc[:, ~df.columns.duplicated()].copy()
    skor_q = kues[kues["Tipe"].isin(TIPE_SKOR)]
    kolom_data = {norm(c): c for c in df.columns}

    peta_rows, kolom_pakai = [], {}
    for q in skor_q.to_dict("records"):
        kol = kolom_data.get(norm(q["Pertanyaan_Form"]))
        peta_rows.append(dict(Kode=q["Kode"], Paket=q["Paket"], Modal=q["Modal"], Pertanyaan_Form=q["Pertanyaan_Form"],
                              Kolom_di_Data=kol if kol else "(tidak ditemukan)"))
        if kol:
            kolom_pakai[q["Kode"]] = kol
    peta = pd.DataFrame(peta_rows)

    hilang = peta[(peta["Paket"] == "Wajib") & (peta["Kolom_di_Data"] == "(tidak ditemukan)")]
    if len(hilang):
        dikenal = {norm(t) for t in kues["Pertanyaan_Form"]}
        tak_dikenal = [c for c in df.columns if norm(c) not in dikenal]
        raise SLFError(
            f"{len(hilang)} pertanyaan paket wajib tidak ditemukan di data: {list(hilang['Kode'])}. "
            f"Judul kolom di data yang tidak dikenali tabel: {tak_dikenal}. "
            "Judul kolom di data harus sama dengan kolom 'Pertanyaan_Form' di tabel kuesioner.")

    terisi = pd.concat([~kosong(df[c]) for c in kolom_pakai.values()], axis=1).any(axis=1)
    df = df[terisi].reset_index(drop=True)
    if df.empty:
        raise SLFError("Data tidak berisi jawaban untuk pertanyaan yang diskor.")
    ids = pd.Series([f"RT-{i:03d}" for i in range(1, len(df) + 1)], name="ID_Responden")

    ski = pd.DataFrame(index=df.index)
    masalah_rows = []
    for q in skor_q.to_dict("records"):
        kode = q["Kode"]
        if kode not in kolom_pakai:
            continue
        s, m = skor_pertanyaan(df[kolom_pakai[kode]], q, _opsi_list(pil[pil["Kode"] == kode]))
        ski[kode] = s
        masalah_rows += m
    masalah = pd.DataFrame(masalah_rows, columns=["Kode", "Pertanyaan", "Jenis", "Detail"])

    wajib = skor_q[skor_q["Paket"] == "Wajib"]
    modal = pd.DataFrame({"ID_Responden": ids})
    for m in MODAL:
        kodes = [k for k in wajib[wajib["Modal"] == m]["Kode"] if k in ski.columns]
        modal[m] = ski[kodes].mean(axis=1, skipna=True) if kodes else np.nan
    modal["Skor_Total"] = modal[MODAL].mean(axis=1)
    kosong_wajib = ski[[k for k in wajib["Kode"] if k in ski.columns]].isna().sum(axis=1)
    rata_desa = modal[MODAL].mean()

    modul_rt = pd.DataFrame({"ID_Responden": ids})
    ringkas, pentagon = [], {}
    for p in dict.fromkeys(skor_q["Paket"]):
        if p == "Wajib":
            continue
        sub = skor_q[skor_q["Paket"] == p]
        kodes = [k for k in sub["Kode"] if k in ski.columns]
        if not kodes:
            continue
        modul_rt[p] = ski[kodes].mean(axis=1, skipna=True)  # NaN bila RT tidak mengisi modul
        diisi = ski[kodes].notna().sum(axis=1)
        pent = {}
        for m in MODAL:
            km = [k for k in sub[sub["Modal"] == m]["Kode"] if k in ski.columns]
            pent[m] = ski[km].mean(axis=1).mean() if km else np.nan
        pentagon[p] = pd.Series(pent)
        n_pelaku = int(modul_rt[p].notna().sum())
        ringkas.append(dict(Modul=p, N_Pelaku=n_pelaku, Persen_Pelaku=round(100 * n_pelaku / len(df), 1),
                            N_Jawaban_Sebagian=int(((diisi > 0) & (diisi < len(kodes))).sum()),
                            Rata_Rata_Skor=modul_rt[p].mean(), **pentagon[p].to_dict()))
    modul_ringkas = pd.DataFrame(ringkas)

    luas_ha = None
    kode_luas, faktor = str(wilayah.get("kode_luas", "W-ALA-01")), wilayah.get("hektar_per_satuan_lokal")
    if kode_luas in kolom_pakai and faktor:
        luas_ha = ke_angka(df[kolom_pakai[kode_luas]]) * float(faktor)

    return Hasil(n=len(df), ids=ids, skor_indikator=ski, skor_modal=modal, rata_desa=rata_desa, kosong_wajib=kosong_wajib,
                 modul_rt=modul_rt, modul_ringkas=modul_ringkas, modul_pentagon=pentagon, masalah=masalah, peta=peta,
                 luas_ha=luas_ha)


# ----------------------------------------------------------------------------- data contoh
def buat_dummy(kues: pd.DataFrame, pil: pd.DataFrame, n: int = 35, seed: int = 42) -> pd.DataFrame:
    """Bangun jawaban simulasi mengikuti tabel kuesioner (judul kolom = Pertanyaan_Form)."""
    rng = np.random.default_rng(seed)
    pakets = [p for p in dict.fromkeys(kues["Paket"]) if p != "Wajib"]
    peluang = [0.6, 0.5, 0.55, 0.3, 0.3, 0.3]
    ikut = {p: rng.random(n) < peluang[i % len(peluang)] for i, p in enumerate(pakets)}
    if pakets:  # setiap RT minimal mengisi satu modul
        tanpa = ~np.any([ikut[p] for p in pakets], axis=0)
        ikut[pakets[0]] = ikut[pakets[0]] | tanpa

    data = {"Timestamp": pd.date_range("2026-11-01 08:00", periods=n, freq="37min").strftime("%Y/%m/%d %H:%M:%S")}
    for q in kues.to_dict("records"):
        tipe, kode = q["Tipe"], q["Kode"]
        opsi = _opsi_list(pil[pil["Kode"] == kode])
        if tipe == "teks":
            nilai = [f"Contoh {kode}-{i + 1:03d}" for i in range(n)]
        elif tipe == "penentu_modul":
            nilai = [", ".join(p for p in pakets if ikut[p][i]) for i in range(n)]
        elif tipe == "likert":
            nilai = np.clip(np.round(rng.normal(3.4, 1.0, n)), 1, 5).astype(int)
        elif tipe == "angka":
            nilai = (np.round(rng.gamma(2.5, 2.0, n)) + 1).astype(int)
        elif tipe in ("pilihan", "centang_tingkat") and opsi:
            w = np.exp(-((np.arange(len(opsi)) - (len(opsi) - 1) * 0.55) ** 2) / 2.0)
            idx = rng.choice(len(opsi), n, p=w / w.sum())
            if tipe == "pilihan":
                nilai = [opsi[i]["label"] for i in idx]
            else:  # kadang memilih dua tingkat sekaligus
                nilai = [", ".join(dict.fromkeys([opsi[i]["label"], opsi[rng.integers(len(opsi))]["label"]])) if rng.random() < 0.3
                         else opsi[i]["label"] for i in idx]
        elif tipe == "centang_hitung" and opsi:
            nilai = []
            for _ in range(n):
                k = int(rng.integers(1, len(opsi) + 1))
                pilih = sorted(rng.choice(len(opsi), k, replace=False))
                nilai.append(", ".join(opsi[i]["label"] for i in pilih))
        else:
            nilai = [np.nan] * n
        arr = np.array(nilai, dtype=object)
        if q["Paket"] != "Wajib" and q["Paket"] in ikut:
            arr[~ikut[q["Paket"]]] = np.nan
        data[q["Pertanyaan_Form"]] = arr
    return pd.DataFrame(data)


# ----------------------------------------------------------------------------- keluaran
def buat_png_pentagon(nilai: pd.Series, n: int, judul: str, dpi: int = 300, subjudul: str | None = None) -> bytes:
    """Gambar pentagon aset (skala 0-1) bertema hijau dan kembalikan bytes PNG."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    hijau_tua, hijau, latar, grid = "#1B5E20", "#2E7D32", "#F1F8E9", "#A5D6A7"
    label = list(nilai.index)
    v = [0.0 if pd.isna(x) else float(x) for x in nilai.values]
    sudut = np.linspace(0, 2 * np.pi, len(label), endpoint=False).tolist()
    vt, st_ = v + v[:1], sudut + sudut[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True}, facecolor=latar)
    ax.set_facecolor(latar)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.20", "0.40", "0.60", "0.80", "1.00"], color="#4E6B50", fontsize=9)
    ax.yaxis.grid(False)
    ax.xaxis.grid(color=grid, linewidth=0.8)
    ax.spines["polar"].set_visible(False)
    for lv in [0.2, 0.4, 0.6, 0.8, 1.0]:
        ax.plot(st_, [lv] * len(st_), color=grid, linewidth=0.8)
    ax.plot(st_, vt, color=hijau_tua, linewidth=2.5, marker="o", markersize=7)
    ax.fill(st_, vt, color=hijau, alpha=0.35)
    ax.set_xticks(sudut)
    ax.set_xticklabels(label, fontsize=13, fontweight="bold", color=hijau_tua)
    for s, x in zip(sudut, v):
        ax.text(s, min(x + 0.07, 1.0), f"{x:.2f}", ha="center", va="center", fontsize=11, color=hijau_tua, fontweight="bold")
    ax.set_title(judul, fontsize=14, fontweight="bold", color=hijau_tua, pad=30)
    fig.text(0.5, 0.06, subjudul or f"n = {n} responden  |  Skala 0,00 – 1,00", ha="center", fontsize=11, color="#4E6B50")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


def buat_excel(h: Hasil, kues: pd.DataFrame, pil: pd.DataFrame, nama_wilayah: str = "") -> bytes:
    """Kumpulkan semua hasil ke satu file Excel (tanpa kolom identitas responden)."""
    r = lambda d: d.round(4)  # noqa: E731
    desa = h.rata_desa.rename("Rata_Rata_Desa").to_frame()
    desa.loc["Skor_Total"] = h.rata_desa.mean()
    desa.loc["N_Responden"] = h.n
    per_rt = h.skor_modal.copy()
    per_rt["Jawaban_Wajib_Kosong"] = h.kosong_wajib
    if h.luas_ha is not None:
        per_rt["Luas_Lahan_Ha"] = h.luas_ha
    per_rt = per_rt.merge(h.modul_rt, on="ID_Responden")
    indikator = pd.concat([h.ids, h.skor_indikator], axis=1)
    pent_modul = pd.DataFrame(h.modul_pentagon).T.rename_axis("Modul").reset_index() if h.modul_pentagon else pd.DataFrame()
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame({"Keterangan": [f"Wilayah: {nama_wilayah}", f"Jumlah responden: {h.n}",
                                     "Skor 0,00-1,00. Skor numerik dinormalisasi Min-Max antar responden (relatif terhadap sampel).",
                                     "Modul tematik: RT yang tidak mengisi = kosong (bukan 0)."]}).to_excel(w, sheet_name="Catatan", index=False)
        r(desa).to_excel(w, sheet_name="Rata_Rata_Desa")
        r(per_rt).to_excel(w, sheet_name="Skor_Per_RT", index=False)
        r(indikator).to_excel(w, sheet_name="Skor_Per_Indikator", index=False)
        r(h.modul_ringkas).to_excel(w, sheet_name="Modul_Tematik", index=False)
        if not pent_modul.empty:
            r(pent_modul).to_excel(w, sheet_name="Pentagon_Modul", index=False)
        h.peta.to_excel(w, sheet_name="Pemetaan_Kolom", index=False)
        h.masalah.to_excel(w, sheet_name="Masalah_Data", index=False)
        kues.to_excel(w, sheet_name="Kuesioner_Dipakai", index=False)
        pil.to_excel(w, sheet_name="Pilihan_Dipakai", index=False)
    return buf.getvalue()
