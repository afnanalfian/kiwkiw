"""
Script Otomasi Penandaan Komentar KBLI & Penyelesaian Anomali FASIH-SM (Multi-PC Paralel & Full Otomatis)
Sensus Ekonomi 2026 - BPS Kabupaten Pangkajene dan Kepulauan

Fitur Utama:
1. Mendukung Multi-PC Paralel (PC 1 s.d. PC 8) untuk mempercepat pengerjaan secara serentak.
   - PC 1: Master #300 s.d. #2.134  (1.835 assignment)
   - PC 2: Master #2.135 s.d. #3.969  (1.835 assignment)
   - PC 3: Master #3.970 s.d. #5.804  (1.835 assignment)
   - PC 4: Master #5.805 s.d. #7.638  (1.834 assignment)
   - PC 5: Master #7.639 s.d. #9.472  (1.834 assignment)
   - PC 6: Master #9.473 s.d. #11.306 (1.834 assignment)
   - PC 7: Master #11.307 s.d. #13.140 (1.834 assignment)
   - PC 8: Master #13.141 s.d. #14.974 (1.834 assignment)
2. Menavigasi ke setiap assignment secara otomatis tanpa perlu tekan Enter berulang kali.
3. Membuka menu 'SE2026 - L BLOK II' (Keterangan Usaha/Perusahaan) dan memilih sub-usaha terkait (sidebar / card).
4. Menemukan rincian '13. g. Kode KBLI' (atau 13. h.) dan membuka tombol kecil 'Catatan' (title='Catatan' / SVG bubble).
5. Jika kolom catatan SUDAH TERISI catatan apapun oleh pegawai, langsung SKIP assignment tersebut.
6. Mengisi '#DC_00' (Sesuai) atau '#DC_01' (Tidak Sesuai) jika kolom catatan masih kosong.
7. Berpindah ke menu 'CATATAN' di sidebar.
8. Memastikan switch 'Tampilkan Anomali Usaha dan Keluarga' (#cek_anomali_button) AKTIF (ON).
9. Memastikan switch 'Anomali diselesaikan oleh admin' (#anomali_admin) AKTIF (ON).
10. Mengisi kolom 'Penjelasan Penyelesaian Anomali oleh Admin' (#catatan_anomali_admin textarea):
    - "Sesuai" atau "Tidak Sesuai dan Telah diperbaiki" (jika sudah ada isian, tidak ditimpa).
11. Memperbarui 'Waktu Selesai' (#waktu_selesai) jika masih kosong.
12. Mengklik tombol 'Kirim' di header dan menyetujui modal konfirmasi secara otomatis.
13. Penanganan Sesi Habis (Session Timeout): Mendeteksi otomatis jika logout/sesi habis, membunyikan alarm suara,
    dan menunggu pengguna login kembali di Chrome tanpa melempar/melewati assignment yang sedang berjalan.
14. Pemilihan Titik Mulai Fleksibel: Menampilkan urutan pengerjaan lokal PC dan nomor master SE2026.
"""

import os
import sys
import re
import csv
import json
import time
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE_DIR, ".playwright_profile")
HASIL_DIR = os.path.join(BASE_DIR, "hasil-analisis")
DATA_PC_DIR = os.path.join(HASIL_DIR, "data_pc")

SURVEY_ID = "fd68e454-ba45-4b85-8205-f3bf777ded24"
FASIH_URL = "https://fasih-sm.bps.go.id/app"

def get_checkpoint_path(pc_num=None):
    if pc_num:
        return os.path.join(HASIL_DIR, f"checkpoint_pc_{pc_num}.json")
    return os.path.join(HASIL_DIR, "checkpoint_fasih.json")

def load_checkpoint(chk_path):
    if os.path.exists(chk_path):
        try:
            with open(chk_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"done_assignments": [], "skipped": [], "failed": []}

def save_checkpoint(chk_path, data):
    with open(chk_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def bunyikan_alarm():
    """Membunyikan alert suara di Windows console."""
    try:
        import winsound
        winsound.Beep(1000, 350)
        winsound.Beep(1500, 500)
    except Exception:
        print("\a\a", end="", flush=True)

def cek_apakah_sesi_habis(page):
    """Mendeteksi apakah sesi login FASIH telah habis atau browser dialihkan ke halaman login."""
    try:
        url = page.url.lower()
        if any(kw in url for kw in ["cas.bps.go.id", "/login", "/auth", "sso", "identity"]):
            return True
        
        login_selectors = [
            "text='Lanjutkan dengan SSO Eksternal'",
            "text='Masuk dengan Akun Pegawai'",
            "text='Selamat Datang Kembali'",
            "text='Sesi Anda telah berakhir'",
            "text='Session Expired'",
            "input[type='password']",
            "button:has-text('SSO Eksternal')",
            "button:has-text('Login')"
        ]
        for sel in login_selectors:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                return True

        title = page.title().lower()
        if "login" in title or "sso" in title or "401" in title or "unauthorized" in title:
            return True
    except Exception:
        pass
    return False

AUTH_CACHE_FILE = os.path.join(HASIL_DIR, ".sso_credentials.json")
CURRENT_AUTH = {"tipe": "pegawai"}

def load_cached_auth():
    if os.path.exists(AUTH_CACHE_FILE):
        try:
            with open(AUTH_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_cached_auth(email, password):
    try:
        with open(AUTH_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"email": email, "password": password}, f, indent=2)
    except Exception:
        pass

def pilih_metode_login():
    print("\n" + "="*70)
    print("                    PILIH METODE LOGIN FASIH-SM")
    print("="*70)
    print("  [1] SSO Eksternal (Otomatis: Input Email/Password, Auto Re-Login) [DEFAULT]")
    print("  [2] SSO Pegawai   (Manual: Login sendiri di browser setiap sesi habis)")
    print("="*70)
    
    pilihan = input("Pilih metode login (1/2) [Default: 1]: ").strip()
    if pilihan == "2":
        print("-> Mode Login: SSO Pegawai (Manual).")
        return {"tipe": "pegawai"}

    print("-> Mode Login: SSO Eksternal (Otomatis).")
    cached = load_cached_auth()
    if cached and cached.get("email"):
        c_email = cached["email"]
        pakai = input(f"Gunakan akun SSO Eksternal tersimpan ({c_email})? (Y/n) [Default: Y]: ").strip().lower()
        if pakai not in ["n", "no", "tidak"]:
            return {"tipe": "external", "email": c_email, "password": cached.get("password", "")}

    email = input("Masukkan Email SSO Eksternal    : ").strip()
    password = input("Masukkan Password SSO Eksternal : ").strip()
    if email and password:
        save_cached_auth(email, password)
    return {"tipe": "external", "email": email, "password": password}

def lakukan_login_otomatis(page, email, password):
    """
    Melakukan login SSO Eksternal secara otomatis:
    1. Klik tombol 'Lanjutkan dengan SSO Eksternal'.
    2. Isi username/email dan password.
    3. Submit dan tunggu redirect kembali ke FASIH.
    """
    try:
        print("  [Auto-Login] Memeriksa halaman login...")
        time.sleep(1.5)

        # 1. Cek apakah ada tombol "Lanjutkan dengan SSO Eksternal"
        sso_btn_selectors = [
            "button:has-text('SSO Eksternal')",
            "button:has-text('SSO External')",
            "a:has-text('SSO Eksternal')",
            "a:has-text('SSO External')",
            "button:has-text('Lanjutkan dengan SSO')",
            "button:has-text('Eksternal')"
        ]
        for sel in sso_btn_selectors:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                print(f"  [Auto-Login] Mengklik tombol '{btn.inner_text().strip()}'...")
                try:
                    btn.click(timeout=5000)
                except Exception:
                    btn.dispatch_event("click")
                time.sleep(2)
                break

        # 2. Tunggu input username dan password muncul
        u_box = None
        p_box = None
        for _ in range(15):
            for sel in [
                "input#username",
                "input[name='username']",
                "input[type='email']",
                "input[name='email']",
                "input[placeholder*='email' i]",
                "input[placeholder*='username' i]",
                "input[type='text']:visible"
            ]:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    u_box = loc.first
                    break
            for sel in [
                "input#password",
                "input[name='password']",
                "input[type='password']",
                "input[placeholder*='password' i]",
                "input[placeholder*='sandi' i]"
            ]:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    p_box = loc.first
                    break
            if u_box and p_box:
                break
            time.sleep(1)

        if not u_box or not p_box:
            print("  [Auto-Login] Field username/password tidak ditemukan di layar.")
            return False

        print(f"  [Auto-Login] Mengisi email ({email}) dan password...")
        u_box.fill("")
        u_box.fill(email)
        time.sleep(0.3)
        p_box.fill("")
        p_box.fill(password)
        time.sleep(0.5)

        # 3. Klik tombol submit
        submit_selectors = [
            "input#kc-login",
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Masuk')",
            "button:has-text('Login')",
            "button:has-text('Sign In')",
            "button:has-text('Log In')"
        ]
        submit_btn = None
        for sel in submit_selectors:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                submit_btn = loc.first
                break

        if submit_btn:
            print("  [Auto-Login] Mengirim form login (klik Submit)...")
            submit_btn.click()
        else:
            p_box.press("Enter")

        # 4. Tunggu pengalihan dan verifikasi login
        print("  [Auto-Login] Menunggu proses autentikasi dan redirect FASIH...")
        for det in range(25):
            time.sleep(1)
            # Cek jika ada notifikasi error dari server login (misal salah password)
            err = page.locator(".alert-error, .feedback-error, span#input-error, [class*='alert-danger'], text=/salah|invalid|gagal/i").first
            if err.count() > 0 and err.is_visible():
                print(f"  [Auto-Login Gagal] Pesan server: {err.inner_text().strip()}")
                return False

            if not cek_apakah_sesi_habis(page):
                print(f"  [Auto-Login] >> Berhasil terautentikasi dalam {det+1} detik! Sesi aktif.")
                time.sleep(1.5)
                return True

        if not cek_apakah_sesi_habis(page):
            return True

        print("  [Auto-Login] Timeout menunggu penyelesaian login.")
        return False

    except Exception as e:
        print(f"  [Auto-Login Error] Terjadi kendala saat login otomatis: {e}")
        return False

def pastikan_sesi_aktif(page, target_url=None, auth_config=None):
    """
    Jika sesi terdeteksi habis:
    - Jika SSO Eksternal: Lakukan login ulang otomatis, lalu buka kembali target_url tanpa intervensi user.
    - Jika SSO Pegawai (atau auto-login gagal): Bunyikan alarm suara dan tunggu user login manual di Chrome.
    """
    if not cek_apakah_sesi_habis(page):
        return True

    cfg = auth_config if auth_config is not None else CURRENT_AUTH

    print("\n" + "!" * 70)
    print(" [PERINGATAN] SESI LOGIN FASIH TELAH HABIS / LOGOUT OTOMATIS!")
    print("!" * 70)

    # 1. Coba auto-login jika mode SSO Eksternal
    if cfg and cfg.get("tipe") == "external":
        email = cfg.get("email")
        password = cfg.get("password")
        if email and password:
            print("  [Auto-Login] Memulai proses login ulang otomatis SSO Eksternal...")
            sukses = lakukan_login_otomatis(page, email, password)
            if sukses:
                print("  [Auto-Login] >> RE-LOGIN OTOMATIS BERHASIL! Sesi kembali aktif.")
                if target_url:
                    print(f"  [Navigasi] Memuat ulang URL assignment: {target_url}")
                    try:
                        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                    except Exception:
                        pass
                    tunggu_halaman_siap(page, timeout=25)
                return True
            else:
                print("  [Auto-Login] Auto-login belum berhasil, beralih ke instruksi manual.")

    # 2. Fallback manual (untuk SSO Pegawai atau jika auto-login gagal)
    bunyikan_alarm()
    print("\nLangkah yang perlu dilakukan:")
    print("1. Buka jendela Google Chrome FASIH yang sedang terbuka.")
    print("2. Selesaikan login kembali akun Anda.")
    print("3. Pastikan sudah berhasil masuk ke Dashboard FASIH.")
    print("4. KEMBALI KE TERMINAL INI lalu tekan [ENTER] untuk melanjutkan assignment ini.\n")

    while True:
        input(">> TEKAN [ENTER] DI SINI SETELAH ANDA SELESAI LOGIN KEMBALI DI BROWSER << ")
        time.sleep(1.5)
        if cek_apakah_sesi_habis(page):
            print("  [!] Browser masih berada di halaman login atau belum terautentikasi.")
            print("      Silakan selesaikan login di browser Chrome terlebih dahulu.")
            bunyikan_alarm()
        else:
            print("  [OK] Sesi login terdeteksi kembali AKTIF!")
            break

    if target_url:
        print(f"  [Navigasi] Memuat ulang URL assignment: {target_url}")
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"  [Navigasi] Peringatan memuat URL ({e}), memeriksa status form...")
        tunggu_halaman_siap(page, timeout=25)

    return True

def pilih_mode_dan_dataset():
    print("\n" + "="*70)
    print("      OTOMASI PENANDAAN KBLI FASIH-SM SE2026 (MULTI-PC PARALEL)")
    print("                    BPS KABUPATEN PANGKEP")
    print("="*70)
    print("PILIH NOMOR PC UNTUK KOMPUTER INI:")
    print("  [1] PC 1 (Assignment Master #300   s.d. #2.134  | 1.835 Assignment)")
    print("  [2] PC 2 (Assignment Master #2.135 s.d. #3.969  | 1.835 Assignment)")
    print("  [3] PC 3 (Assignment Master #3.970 s.d. #5.804  | 1.835 Assignment)")
    print("  [4] PC 4 (Assignment Master #5.805 s.d. #7.638  | 1.834 Assignment)")
    print("  [5] PC 5 (Assignment Master #7.639 s.d. #9.472  | 1.834 Assignment)")
    print("  [6] PC 6 (Assignment Master #9.473 s.d. #11.306 | 1.834 Assignment)")
    print("  [7] PC 7 (Assignment Master #11.307 s.d. #13.140 | 1.834 Assignment)")
    print("  [8] PC 8 (Assignment Master #13.141 s.d. #14.974 | 1.834 Assignment)")
    print("  " + "-"*66)
    print("  [9] Mode Manual / Dataset Lain (Koreksi / Semua 14.993 / Mark Sesuai Lengkap)")
    print("="*70)
    
    pilihan = input("Pilih PC (1 - 8) atau 9 untuk menu manual [Default: 1]: ").strip()
    if not pilihan:
        pilihan = "1"

    if pilihan in [str(i) for i in range(1, 9)]:
        pc_num = int(pilihan)
        path = os.path.join(DATA_PC_DIR, f"pc_{pc_num}.csv")
        if not os.path.exists(path):
            print(f"Error: File dataset {path} tidak ditemukan!")
            sys.exit(1)
        return path, f"PC_{pc_num}", pc_num
        
    # Menu manual / dataset lain
    print("\n" + "="*70)
    print("      PILIH DATASET MANUAL")
    print("="*70)
    print("1. [PRIORITAS] 72 Assignment PERLU KOREKSI (#DC_01 - Kasus Bukan Padi)")
    print("2. Seluruh 14.993 Assignment (Kombinasi #DC_00 dan #DC_01)")
    print("3. Khusus Assignment Murni SESUAI (Semua 14.974 Assignment)")
    print("="*70)
    sub_pil = input("Masukkan pilihan (1/2/3) [Default: 3]: ").strip()
    if sub_pil == "1":
        path = os.path.join(HASIL_DIR, "anomali_24_7309_perlu_koreksi_fasih.csv")
        return path, "perlu_koreksi", None
    elif sub_pil == "2":
        path = os.path.join(HASIL_DIR, "anomali_24_7309_analisis.csv")
        return path, "seluruh", None
    else:
        path = os.path.join(HASIL_DIR, "anomali_24_7309_mark_sesuai.csv")
        return path, "mark_sesuai", None

def tentukan_index_mulai(total_assignments, mode_nama, pc_num, done_count=0):
    if pc_num:
        default_start = done_count + 1 if done_count < total_assignments else total_assignments
    elif mode_nama == "mark_sesuai":
        default_start = max(159, done_count + 1)
    else:
        default_start = 1

    if default_start > total_assignments:
        default_start = total_assignments

    print("\n" + "-"*70)
    print("PILIHAN TITIK AWAL PENGERJAAN:")
    print(f"Total assignment dalam dataset : {total_assignments:,}")
    print(f"Telah selesai di checkpoint    : {done_count:,}")
    print(f"Rekomendasi titik mulai        : {default_start}")
    print("-"*70)
    
    label_pc = f"di PC {pc_num}" if pc_num else ""
    prompt = f"Mulai dari nomor urut assignment ke-berapa {label_pc}? (1-{total_assignments:,}) [Default: {default_start}]: "
    val = input(prompt).strip()
    if not val:
        start_idx = default_start
    else:
        try:
            start_idx = int(val)
            if start_idx < 1:
                start_idx = 1
            elif start_idx > total_assignments:
                start_idx = total_assignments
        except ValueError:
            print(f"Input '{val}' tidak valid. Menggunakan default {default_start}.")
            start_idx = default_start
            
    print(f"-> Otomasi akan dimulai dari assignment nomor urut ke-{start_idx:,}.\n")
    return start_idx

def muat_kamus_analisis():
    kamus = {}
    analisis_path = os.path.join(HASIL_DIR, "anomali_24_7309_analisis.csv")
    if os.path.exists(analisis_path):
        try:
            with open(analisis_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    aid = r.get("assignment_id", "").strip()
                    if aid:
                        if aid not in kamus:
                            kamus[aid] = []
                        kamus[aid].append(r)
        except Exception as e:
            print(f"Peringatan memuat kamus analisis: {e}")
    return kamus

def baca_data_dikelompokkan(filepath):
    """Membaca CSV dan mengelompokkan baris berdasarkan assignment_id."""
    kamus = None
    grouped = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            aid = row.get("assignment_id", "").strip()
            if not aid:
                continue
            nama_u = row.get("nama_usaha", "").strip()
            # Jika file hanya memuat assignment_id tanpa nama usaha, cari di kamus
            if not nama_u or nama_u == "-":
                if kamus is None:
                    kamus = muat_kamus_analisis()
                if aid in kamus:
                    grouped[aid] = kamus[aid]
                    continue

            if aid not in grouped:
                grouped[aid] = []
            if not row.get("rekomendasi_komentar_fasih"):
                kes = row.get("kesesuaian", "1")
                row["rekomendasi_komentar_fasih"] = "#DC_00" if str(kes) == "1" else "#DC_01"
            grouped[aid].append(row)
    return grouped

def tunggu_halaman_siap(page, timeout=25):
    """Menunggu indikator loading selesai dan form kuesioner siap, sambil memantau status login."""
    mulai = time.time()
    while time.time() - mulai < timeout:
        if cek_apakah_sesi_habis(page):
            return "SESSION_EXPIRED"

        loading = page.locator("text='Loading', text='Memuat', [class*='spinner'], #FormGear-loader:not(.f\\:hidden)").count()
        if loading == 0:
            if page.locator("div.fasih-form-sidebar, [title='SE2026 - L BLOK II'], #fasih-form").count() > 0:
                time.sleep(1)
                return True
        time.sleep(0.8)
    return False

def buka_dan_pilih_usaha(page, enterprise_info):
    """Membuka SE2026 - L BLOK II dan memilih usaha target hingga pertanyaan 13.g Kode KBLI benar-benar terbuka."""
    # 1. Cek apakah pertanyaan KBLI sudah terbuka di layar
    if page.locator("text=/13\\.\\s*[gh]\\.\\s*Kode KBLI/i").count() > 0:
        print("  [Usaha] Pertanyaan 13.g Kode KBLI sudah terbuka di layar.")
        return True

    # 2. Buka menu SE2026 - L BLOK II di sidebar
    blok2_trigger = page.locator("div.fasih-form-sidebar div[title='SE2026 - L BLOK II'], div.fasih-form-sidebar:has-text('SE2026 - L BLOK II')").first
    if blok2_trigger.count() == 0:
        blok2_trigger = page.locator("[title='SE2026 - L BLOK II']").first

    if blok2_trigger.count() > 0:
        print("  [Sidebar] Mengklik menu 'SE2026 - L BLOK II'...")
        blok2_trigger.scroll_into_view_if_needed()
        blok2_trigger.click()
        time.sleep(1.5)

    # Cek lagi apakah KBLI langsung terlihat
    if page.locator("text=/13\\.\\s*[gh]\\.\\s*Kode KBLI/i").count() > 0:
        return True

    # 3. Kumpulkan kata kunci pencarian usaha
    nama_usaha = enterprise_info.get("nama_usaha", "").upper()
    keg_utama = enterprise_info.get("keg_utama", "").upper()
    
    keywords = ["TANAMAN PANGAN", "PANGAN", "PADI"]
    if any(w in nama_usaha or w in keg_utama for w in ["TERNAK", "SAPI", "KAMBING", "AYAM", "BEBEK", "UNGGAS"]):
        keywords = ["PETERNAKAN", "TERNAK", "SAPI"]
    elif any(w in nama_usaha or w in keg_utama for w in ["IKAN", "UDANG", "TAMBAK", "BANDENG", "PERIKANAN"]):
        keywords = ["PERIKANAN", "IKAN", "TAMBAK"]
    elif any(w in nama_usaha or w in keg_utama for w in ["HORTI", "SAYUR", "BUAH", "JAHE", "JERUK", "CABE"]):
        keywords = ["HORTIKULTURA", "HORTI", "SAYUR"]
    elif any(w in nama_usaha or w in keg_utama for w in ["KEBUN", "KOPI", "CENGKEH", "SAWIT", "KELAPA"]):
        keywords = ["PERKEBUNAN", "KEBUN"]
    elif any(w in nama_usaha or w in keg_utama for w in ["BENGKEL", "DAGANG", "WARUNG", "KIOS", "TOKO", "JASA"]):
        keywords = ["PERDAGANGAN", "JASA", "BENGKEL", "DAGANG"]

    # 4. Jika di sidebar ada "Keterangan Usaha/Perusahaan", pastikan accordion terbuka
    ket_usaha = page.locator("div.fasih-form-sidebar div[title='Keterangan Usaha/Perusahaan'], aside div:has-text('Keterangan Usaha/Perusahaan')").first
    if ket_usaha.count() > 0:
        parent_col = ket_usaha.locator("xpath=ancestor::div[1]")
        col = parent_col.locator("div[id^='collapsible-']").first
        if col.count() > 0 and col.get_attribute("data-closed") is not None:
            print("  [Sidebar] Membuka accordion 'Keterangan Usaha/Perusahaan'...")
            ket_usaha.click()
            time.sleep(1)

    # 5. CARI DAN KLIK SUB-USAHA DI SIDEBAR
    sidebar_items = page.locator("aside div.fasih-form-sidebar div[title], aside div[class*='cursor-pointer']").all()
    sub_candidates = []
    for item in sidebar_items:
        try:
            t = (item.get_attribute("title") or item.locator(".tw\\:line-clamp-2").first.inner_text() or "").strip()
            if t and not any(skip in t.upper() for skip in ["SE2026", "BLOK", "PENGANTAR", "IDENTITAS", "KETERANGAN USAHA", "PEMBERI JAWABAN", "CATATAN", "ANOMALI", "PENGATURAN"]):
                sub_candidates.append((item, t))
        except Exception:
            pass

    if len(sub_candidates) > 0:
        print(f"  [Sidebar] Ditemukan {len(sub_candidates)} pilihan usaha: {[c[1] for c in sub_candidates]}")
        clicked = False
        for kw in keywords:
            for elem, title in sub_candidates:
                if kw in title.upper():
                    print(f"  [Sidebar] Mengklik usaha: '{title}'...")
                    elem.scroll_into_view_if_needed()
                    elem.click()
                    clicked = True
                    time.sleep(2)
                    break
            if clicked:
                break
                
        if not clicked:
            elem, title = sub_candidates[0]
            print(f"  [Sidebar] Mengklik usaha pertama: '{title}'...")
            elem.scroll_into_view_if_needed()
            elem.click()
            time.sleep(2)

    # Cek apakah 13.g sudah terlihat setelah klik sidebar
    for _ in range(6):
        if page.locator("text=/13\\.\\s*[gh]\\.\\s*Kode KBLI/i").count() > 0:
            print("  [Usaha] Berhasil masuk ke form rincian usaha!")
            return True
        time.sleep(0.5)

    # 6. JIKA BELUM TERLIHAT: KLIK KARTU USAHA DI LAYAR UTAMA (Main Form)
    print("  [Usaha] Mencari kartu usaha di layar utama (Lihat Rincian / Card)...")
    cards = page.locator("div[data-nested-view='true'], div.tw\\:flex:has(button:has-text('Lihat Rincian')), div.tw\\:flex:has(button:has-text('Isi Rincian'))").all()
    if len(cards) > 0:
        print(f"  [Card] Ditemukan {len(cards)} kartu usaha di layar utama.")
        clicked = False
        for kw in keywords:
            for c in cards:
                if kw in c.inner_text().upper():
                    print(f"  [Card] Mengklik kartu usaha '{kw}'...")
                    c.scroll_into_view_if_needed()
                    btn = c.locator("button:has-text('Lihat Rincian'), button:has-text('Isi Rincian'), button:has-text('Lanjutkan')").first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click()
                    else:
                        c.click()
                    clicked = True
                    time.sleep(2)
                    break
            if clicked:
                break

        if not clicked:
            print("  [Card] Mengklik kartu usaha pertama...")
            c = cards[0]
            c.scroll_into_view_if_needed()
            btn = c.locator("button:has-text('Lihat Rincian'), button:has-text('Isi Rincian'), button:has-text('Lanjutkan')").first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
            else:
                c.click()
            time.sleep(2)

    # Cek lagi apakah 13.g sudah terlihat setelah klik kartu
    for _ in range(6):
        if page.locator("text=/13\\.\\s*[gh]\\.\\s*Kode KBLI/i").count() > 0:
            print("  [Usaha] Berhasil masuk ke form rincian usaha!")
            return True
        time.sleep(0.5)

    # 7. JIKA MASIH BELUM TERLIHAT: KLIK TOMBOL GLOBAL 'LIHAT RINCIAN' / 'ISI RINCIAN'
    btn_rincian = page.locator("button:has-text('Lihat Rincian'), button:has-text('Isi Rincian'), button:has-text('Lanjutkan')").first
    if btn_rincian.count() > 0 and btn_rincian.is_visible():
        print("  [Button] Mengklik tombol rincian usaha di layar...")
        btn_rincian.click()
        time.sleep(2)

    # 8. JIKA MASIH BELUM: KLIK TOMBOL FLOATING 'Berikutnya: ...'
    btn_berikutnya = page.locator("button:has-text('Berikutnya:')").first
    if btn_berikutnya.count() > 0 and btn_berikutnya.is_visible():
        print(f"  [Button] Mengklik tombol '{btn_berikutnya.inner_text().strip()}'...")
        btn_berikutnya.click()
        time.sleep(2)

    # Verifikasi akhir
    for _ in range(6):
        if page.locator("text=/13\\.\\s*[gh]\\.\\s*Kode KBLI/i").count() > 0:
            print("  [Usaha] Berhasil masuk ke form rincian usaha!")
            return True
        time.sleep(0.5)

    print("  [Usaha] GAGAL: Pertanyaan 13.g Kode KBLI belum berhasil ditampilkan di layar.")
    return False

def temukan_tombol_catatan_kbli(page):
    """Mencari tombol kecil Catatan (title='Catatan' / SVG bubble) pada pertanyaan 13.g."""
    q_loc = page.locator("text=/13\\.\\s*[gh]\\.\\s*Kode KBLI/i").first
    if q_loc.count() == 0:
        q_loc = page.locator("text=/Kode KBLI/i").first

    if q_loc.count() == 0:
        return None

    q_loc.scroll_into_view_if_needed()
    time.sleep(0.5)

    # 1. Cari di container baris pertanyaan KBLI
    container = page.locator("div:has(> *:has-text('Kode KBLI')), div:has-text('13. g. Kode KBLI')").first
    if container.count() > 0:
        btns = container.locator("button[title='Catatan'], button[aria-label='Catatan'], button:has(svg path[d*='M8 9h8'])").all()
        # Cari yang terlihat di layar
        for b in btns:
            try:
                if b.is_visible() and "master kbli" not in b.inner_text().lower():
                    return b
            except Exception:
                pass
        for b in btns:
            try:
                box = b.bounding_box()
                if box and box["width"] > 0 and box["height"] > 0:
                    return b
            except Exception:
                pass
        # Fallback tombol pertama jika disembunyikan oleh CSS container query
        if len(btns) > 0:
            return btns[0]

    # 2. Cari di seluruh halaman yang dekat secara vertikal dengan 13.g
    q_box = q_loc.bounding_box()
    if q_box:
        target_y = q_box["y"]
        all_catatan_btns = page.locator("button[title='Catatan'], button[aria-label='Catatan'], button:has(svg path[d*='M8 9h8'])").all()
        best_btn = None
        min_diff = 999999
        for b in all_catatan_btns:
            try:
                b_box = b.bounding_box()
                if b_box and b_box["x"] > 400:
                    diff = abs(b_box["y"] - target_y)
                    if diff < min_diff:
                        min_diff = diff
                        best_btn = b
            except Exception:
                pass
        if best_btn and min_diff < 200:
            return best_btn

    # 3. Fallback tombol catatan pertama
    fallback = page.locator("button[title='Catatan'], button[aria-label='Catatan']").first
    if fallback.count() > 0:
        return fallback

    return None

def tutup_dialog_jika_ada(page):
    """Menutup modal dialog jika masih terbuka."""
    try:
        close_btn = page.locator("button[aria-label='Dismiss'], div[role='dialog'] button[aria-label*='close' i], div[role='dialog'] button:has-text('Tutup'), div[role='dialog'] button:has-text('Batal')").first
        if close_btn.count() > 0:
            close_btn.click(force=True, timeout=2000)
            time.sleep(0.5)
    except Exception:
        pass
    page.keyboard.press("Escape")
    time.sleep(0.5)

def tandai_komentar_kbli(page, rekomendasi):
    """Membuka pop-up komentar pada KBLI. Jika sudah terisi catatan apapun, langsung skip."""
    comment_btn = temukan_tombol_catatan_kbli(page)
    if not comment_btn or comment_btn.count() == 0:
        print("  [KBLI] Tombol Catatan KBLI tidak ditemukan.")
        return "NOT_FOUND"

    try:
        comment_btn.scroll_into_view_if_needed()
        comment_btn.click(force=True, timeout=4000)
        time.sleep(1.2)
    except Exception:
        try:
            comment_btn.dispatch_event("click")
            time.sleep(1.2)
        except Exception as e:
            print(f"  [KBLI] Gagal klik tombol catatan: {e}")
            return "FAILED"

    # Periksa isi dialog komentar
    dialog = page.locator("div[role='dialog'], div[class*='modal'], div[class*='drawer'], div:has(#dialog-cl-11-title)").first
    dialog_text = ""
    if dialog.count() > 0:
        dialog_text = dialog.inner_text()
    else:
        dialog_text = page.locator("body").inner_text()

    # Berdasarkan inspect: jika belum ada catatan, tampil teks 'Tidak ada catatan' / 'Belum ada catatan'
    kosong = ("tidak ada catatan" in dialog_text.lower()) or ("belum ada catatan" in dialog_text.lower())

    if not kosong:
        # Jika kolom catatan SUDAH TERISI (apapun isinya), langsung SKIP assignment ini
        print("  [KBLI] >> Kolom catatan 13.g SUDAH TERISI oleh pegawai. Langsung SKIP ke assignment berikutnya!")
        tutup_dialog_jika_ada(page)
        return "ALREADY_DONE"

    # Jika KOSONG: Isi catatan
    textarea = page.locator("textarea[placeholder*='Tambah catatan' i], div[role='dialog'] textarea, textarea:visible").last
    if textarea.count() > 0:
        textarea.fill(rekomendasi)
        time.sleep(0.5)

        # Klik tombol Simpan (title='Simpan')
        save_btn = page.locator("button[title='Simpan'], div[role='dialog'] button:has(svg path[d*='M10 14l11 -11']), div[role='dialog'] button:has-text('Simpan')").first
        if save_btn.count() > 0:
            save_btn.click(force=True, timeout=3000)
            print(f"  [KBLI] >> Berhasil memberikan komentar: {rekomendasi}")
            time.sleep(1.2)
        else:
            textarea.press("Enter")
            print(f"  [KBLI] >> Komentar dikirim via Enter: {rekomendasi}")
            time.sleep(1)

        tutup_dialog_jika_ada(page)
        return "SUCCESS"
    else:
        print("  [KBLI] Textarea komentar dialog tidak muncul.")
        tutup_dialog_jika_ada(page)
        return "FAILED"

def proses_bagian_catatan(page, teks_penjelasan):
    """
    Menavigasi ke bagian CATATAN menggunakan selector ID presisi:
    1. Menu CATATAN: div[title='CATATAN']
    2. Toggle switch 'Tampilkan Anomali Usaha dan Keluarga': #cek_anomali_button
    3. Toggle switch 'Anomali diselesaikan oleh admin': #anomali_admin
    4. Textarea penjelasan admin: #catatan_anomali_admin textarea
    5. Tombol perbarui waktu: #waktu_selesai
    """
    # 1. Klik menu CATATAN di sidebar
    catatan_menu = page.locator("div.fasih-form-sidebar div[title='CATATAN'], [title='CATATAN']").first
    if catatan_menu.count() > 0:
        catatan_menu.scroll_into_view_if_needed()
        catatan_menu.click()
        time.sleep(1.5)
    else:
        print("  [Catatan] Menu CATATAN di sidebar tidak ditemukan.")
        return False

    # 2. Toggle 'Tampilkan Anomali Usaha dan Keluarga' (#cek_anomali_button)
    cek_anomali = page.locator("#cek_anomali_button").first
    if cek_anomali.count() > 0:
        is_checked = cek_anomali.locator("[data-checked]").count() > 0 or cek_anomali.get_attribute("data-checked") is not None
        if not is_checked:
            ctrl = cek_anomali.locator("div[id$='-control']").first
            if ctrl.count() > 0:
                ctrl.click()
            else:
                cek_anomali.locator("input[type='checkbox']").first.click(force=True)
            print("  [Catatan] Switch 'Tampilkan Anomali Usaha dan Keluarga' diaktifkan (ON).")
            time.sleep(0.5)
        else:
            print("  [Catatan] Switch 'Tampilkan Anomali Usaha dan Keluarga' SUDAH AKTIF.")

    # 3. Toggle 'Anomali diselesaikan oleh admin' (#anomali_admin)
    anomali_admin = page.locator("#anomali_admin").first
    if anomali_admin.count() > 0:
        is_checked = anomali_admin.locator("[data-checked]").count() > 0 or anomali_admin.get_attribute("data-checked") is not None
        if not is_checked:
            ctrl = anomali_admin.locator("div[id$='-control']").first
            if ctrl.count() > 0:
                ctrl.click()
            else:
                anomali_admin.locator("input[type='checkbox']").first.click(force=True)
            print("  [Catatan] Switch 'Anomali diselesaikan oleh admin' diaktifkan (ON).")
            time.sleep(0.5)
        else:
            print("  [Catatan] Switch 'Anomali diselesaikan oleh admin' SUDAH AKTIF.")

    # 4. Textarea 'Penjelasan Penyelesaian Anomali oleh Admin' (#catatan_anomali_admin textarea)
    penjelasan_box = page.locator("#catatan_anomali_admin textarea").first
    if penjelasan_box.count() == 0:
        penjelasan_box = page.locator("//div[contains(., 'Penjelasan Penyelesaian Anomali oleh Admin')]//textarea").first

    if penjelasan_box and penjelasan_box.count() > 0:
        current_val = penjelasan_box.input_value().strip()
        if current_val:
            print(f"  [Catatan] Penjelasan Admin SUDAH TERISI: '{current_val}'. (Tidak ditimpa)")
        else:
            penjelasan_box.fill(teks_penjelasan)
            print(f"  [Catatan] Penjelasan Admin diisi: '{teks_penjelasan}'")
            time.sleep(0.5)
    else:
        print("  [Catatan] Textarea Penjelasan Admin tidak ditemukan.")

    # 5. Tombol 'Perbarui Waktu' jika belum terisi waktu
    waktu_container = page.locator("#waktu_selesai").first
    if waktu_container.count() > 0:
        btn_perbarui = waktu_container.locator("button:has-text('Perbarui Waktu')").first
        if btn_perbarui.count() > 0:
            has_waktu = waktu_container.locator("span.tw\\:font-medium, span[class*='font-medium']").count() > 0
            if not has_waktu:
                btn_perbarui.click()
                print("  [Catatan] Waktu Selesai diperbarui.")
                time.sleep(0.5)

    return True

def kirim_dan_konfirmasi(page):
    """Mengklik tombol Kirim di header dan menyetujui modal konfirmasi."""
    kirim_btn = page.locator("button:has-text('Kirim')").filter(has_text="Kirim").first
    if kirim_btn.count() == 0 or not kirim_btn.is_visible():
        print("  [Kirim] Tombol Kirim di header tidak ditemukan.")
        return False

    print("  [Kirim] Mengklik tombol Kirim...")
    kirim_btn.click()
    time.sleep(1.5)

    # Modal konfirmasi
    modal = page.locator("div[role='dialog'], [id^='alert-dialog-'], [id^='dialog-']").first
    if modal.count() > 0 and modal.is_visible():
        confirm_btn = modal.locator("button:has-text('Kirim'), button:has-text('Ya'), button:has-text('Konfirmasi'), button:has-text('Setuju')").first
        if confirm_btn.count() > 0:
            print("  [Kirim] Mengonfirmasi pengiriman di dialog...")
            confirm_btn.click()
            time.sleep(3)
            print("  >> KUESIONER BERHASIL DIKIRIM DAN DIKONFIRMASI!")
            return True

    time.sleep(2)
    print("  >> Kuesioner terkirim.")
    return True

def main():
    dataset_path, mode_nama, pc_num = pilih_mode_dan_dataset()
    auth_config = pilih_metode_login()
    global CURRENT_AUTH
    CURRENT_AUTH = auth_config

    grouped_assignments = baca_data_dikelompokkan(dataset_path)
    assignments_list = list(grouped_assignments.items())
    total_assignments = len(assignments_list)
    
    chk_path = get_checkpoint_path(pc_num)
    chk = load_checkpoint(chk_path)
    done_set = set(chk.get("done_assignments", []))
    
    if pc_num:
        print(f"\n[PC {pc_num}] Memuat {total_assignments:,} assignment unik dari: {os.path.basename(dataset_path)}")
        print(f"File Checkpoint: {os.path.basename(chk_path)} ({len(done_set):,} selesai)")
    else:
        print(f"\nMemuat {total_assignments:,} assignment unik dari: {os.path.basename(dataset_path)}")
        print(f"File Checkpoint: {os.path.basename(chk_path)} ({len(done_set):,} selesai)")

    start_index = tentukan_index_mulai(total_assignments, mode_nama, pc_num, len(done_set))
    
    with sync_playwright() as p:
        print("[1/3] Membuka Google Chrome...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="chrome",
            headless=False,
            no_viewport=True,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        context.set_default_navigation_timeout(60000)
        page = context.pages[0] if context.pages else context.new_page()
        
        print(f"[2/3] Membuka halaman FASIH: {FASIH_URL}")
        try:
            page.goto(FASIH_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"  [Catatan Jaringan] Waktu muat awal agak lambat ({e}).")
            print("  Jendela Chrome tetap terbuka, silakan langsung login di Chrome.")
        
        if auth_config.get("tipe") == "external":
            print("\n" + "*"*70)
            print("LOGIN SSO EKSTERNAL (OTOMATIS):")
            print(f"Akun : {auth_config.get('email')}")
            print("Sistem akan login otomatis dan re-login jika sesi logout.")
            print("*"*70)
            sukses_login = lakukan_login_otomatis(page, auth_config["email"], auth_config["password"])
            if sukses_login:
                print("[Auth] >> BERHASIL LOGIN OTOMATIS! Langsung memulai pengerjaan...")
                time.sleep(2)
            else:
                print("[Auth] >> Perlu bantuan login di browser Chrome.")
                bunyikan_alarm()
                input(">> Silakan login di browser Chrome, lalu TEKAN [ENTER] DI SINI << ")
        else:
            print("\n" + "*"*70)
            print("PANDUAN LOGIN SSO PEGAWAI (MANUAL):")
            print("1. Jika Anda belum login, klik 'Masuk dengan Akun Pegawai' di Chrome.")
            print("2. Masukkan Email dan Password akun pegawai Anda.")
            print("3. Setelah berhasil masuk ke Dashboard FASIH...")
            print("*"*70)
            input(">> TEKAN [ENTER] DI TERMINAL INI SETELAH ANDA BERHASIL LOGIN DI BROWSER << ")
        
        print("\n[3/3] Memulai PROSES OTOMASI PENUH tanpa henti...")
        
        try:
            for idx, (assign_id, enterprise_list) in enumerate(assignments_list[start_index - 1 :], start=start_index):
                # Lewati jika sudah ada di checkpoint (kecuali jika tepat sama dengan start_index yg dimasukkan manual)
                if assign_id in done_set and idx != start_index:
                    print(f"[{idx}/{total_assignments}] SKIP (Sudah di-checkpoint): {assign_id}")
                    continue
                    
                edit_url = f"https://fasih-sm.bps.go.id/app/assignment/{SURVEY_ID}/{assign_id}/edit"
                master_idx = enterprise_list[0].get("master_index", "-")
                
                print("\n" + "="*70)
                if pc_num:
                    print(f"[PC {pc_num} | {idx}/{total_assignments} (Master #{master_idx}/14974)] MEMPROSES: {assign_id}")
                else:
                    print(f"[{idx}/{total_assignments}] MEMPROSES OTOMATIS: {assign_id}")
                print(f"  Jumlah Usaha : {len(enterprise_list)}")
                print(f"  URL Edit     : {edit_url}")
                print("="*70)
                
                berhasil_proses = False
                skip_seluruh_assignment = False
                max_retries = 3
                attempt = 0

                while attempt < max_retries and not berhasil_proses and not skip_seluruh_assignment:
                    attempt += 1
                    if attempt > 1:
                        print(f"  [Retry] Percobaan ke-{attempt}/{max_retries} untuk assignment {assign_id}...")

                    # 1. Pastikan sesi login aktif
                    pastikan_sesi_aktif(page, target_url=None)

                    try:
                        try:
                            page.goto(edit_url, wait_until="domcontentloaded", timeout=60000)
                        except Exception as e_nav:
                            print(f"  [Navigasi] Info load URL ({e_nav}), memeriksa status form...")
                        status_siap = tunggu_halaman_siap(page, timeout=25)

                        if status_siap == "SESSION_EXPIRED" or cek_apakah_sesi_habis(page):
                            pastikan_sesi_aktif(page, target_url=edit_url)
                            attempt -= 1
                            continue

                        if not status_siap:
                            if cek_apakah_sesi_habis(page):
                                pastikan_sesi_aktif(page, target_url=edit_url)
                                attempt -= 1
                                continue
                            print("  >> Peringatan: Halaman kuesioner belum terbuka sempurna.")
                            time.sleep(2)
                            continue

                        ada_tidak_sesuai = False
                        gagal_navigasi = False

                        for ent_idx, ent in enumerate(enterprise_list, 1):
                            rekomendasi = ent.get("rekomendasi_komentar_fasih", "").strip()
                            if not rekomendasi:
                                kesesuaian = ent.get("kesesuaian", "1")
                                rekomendasi = "#DC_00" if str(kesesuaian) == "1" else "#DC_01"

                            if rekomendasi == "#DC_01":
                                ada_tidak_sesuai = True

                            nama_u = ent.get("nama_usaha", "-")
                            print(f"  -> [Usaha {ent_idx}/{len(enterprise_list)}] {nama_u} (Target: {rekomendasi})")

                            # Cek status sesi sebelum melangkah
                            if cek_apakah_sesi_habis(page):
                                raise Exception("SESSION_EXPIRED")

                            # 1. Buka sub-usaha di BLOK II
                            buka_ok = buka_dan_pilih_usaha(page, ent)
                            if not buka_ok:
                                if cek_apakah_sesi_habis(page):
                                    raise Exception("SESSION_EXPIRED")
                                print("  >> [GAGAL MASUK USAHA] Halaman rincian usaha 13.g tidak berhasil dibuka.")
                                gagal_navigasi = True
                                break

                            # 2. Tandai komentar KBLI (13.g / 13.h)
                            status_komentar = tandai_komentar_kbli(page, rekomendasi)
                            
                            if status_komentar == "ALREADY_DONE":
                                print("  >> [SKIP ASSIGNMENT] Assignment ini SUDAH DIKERJAKAN oleh pegawai (komentar KBLI sudah ada).")
                                print("  >> Melewati pengisian dan pengiriman, langsung lanjut ke assignment berikutnya!")
                                skip_seluruh_assignment = True
                                break

                            if status_komentar in ["NOT_FOUND", "FAILED"]:
                                if cek_apakah_sesi_habis(page):
                                    raise Exception("SESSION_EXPIRED")
                                print(f"  >> [PERINGATAN] Status komentar KBLI: {status_komentar}.")
                                gagal_navigasi = True
                                break

                        # Jika di-skip karena pegawai sudah mengisi catatan
                        if skip_seluruh_assignment:
                            chk["skipped"].append(assign_id)
                            done_set.add(assign_id)
                            save_checkpoint(chk_path, chk)
                            break

                        # Jika gagal navigasi ke rincian usaha / tombol KBLI
                        if gagal_navigasi:
                            time.sleep(2)
                            continue

                        # Cek sesi sebelum masuk CATATAN
                        if cek_apakah_sesi_habis(page):
                            raise Exception("SESSION_EXPIRED")

                        # 3. Masuk ke Bagian CATATAN
                        teks_penjelasan = "Tidak Sesuai dan Telah diperbaiki" if ada_tidak_sesuai else "Sesuai"
                        proses_bagian_catatan(page, teks_penjelasan)

                        # Cek sesi sebelum Kirim
                        if cek_apakah_sesi_habis(page):
                            raise Exception("SESSION_EXPIRED")

                        # 4. Kirim dan Konfirmasi Kuesioner
                        kirim_ok = kirim_dan_konfirmasi(page)

                        if kirim_ok:
                            chk["done_assignments"].append(assign_id)
                            done_set.add(assign_id)
                            save_checkpoint(chk_path, chk)
                            berhasil_proses = True
                            print(f"  >> SUKSES: Assignment {assign_id} selesai.")
                            break
                        else:
                            if cek_apakah_sesi_habis(page):
                                raise Exception("SESSION_EXPIRED")
                            print(f"  >> GAGAL: Assignment {assign_id} belum terkirim pada percobaan {attempt}.")
                            time.sleep(2)

                    except Exception as e:
                        if "SESSION_EXPIRED" in str(e) or cek_apakah_sesi_habis(page):
                            print(f"  [Sesi] Terdeteksi logout / sesi habis saat proses: {e}")
                            pastikan_sesi_aktif(page, target_url=edit_url)
                            attempt -= 1
                            continue
                        else:
                            print(f"  >> Error pada percobaan ke-{attempt}: {e}")
                            time.sleep(2)

                if not berhasil_proses and not skip_seluruh_assignment:
                    print(f"  >> [FINAL FAILED] Assignment {assign_id} gagal setelah {max_retries} percobaan.")
                    chk["failed"].append(assign_id)
                    save_checkpoint(chk_path, chk)

                # Jeda aman 2 detik
                print("  Jeda 2 detik sebelum assignment berikutnya...")
                time.sleep(2)

        except KeyboardInterrupt:
            print("\n" + "="*70)
            print("[INFO] Otomasi dihentikan sementara oleh pengguna (KeyboardInterrupt).")
            print("Checkpoint telah disimpan dengan aman.")
            print("="*70)
            save_checkpoint(chk_path, chk)

        print("\n" + "="*70)
        print("PROSES OTOMASI FASIH SELESAI / TERHENTI!")
        print(f"Total Selesai : {len(chk['done_assignments']):,}")
        print(f"Total Dilewati : {len(chk['skipped']):,}")
        print(f"Total Gagal/Cek: {len(chk['failed']):,}")
        print("="*70)
        context.close()

if __name__ == "__main__":
    main()
