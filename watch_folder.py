import time
import os
import atexit
import shutil
import sqlite3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# İzlenecek klasörler
WATCHED_FOLDERS = [
    "S:\\SD_Bilgi_Takip\\1 - PERSONEL BOLUMU",
    "S:\\SD_Bilgi_Takip\\2 - ARAC VE MALZEME BOLUMU"
]

DB_FILE = "file_list.db"  # Yerel veritabanı dosyası
REMOTE_DB_PATH = "S:\\SD_Bilgi_Takip\\Programlar\\db\\file_list.db"  # Kopyalanacak yer

def create_db():
    """SQLite veritabanını oluşturur ve tabloyu hazırlar."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE
        )
    ''')
    
    conn.commit()
    conn.close()

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self):
        """Veritabanını oluştur ve tabloyu hazırlamaya çalış"""
        create_db()

    def on_created(self, event):
        """Yeni bir dosya eklendiğinde çağrılır."""
        if not event.is_directory and not event.src_path.endswith("file_list.db"):
            self.add_file_to_db(event.src_path)
            print(f"➕ Yeni dosya eklendi: {event.src_path}")

    def on_deleted(self, event):
        """Bir dosya silindiğinde çağrılır."""
        if not event.is_directory and not event.src_path.endswith("file_list.db"):
            self.remove_file_from_db(event.src_path)
            print(f"❌ Dosya silindi: {event.src_path}")

    def on_modified(self, event):
        """Bir dosya değiştirildiğinde çağrılır."""
        if not event.is_directory and not event.src_path.endswith("file_list.db"):
            print(f"✏️ Dosya değiştirildi: {event.src_path}")
    
    def add_file_to_db(self, file_path):
        """Yeni dosyayı SQLite veritabanına ekler. Eğer zaten varsa, hata vermeden atlar."""
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO files (file_path) VALUES (?)", (file_path,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"⚠️ Veritabanı hatası: {e}")
        finally:
            conn.close()
    
    def remove_file_from_db(self, file_path):
        """Silinen dosyayı SQLite veritabanından çıkarır."""
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("DELETE FROM files WHERE file_path = ?", (file_path,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"⚠️ Veritabanı hatası: {e}")
        finally:
            conn.close()

def get_file_size(file_path):
    """Dosya boyutunu döndürür. Dosya yoksa 0 döndürür."""
    return os.path.getsize(file_path) if os.path.exists(file_path) else 0

def sync_database():
    """Her 60 saniyede bir kendi file_list.db dosyasını REMOTE_DB_PATH ile karşılaştırır ve farklı ise kopyalar."""
    while True:
        local_size = get_file_size(DB_FILE)
        remote_size = get_file_size(REMOTE_DB_PATH)

        if local_size != remote_size:
            os.makedirs(os.path.dirname(REMOTE_DB_PATH), exist_ok=True)  # Hedef klasörü oluştur
            shutil.copy2(DB_FILE, REMOTE_DB_PATH)  # Dosyayı kopyala
            print(f"📂 Güncellendi: {DB_FILE} → {REMOTE_DB_PATH}")
        
        time.sleep(60)  # 60 saniye bekle ve tekrar kontrol et

def watch_folders():
    """İzlenecek tüm klasörleri ekleyerek değişiklikleri takip eder."""
    event_handler = FileChangeHandler()
    observer = Observer()

    for folder in WATCHED_FOLDERS:
        observer.schedule(event_handler, path=folder, recursive=True)
        print(f"👀 {folder} izleniyor...")

    observer.start()
    atexit.register(observer.stop)  # Program kapanırken observer'ı durdur

    try:
        sync_database()
    except KeyboardInterrupt:
        print("🛑 İzleme durduruluyor...")
        observer.stop()
        observer.join()

if __name__ == "__main__":
    watch_folders()
