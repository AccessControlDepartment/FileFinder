import os
import eel
import concurrent.futures

# 🚀 Eel Başlatma
eel.init('web')  # web klasörünü HTML/CSS/JS dosyaları için kullan

# 🔹 Aranacak klasörler
search_paths = [
    "C:\\Users\\selda.cetin\\Desktop", 
    "S:\\SD_Access", 
    "S:\\SD_ACS", 
    "S:\\SD_Bilgi_Takip"
]

# 🔹 Maksimum taranacak dosya boyutu (MB) - Opsiyonel
MAX_FILE_SIZE_MB = 50

def search_in_directory(path, search_term):
    """ Belirtilen dizinde arama yapar ve bulunan dosyaları listeler. """
    found_files = []

    if not os.path.exists(path):
        print(f"❌ {path} bulunamadı, atlanıyor...")
        return []

    print(f"🔍 Taranıyor: {path}")

    try:
        for root, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)

                # 🔹 Belirtilen boyuttan büyük dosyaları atla (Opsiyonel)
                if os.path.getsize(file_path) > (MAX_FILE_SIZE_MB * 1024 * 1024):
                    continue

                # 🔹 Aranan kelime dosya adında geçiyor mu?
                if search_term.lower() in file.lower():
                    found_files.append(file_path)

    except PermissionError:
        print(f"⚠️ İzin hatası: {path} atlanıyor...")

    return found_files

@eel.expose
def search_files(search_term):
    """ Tüm belirlenen dizinlerde arama yapar ve sonuçları döndürür. """
    found_files = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(search_in_directory, path, search_term): path for path in search_paths}

        for future in concurrent.futures.as_completed(futures):
            found_files.extend(future.result())

    print(f"✅ Toplam {len(found_files)} dosya bulundu.")
    return found_files

# 🔥 Eel ile Masaüstü Uygulama Olarak Aç
eel.start('index.html', size=(800, 600))
