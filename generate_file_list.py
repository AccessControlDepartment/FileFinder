import os
import time
import sqlite3

FOLDER_PATHS = [
    r"S:\SD_Bilgi_Takip\1 - PERSONEL BOLUMU",
    r"S:\SD_Bilgi_Takip\2 - ARAC VE MALZEME BOLUMU"
]
DB_FILE = "file_list.db"

def create_db():
    """SQLite veritabanını oluşturur ve dosya tablosunu oluşturur."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Dosya yollarının tekrar eklenmesini önlemek için UNIQUE ekledik
    c.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE
        )
    ''')
    
    conn.commit()
    conn.close()

def save_file_list():
    """Klasördeki tüm dosyaları tarayıp SQLite veritabanına kaydeder."""
    start_time = time.time()

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("DELETE FROM files")

    file_list = []
    for folder in FOLDER_PATHS:
        for root, _, files in os.walk(folder):
            file_list.extend([(os.path.join(root, file),) for file in files])

    # Toplu ekleme işlemi
    if file_list:
        c.executemany("INSERT INTO files (file_path) VALUES (?)", file_list)

    conn.commit()
    conn.close()

    elapsed_time = time.time() - start_time
    print(f"✅ {FOLDER_PATHS} içindeki tüm dosyalar SQLite veritabanına kaydedildi.")
    print(f"⏳ İşlem süresi: {elapsed_time:.2f} saniye.")

if __name__ == "__main__":
    create_db()
    save_file_list()
