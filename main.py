import eel
import os

# Eel başlat
eel.init('web')

# Desteklenen dosya türleri
ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt')

@eel.expose
def search_files(search_term):
    found_files = []
    search_paths = ['C:\\', 'S:\\']
    
    print("Arama başlatıldı...")
    
    try:
        for path in search_paths:
            print(f"Tarama yapılıyor: {path}")
            for root, dirs, files in os.walk(path):
                for file in files:
                    if search_term.lower() in file.lower():
                        found_files.append(os.path.join(root, file))
    except KeyboardInterrupt:
        print("\nArama işlemi iptal edildi.")
        return []  # Kullanıcı arama işlemini iptal ettiğinde boş liste döndür.
    
    print(f"Toplam bulunan {len(found_files)} dosya.")
    return found_files

@eel.expose
def open_file(file_path):
    try:
        os.startfile(file_path)  # Windows için dosyayı aç
    except Exception as e:
        print(f"Dosya açılamadı: {e}")

# Uygulamayı başlat
eel.start('index.html', size=(800, 600), port=8001)
