# Proiect Sistem de Operare: Implementare Sistem de Fișiere FAT

Acest proiect simulează un sistem de operare de bază (Virtual OS) care gestionează un hard disk virtual (`hdd.bin`) folosind o arhitectură bazată pe File Allocation Table (FAT). 

## Arhitectura Sistemului
* **Dimensiune Unitate de Alocare (UA):** 16 bytes
* **Număr total UA:** 4096
* **Capacitate totală HDD:** 64 KB (65.536 bytes)
* **Tabela FAT:** Ocupă 512 UA (8192 bytes), folosind locații de 2 octeți.
* **Tabela ROOT:** Ocupă 64 UA (1024 bytes), permițând un maxim de 64 de fișiere.

## Comenzi Suportate (Shell)
* `DIR` / `DIR -a`: Afișează conținutul tabelei ROOT (nume, extensie, mărime, prima UA, atribute).
* `CREATE nume dim -model`: Creează un fișier de dimensiunea specificată, populat automat (-ALFA, -NUM, -HEX). Alocă dinamic spațiu în FAT și actualizează ROOT-ul.
* `DELETE nume`: Șterge intrarea din ROOT și eliberează lanțul de memorie din FAT.
* `RENAME vechi nou`: Redenumește un fișier direct în ROOT, fără a reloca datele.
* `COPY sursa dest`: Parcurge lanțul FAT al fișierului sursă, buffer-ează datele, alocă unități noi și creează o clonă fizică și logică a fișierului.

---

## Partea Teoretică: Analiza modificării parametrilor sistemului

### Întrebarea 1: Ce se întâmplă dacă mărimea UA este 32, iar numărul de UA este 4096?
Dacă mărimea Unității de Alocare se dublează, dar numărul lor rămâne constant, apar următoarele efecte asupra sistemului:

1. **Capacitatea discului se dublează:** Discul va avea acum dimensiunea de 4096 UA * 32 bytes = 131.072 bytes (128 KB).
2. **Spațiul logic ocupat de FAT scade:** Tabela FAT are în continuare nevoie de 4096 de intrări (a câte 2 octeți), ocupând fizic tot 8192 bytes. Însă, deoarece o UA are acum 32 de octeți, FAT-ul va consuma doar 256 UA pe disc (8192 / 32 = 256), spre deosebire de 512 UA în cazul inițial. Tabela FAT devine mai "compactă" raportat la noile "cutii" de memorie.
3. **Tabela ROOT ocupă mai puține UA:** Dimensiunea unei intrări ROOT (metadatele unui fișier) rămâne de 16 bytes. Deoarece o UA are acum 32 bytes, într-o singură UA vor încăpea 2 intrări de fișiere. Pentru cele 64 de sloturi maxime, ROOT va consuma doar 32 UA pe disc (față de 64 UA inițial).
4. **Creșterea fragmentării interne (Dezavantaj major):** Spațiul minim pe care sistemul îl poate aloca devine 32 de octeți. Dacă salvăm un fișier care conține doar 1 byte de informație, acesta va bloca o întreagă unitate de 32 de bytes. Astfel, 31 de bytes vor fi irosiți (fragmentare internă), ceea ce face sistemul ineficient pentru stocarea fișierelor foarte mici.

### Întrebarea 2: Ce se întâmplă dacă mărimea UA este 16, iar numărul de UA este 8192?
Dacă mărimea Unității de Alocare rămâne mică, dar numărul de "cutii" se dublează, efectele sunt următoarele:

1. **Capacitatea discului se dublează:** Discul va avea dimensiunea de 8192 UA * 16 bytes = 131.072 bytes (128 KB).
2. **Dimensiunea tabelei FAT se dublează:** Acum trebuie să ținem evidența a 8192 de unități. FAT va avea 8192 de locații. Valoarea maximă a unui index este 8191, care încă se încadrează confortabil într-un număr reprezentat pe 2 octeți (limita fiind 65535). Prin urmare, dimensiunea totală a FAT în bytes va fi de 8192 locații * 2 octeți = 16.384 bytes.
3. **Spațiul ocupat de FAT pe disc crește:** Cei 16.384 de bytes ai tabelei FAT, împărțiți la 16 bytes per UA, înseamnă că FAT va ocupa 1024 UA pe disc (față de 512 UA inițial). Astfel, "overhead-ul" administrativ al sistemului crește proporțional.
4. **Tabela ROOT rămâne neschimbată:** Dimensiunea UA este de 16 bytes, dimensiunea unei intrări ROOT este de 16 bytes. ROOT va ocupa în continuare fix 64 UA pentru cele 64 de fișiere permise.
5. **Gestionare mai eficientă a spațiului (Avantaj):** Deoarece dimensiunea minimă alocabilă rămâne de 16 bytes, fragmentarea internă este păstrată la un nivel redus. Fișierele mici nu vor irosi mult spațiu, sistemul oferind un echilibru mai bun la nivel granular față de Scenariul 1.