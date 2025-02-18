function searchFiles() {
    let keyword = document.getElementById("searchInput").value.trim();

    if (!keyword) {
        alert("Lütfen bir anahtar kelime girin!");
        return;
    }

    eel.search_files(keyword)(function(results) {
        let resultsContainer = document.getElementById("resultsContainer");
        resultsContainer.innerHTML = "";  // Önceki sonuçları temizle

        if (results.length === 0) {
            resultsContainer.innerHTML = "<p>Sonuç bulunamadı.</p>";
            return;
        }

        results.forEach(function(filePath) {
            let resultItem = document.createElement("div");
            resultItem.classList.add("result-item");

            let fileText = document.createElement("div");
            fileText.classList.add("file-path");
            fileText.textContent = filePath;

            let openButton = document.createElement("button");
            openButton.classList.add("btn-open");
            openButton.textContent = "Aç";
            openButton.onclick = function() {
                eel.open_file(filePath);  // Python tarafında dosyayı açma işlemi
            };

            resultItem.appendChild(fileText);
            resultItem.appendChild(openButton);
            resultsContainer.appendChild(resultItem);
        });
    });
}
