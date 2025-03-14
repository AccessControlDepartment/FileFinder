import eel
import os
import sqlite3
import shutil
import re
import unicodedata
import time

# Eel başlat
eel.init("web")

# Global veritabanı bağlantısı
conn = None

# Dosya yolu önbelleği - performans için dosya yollarını saklayacak
file_paths_cache = None

# Arama sonuçlarını önbelleği
search_cache = {}

# Metni normalize eden ve tüm özel karakterleri kaldıran fonksiyon
def normalize_text(text):
    if not isinstance(text, str) or not text:
        return ""
    
    # Unicode normalizasyonu
    text = unicodedata.normalize('NFKD', text)
    # ASCII olmayan karakterleri kaldır (aksanları ve özel işaretleri kaldırır)
    text = ''.join([c for c in text if not unicodedata.combining(c)])
    
    # Özel Türkçe karakter dönüşümleri
    replacements = {
        'İ': 'I', 'Ö': 'O', 'Ç': 'C', 'Ü': 'U', 'Ğ': 'G', 'Ş': 'S',
        'ı': 'i', 'ö': 'o', 'ç': 'c', 'ü': 'u', 'ğ': 'g', 'ş': 's'
    }
    
    for turkish, english in replacements.items():
        text = text.replace(turkish, english)
    
    # Tüm metni küçük harfe çevir
    text = text.lower()
    
    # Alfanümerik olmayan karakterleri boşluğa çevir
    text = re.sub(r'[^a-z0-9]', ' ', text)
    
    # Birden fazla boşluğu tek boşluğa indirgeme
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

# Veritabanı tablosunu bul ve ayarla
def find_database_table():
    try:
        temp_conn = sqlite3.connect('file_list.db')
        cursor = temp_conn.cursor()
        
        # Veritabanındaki tüm tabloları listele
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if not tables:
            print("Veritabanında hiç tablo bulunamadı!")
            temp_conn.close()
            return None
            
        # Bulunan ilk tabloyu kullan (normalde sadece bir tablo olması beklenir)
        table_name = tables[0][0]
        print(f"Bulunan tablo adı: {table_name}")
        
        # Tablo yapısını kontrol et
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        print(f"Tablo sütunları: {[col[1] for col in columns]}")
        
        temp_conn.close()
        return table_name
    except Exception as e:
        print(f"Tablo arama hatası: {str(e)}")
        return None

# Global tablo adı
TABLE_NAME = None

# Veritabanını başlat ve optimize et
def init_database():
    global conn, TABLE_NAME
    try:
        # Önce tablo adını bul (eğer henüz bulunmadıysa)
        if TABLE_NAME is None:
            TABLE_NAME = find_database_table()
            if TABLE_NAME is None:
                print("Tablo adı bulunamadı, işlem durduruluyor.")
                return
        
        conn = sqlite3.connect('file_list.db')
        cursor = conn.cursor()
        
        # İndeks oluştur (eğer yoksa)
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_file_path ON {TABLE_NAME}(file_path)")
        
        # Veritabanını optimize et
        cursor.execute("PRAGMA optimize")
        cursor.execute("PRAGMA cache_size = 10000")  # Önbellek boyutunu artır
        cursor.execute("PRAGMA temp_store = MEMORY")  # Geçici tabloları RAM'de tut
        cursor.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging modunu etkinleştir
        
        conn.commit()
        print(f"Veritabanı bağlantısı başlatıldı ve optimize edildi. Tablo adı: {TABLE_NAME}")
    except Exception as e:
        print(f"Veritabanı başlatma hatası: {str(e)}")
        if conn:
            conn.close()
            conn = None

# Veritabanından dosya yollarını al
def read_file_list():
    global conn, TABLE_NAME
    if conn is None or TABLE_NAME is None:
        init_database()
        if TABLE_NAME is None:
            return []
        
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT file_path FROM {TABLE_NAME}")
        rows = cursor.fetchall()
        return [row[0] for row in rows] if rows else []
    except sqlite3.Error as e:
        print(f"Veritabanı hatası: {e}")
        # Hata durumunda bağlantıyı yeniden kurmayı dene
        try:
            if conn:
                conn.close()
            init_database()
        except:
            pass
        return []

# Veritabanının varlığını kontrol eden fonksiyon
@eel.expose
def is_database_updated():
    try:
        if os.path.exists('file_list.db'):
            # Veritabanının boyutunu kontrol et, dosya var ama boş değil mi?
            size = os.path.getsize('file_list.db')
            return size > 0  # Dosya boyutu 0'dan büyükse güncellenmiş kabul et
        return False  # Dosya yoksa güncellenmemiş
    except Exception as e:
        print(f"Veritabanı durumu kontrol hatası: {str(e)}")
        return False

def get_all_file_paths(force_refresh=False):
    global file_paths_cache, conn, TABLE_NAME
    
    # Eğer önbellekte varsa ve yenileme istenmediyse, önbellekten döndür
    if file_paths_cache is not None and not force_refresh:
        return file_paths_cache
    
    if conn is None or TABLE_NAME is None:
        init_database()
        if TABLE_NAME is None:
            return []
    
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT file_path FROM {TABLE_NAME}")
        rows = cursor.fetchall()
        
        # Sonuçları önbelleğe al
        file_paths_cache = [row[0] for row in rows]
        
        # Normalize edilmiş versiyonlarını da önbelleğe al
        # Bu işlemi de önbelleğe alabiliriz ancak şimdilik sadece dosya yollarını önbelleğe alalım
        
        return file_paths_cache
    except Exception as e:
        print(f"Dosya yolları okuma hatası: {str(e)}")
        return []

# JavaScript tarafından çağrılacak: Gelişmiş dosya arama işlemi
@eel.expose
def search_file(query):
    global conn, TABLE_NAME, search_cache
    
    if not query or len(query.strip()) == 0:
        return []
    
    # Sorguyu temizle
    query = query.strip()
    
    # Sonuç zaten önbellekte var mı kontrol et
    if query in search_cache:
        return search_cache[query]
    
    try:
        if conn is None or TABLE_NAME is None:
            init_database()
            if TABLE_NAME is None:
                return []
            
        # Orijinal sorgu ve normalize edilmiş versiyonu 
        original_query = query
        normalized_query = normalize_text(query)
        search_terms = normalized_query.split()
        
        # SQL sorgusu için temel arama desenleri - hem orijinal hem de normalize edilmiş terim için
        sql_search_patterns = []
        params = []
        
        # Her arama terimi için bir OR koşulu ekle (geniş sonuç kümesi oluşturmak için)
        for term in search_terms:
            sql_search_patterns.append("lower(file_path) LIKE ?")
            params.append(f"%{term}%")
        
        # Orijinal sorgu terimleri için de ekle (Türkçe karakterleri de dene)
        for term in original_query.lower().split():
            if term not in search_terms:  # Normalize edilmiş terimlerle çakışmayı önle
                sql_search_patterns.append("lower(file_path) LIKE ?")
                params.append(f"%{term}%")
        
        # SQL sorgusunu oluştur - potansiyel tüm sonuçları toplamak için OR kullan
        sql = f"""
            SELECT file_path FROM {TABLE_NAME}
            WHERE {" OR ".join(sql_search_patterns)}
            LIMIT 5000  -- Daha geniş bir sonuç kümesi al
        """
        
        # Sorguyu çalıştır
        cursor = conn.cursor()
        cursor.execute(sql, params)
        
        # Potansiyel sonuçları al
        potential_results = [row[0] for row in cursor.fetchall()]
        
        # Bu aşamada normalize edilmiş dosya yollarını arama terimleriyle karşılaştır
        final_results = []
        
        for file_path in potential_results:
            normalized_path = normalize_text(file_path)
            
            # Tüm arama terimlerinin dosya yolunda olup olmadığını kontrol et
            if all(term in normalized_path for term in search_terms):
                final_results.append(file_path)
        
        # Sonucu önbelleğe al
        search_cache[query] = final_results
        
        return final_results
        
    except Exception as e:
        print(f"Arama hatası: {str(e)}")
        # Hata durumunda bağlantıyı yeniden kurmayı dene
        try:
            if conn:
                conn.close()
            init_database()
        except:
            pass
        return []

# Veritabanı güncellendiğinde önbelleği temizle
def clear_cache():
    global file_paths_cache, search_cache
    file_paths_cache = None
    search_cache = {}
    print("Önbellek temizlendi")

# JavaScript tarafından çağrılacak: Dosya veya klasör açma
@eel.expose
def open_file_or_folder(file_path, action):
    try:
        if action == "folder":
            folder_path = os.path.dirname(file_path)
            if os.path.exists(folder_path):
                os.startfile(folder_path)
        elif action == "file":
            if os.path.exists(file_path):
                os.startfile(file_path)
        return "Tamamlandı"
    except Exception as e:
        return f"Hata: {str(e)}"

# JavaScript tarafından çağrılacak: Veritabanını güncelleme
@eel.expose
def update_file_list():
    global conn, TABLE_NAME
    max_retries = 3
    retry_count = 0
    
    # İlerleme bildirimi için JavaScript fonksiyonu
    def update_progress(percentage, message):
        eel.updateProgress(percentage, message)()
    
    try:
        # Önce mevcut bağlantıyı kapat
        if conn:
            conn.close()
            conn = None
        
        update_progress(10, "Veritabanı bağlantısı kapatıldı")
        
        source_file = "S:\\SD_Bilgi_Takip\\Programlar\\db\\file_list.db"
        temp_file = "file_list_temp.db"
        dest_file = "file_list.db"
        
        # Dosya boyutlarını kontrol et
        if os.path.exists(source_file) and os.path.exists(dest_file):
            source_size = os.path.getsize(source_file)
            dest_size = os.path.getsize(dest_file)
            
            update_progress(20, f"Dosya boyutları kontrol ediliyor... Ağ: {source_size}B, Yerel: {dest_size}B")
            
            if source_size == dest_size:
                update_progress(100, "✅ Veritabanı zaten güncel!")
                return "✅ Veritabanı zaten güncel!"
        else:
            if not os.path.exists(source_file):
                update_progress(100, "❌ Ağ veritabanı dosyasına erişilemiyor!")
                return "❌ Ağ veritabanı dosyasına erişilemiyor!"
        
        update_progress(25, "Dosya boyutları farklı veya dosya yok, güncelleme başlatılıyor...")
        
        # Yedek oluştur (eğer varsa)
        if os.path.exists(dest_file):
            backup_file = "file_list_backup.db"
            shutil.copy2(dest_file, backup_file)
            update_progress(30, "Yedek alındı")
        
        while retry_count < max_retries:
            try:
                # Önce geçici bir dosyaya kopyala
                update_progress(30, f"Veritabanı indiriliyor...")
                shutil.copy2(source_file, temp_file)
                
                # Kopyalanan dosyayı optimize et
                update_progress(50, "Veritabanı indirme tamamlandı, optimizasyon başlatılıyor")
                
                # Yeni geçici bağlantı
                temp_conn = sqlite3.connect(temp_file)
                cursor = temp_conn.cursor()
                
                # Önce tablo adını bul
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                if not tables:
                    raise Exception("Veritabanında hiç tablo bulunamadı!")
                    
                temp_table_name = tables[0][0]
                update_progress(60, "Tablo yapısı analiz ediliyor")
                
                # İndeks oluştur
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_file_path ON {temp_table_name}(file_path)")
                
                # Optimize et
                update_progress(70, "İndeksler oluşturuluyor")
                cursor.execute("PRAGMA optimize")
                cursor.execute("PRAGMA cache_size = 10000")
                cursor.execute("PRAGMA temp_store = MEMORY")
                cursor.execute("PRAGMA journal_mode = WAL")
                
                update_progress(80, "Veritabanı optimize ediliyor")
                cursor.execute("ANALYZE")
                
                # Değişiklikleri kaydet
                temp_conn.commit()
                
                # Bağlantıyı kapat
                temp_conn.close()
                
                # Optimizasyon tamamlandı, dosyayı yerine koy
                update_progress(90, "Optimizasyon tamamlandı, veritabanı uygulamaya aktarılıyor")
                
                # Eğer varsa eski dosyayı sil
                if os.path.exists(dest_file):
                    os.remove(dest_file)
                
                # Geçici dosyayı hedef dosya olarak yeniden adlandır
                os.rename(temp_file, dest_file)
                
                # Tablo adını sıfırla ve yeniden bulmasını sağla
                TABLE_NAME = None
                
                # Veritabanı güncellemesinden sonra yeniden başlat ve optimize et
                update_progress(95, "Veritabanı yapılandırması tamamlanıyor")
                init_database()
                
                update_progress(100, "✅ Güncelleme ve optimizasyon başarıyla tamamlandı")
                return "✅ Güncelleme Başarılı"
                
            except Exception as e:
                retry_count += 1
                error_message = f"Deneme {retry_count}/{max_retries}: {str(e)}"
                update_progress(30, error_message)
                print(f"Güncelleme hatası: {error_message}")
                
                # Geçici dosyayı temizle
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                
                if retry_count < max_retries:
                    update_progress(35, f"5 saniye içinde tekrar denenecek...")
                    time.sleep(5)
                else:
                    # Yedekten geri dön
                    if os.path.exists("file_list_backup.db"):
                        shutil.copy2("file_list_backup.db", dest_file)
                        update_progress(40, "Yedekten geri yüklendi")
                    
                    update_progress(100, "❌ Güncelleme başarısız oldu")
                    return f"❌ Güncelleme Hatası! {str(e)}"
    
    except Exception as e:
        update_progress(100, f"❌ Güncelleme Hatası: {str(e)}")
        clear_cache()
        return f"❌ Güncelleme Hatası! {str(e)}"

# Tam kapsamlı veritabanı optimizasyonu
@eel.expose
def full_optimize_database():
    global conn, TABLE_NAME
    try:
        # Önce mevcut bağlantıyı kapat
        if conn:
            conn.close()
            conn = None
            
        if TABLE_NAME is None:
            TABLE_NAME = find_database_table()
            if TABLE_NAME is None:
                return "❌ Tablo adı bulunamadı!"
                
        # Yeni geçici bağlantı
        temp_conn = sqlite3.connect('file_list.db')
        cursor = temp_conn.cursor()
        
        # İndeks oluştur
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_file_path ON {TABLE_NAME}(file_path)")
        
        # Veritabanını tamamen optimize et
        cursor.execute("VACUUM")
        cursor.execute("ANALYZE")
        
        temp_conn.commit()
        temp_conn.close()
        
        # Ana bağlantıyı yeniden başlat
        init_database()
        
        return "✔ Veritabanı tam olarak optimize edildi"
    except Exception as e:
        return f"❌ Optimizasyon hatası: {str(e)}"

# Uygulama kapatılmadan önce bağlantıyı kapat
@eel.expose
def close_application():
    global conn
    if conn:
        try:
            conn.close()
            print("Veritabanı bağlantısı kapatıldı.")
        except:
            pass
    return "Uygulama kapatıldı"

# Başlangıçta veritabanı bağlantısını kur
init_database()

# Uygulamayı başlat
eel.start("index.html", size=(800, 1200), block=True)

# Uygulama kapatıldığında bağlantıyı kapat (block=True olduğunda buraya gelmez)
if conn:
    conn.close()