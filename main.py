import struct
import os


class SistemDeFisiere:
    # --- CONSTANTELE HARDWARE (conform descrierii proiectului) ---
    UA = 16  # Dimensiunea unei Unități de Alocare (bytes)
    NR_UA = 4096  # Numărul total de Unități de Alocare
    DIM_HDD = UA * NR_UA  # Dimensiunea totală a HDD-ului (64 KB)

    OFFSET_FAT = 0
    OFFSET_ROOT = 8192  # ROOT începe de la octetul 8192 (UA 512 * 16)
    MAX_FISIERE = 64  # Numărul maxim de intrări posibile în ROOT

    def __init__(self, nume_disc="hdd.bin"):
        self.nume_disc = nume_disc
        # Creăm un buffer în memoria RAM de 64 KB plin cu zerouri.
        # Aici facem toate modificările înainte de a le salva pe disc.
        self.ram_buffer = bytearray(self.DIM_HDD)

    def formateaza_disc(self):
        print(f"[*] Se formateaza discul virtual '{self.nume_disc}'...")

        # Cursorul care ne arată la ce octet suntem în Tabela FAT
        offset_fat = 0

        # Parcurgem fiecare dintre cele 4096 de locații FAT
        for i in range(self.NR_UA):
            # Stabilim starea unității de alocare
            if 0 <= i <= 511:
                valoare = 1  # UA rezervată pentru FAT
            elif 512 <= i <= 575:
                valoare = 2  # UA rezervată pentru ROOT
            else:
                valoare = 0  # UA liberă pentru date/fișiere

            # Împachetăm valoarea pe 2 octeți (Unsigned Short - "<H")
            octeti = struct.pack('<H', valoare)

            # Scriem cei 2 octeți în memoria noastră RAM
            self.ram_buffer[offset_fat: offset_fat + 2] = octeti
            offset_fat += 2

        # Salvăm rezultatul final pe "discul" fizic
        self._salveaza_pe_disc()
        print("[*] Formatare completa. HDD-ul este pregatit!")

    def _salveaza_pe_disc(self):
        # Deschidem/creăm fișierul în modul scriere binară ('wb')
        with open(self.nume_disc, "wb") as f:
            f.write(self.ram_buffer)

    def comanda_dir(self, detaliat=False):
        """
        Execută comanda DIR.
        Dacă detaliat=True (DIR -a), afișează toate metadatele.
        Altfel, afișează doar numele și extensia.
        """
        fisiere_gasite = 0
        for i in range(self.MAX_FISIERE):
            offset_curent = self.OFFSET_ROOT + (i * 16)
            date_slot = self.ram_buffer[offset_curent: offset_curent + 16]
            nume_b, ext_b, marime, prima_ua, attr = struct.unpack('<8s3sHHB', date_slot)

            if nume_b[0] == 0:
                continue

            nume = nume_b.decode('utf-8').strip('\x00').strip()
            ext = ext_b.decode('utf-8').strip('\x00').strip()
            fisiere_gasite += 1

            if detaliat:
                print(f"{nume}.{ext}\t| Marime: {marime} B | Prima UA: {prima_ua} | Attr: {attr}")
            else:
                print(f"{nume}.{ext}")

        if fisiere_gasite == 0:
            print(" -> [INFO] Niciun fisier gasit.")

    def creeaza_intrare_root(self, nume, extensie, marime, prima_ua, attr=0):
        """
        Găsește un slot liber în ROOT și salvează metadatele fișierului.
        """
        print(f"[*] Incercare scriere in ROOT: {nume}.{extensie} ...")

        # 1. Căutăm primul slot liber
        slot_liber = -1
        for i in range(self.MAX_FISIERE):
            offset_curent = self.OFFSET_ROOT + (i * 16)
            # Verificăm dacă primul octet din acest slot este 0
            if self.ram_buffer[offset_curent] == 0:
                slot_liber = i
                break  # Ne oprim la primul slot liber găsit

        if slot_liber == -1:
            print(" -> [WARNING] Tabela ROOT este plina! Nu se mai pot crea fisiere.")
            return False

        # 2. Pregătim și formatăm datele
        # .encode('utf-8') transformă string-ul în octeți (bytes)
        # [:8] taie numele dacă e mai lung de 8 caractere (deși vom face validarea la comandă)
        # .ljust(8, b'\x00') umple cu octeți de zero până se ating fix 8 bytes
        nume_b = nume.encode('utf-8')[:8].ljust(8, b'\x00')
        ext_b = extensie.encode('utf-8')[:3].ljust(3, b'\x00')

        # 3. Împachetăm datele conform formatului
        date_slot = struct.pack('<8s3sHHB', nume_b, ext_b, marime, prima_ua, attr)

        # 4. Scriem în RAM exact la adresa slotului găsit
        offset_scriere = self.OFFSET_ROOT + (slot_liber * 16)
        self.ram_buffer[offset_scriere: offset_scriere + 16] = date_slot

        # 5. Salvăm pe disc
        self._salveaza_pe_disc()
        print(f" -> [SUCCES] Fisier salvat in ROOT la slotul {slot_liber}.")
        return True

    def gaseste_ua_libere(self, necesar_ua):
        """
        Caută în Tabela FAT un număr de 'necesar_ua' unități de alocare libere (marcate cu 0).
        Returnează o listă cu indecșii acestora, sau o listă goală dacă nu e spațiu.
        """
        ua_libere = []
        offset_fat = self.OFFSET_FAT

        # Parcurgem toate cele 4096 de intrări din Tabela FAT
        for i in range(self.NR_UA):
            # Citim valoarea de la locația curentă (2 octeți) din RAM
            octeti = self.ram_buffer[offset_fat: offset_fat + 2]
            valoare = struct.unpack('<H', octeti)[0]

            # Valoarea 0 înseamnă că Unitatea de Alocare este liberă
            if valoare == 0:
                ua_libere.append(i)
                # Dacă am găsit câte ne trebuiau, ne oprim din căutat
                if len(ua_libere) == necesar_ua:
                    break

            offset_fat += 2  # Avansăm cursorul cu 2 octeți pentru următoarea intrare FAT

        # Dacă bucla s-a terminat și nu am strâns suficiente UA-uri
        if len(ua_libere) < necesar_ua:
            return []

        return ua_libere

    def scrie_inlantuire_fat(self, lista_ua):
        """
        Primește o listă de indecși UA libere și le înlănțuie în tabela FAT.
        Ultimul element din listă primește valoarea 3 (Sfârșit de fișier).
        Returnează prima UA din listă, pentru a putea fi salvată în ROOT.
        """
        if not lista_ua:
            return -1  # Eroare (listă goală)

        # Parcurgem lista până la penultimul element
        for i in range(len(lista_ua) - 1):
            ua_curenta = lista_ua[i]
            ua_urmatoare = lista_ua[i + 1]

            # Calculăm adresa din memorie pentru ua_curenta (fiecare are 2 octeți)
            offset_scriere = self.OFFSET_FAT + (ua_curenta * 2)

            # Împachetăm 'ua_urmatoare' pe 2 octeți și o scriem în FAT
            octeti = struct.pack('<H', ua_urmatoare)
            self.ram_buffer[offset_scriere: offset_scriere + 2] = octeti

        # Pentru ultima unitate din listă, punem valoarea 3 (EOF)
        ultima_ua = lista_ua[-1]
        offset_scriere = self.OFFSET_FAT + (ultima_ua * 2)
        octeti_eof = struct.pack('<H', 3)
        self.ram_buffer[offset_scriere: offset_scriere + 2] = octeti_eof

        # Salvăm pe disc noua stare a memoriei FAT
        self._salveaza_pe_disc()
        print(f"[*] Inlantuire FAT creata cu succes. Ultima UA ({ultima_ua}) a primit valoarea 3.")

        # Returnăm capul listei (prima UA), ca să îl trimitem către tabela ROOT
        return lista_ua[0]

    def scrie_date_fisier(self, lista_ua, date_bytes):
        """
        Scrie octeții în locațiile fizice de pe disc (în interiorul blocurilor de date alocate).
        """
        for i, index_ua in enumerate(lista_ua):
            # Decupăm câte 16 octeți (o UA) din datele fișierului
            start = i * self.UA
            sfarsit = start + self.UA
            bucata = date_bytes[start:sfarsit]

            # Dacă am ajuns la final și bucata e mai mică de 16 octeți, facem padding cu zero
            if len(bucata) < self.UA:
                bucata = bucata.ljust(self.UA, b'\x00')

            # Calculăm adresa absolută pe HDD (offset-ul fizic)
            offset_fizic = index_ua * self.UA

            # Scriem pe disc în buffer-ul RAM
            self.ram_buffer[offset_fizic: offset_fizic + self.UA] = bucata

        self._salveaza_pe_disc()
        print("[*] Datele (continutul) au fost scrise fizic pe HDD.")

    def comanda_create(self, nume_complet, dimensiune_str, model):
        """
        Execută comanda CREATE: Validează numele, generează conținutul, caută spațiu,
        înlănțuie în FAT, scrie fizic și salvează intrarea în ROOT.
        """
        dimensiune = int(dimensiune_str)

        # 1. Separăm numele de extensie și validăm regula DOS (8.3)
        if "." in nume_complet:
            nume, extensie = nume_complet.split(".", 1)
        else:
            nume, extensie = nume_complet, ""

        if len(nume) > 8 or len(extensie) > 3:
            print(f" -> [WARNING] Fisierul '{nume_complet}' depaseste limita numelui (max 8) sau a extensiei (max 3).")
            return

        # 2. Generăm textul prestabilit în funcție de argument (-ALFA, -NUM, -HEX)
        if model == "-ALFA":
            baza = "abcdefghijklmnopqrstuvwxyz"
        elif model == "-NUM":
            baza = "0123456789"
        elif model == "-HEX":
            baza = "0123456789ABCDEF"
        else:
            baza = "0"

        # Multiplicăm string-ul de bază până acoperim dimensiunea cerută, apoi îl tăiem exact la numărul de bytes
        continut_string = (baza * ((dimensiune // len(baza)) + 1))[:dimensiune]
        date_bytes = continut_string.encode('utf-8')

        # 3. Calculăm necesarul de Unități de Alocare
        # Ex: 25 bytes / 16 = 1 rest 9 -> deci avem nevoie de 2 UA
        necesar_ua = max(1, (dimensiune + self.UA - 1) // self.UA)

        # 4. Executăm pașii de sistem OS
        lista_ua = self.gaseste_ua_libere(necesar_ua)
        if not lista_ua:
            print(" -> [WARNING] Spatiu insuficient pe disc!")
            return

        prima_ua = self.scrie_inlantuire_fat(lista_ua)
        self.scrie_date_fisier(lista_ua, date_bytes)

        # 5. Salvăm intrarea în Tabela ROOT
        rezultat = self.creeaza_intrare_root(nume, extensie, dimensiune, prima_ua, 0)
        if rezultat:
            print(f" -> [SUCCES] Fisierul '{nume_complet}' ({dimensiune} bytes) creat cu succes!")

    def comanda_delete(self, nume_complet):
        """
        Executa comanda DELETE: Cauta fisierul in ROOT, sterge intrarea,
        apoi elibereaza intregul lant de unitati de alocare din tabela FAT.
        """
        if "." in nume_complet:
            nume_cautat, ext_cautata = nume_complet.split(".", 1)
        else:
            nume_cautat, ext_cautata = nume_complet, ""

        slot_gasit = -1
        prima_ua = -1

        # 1. Cautam fisierul in ROOT
        for i in range(self.MAX_FISIERE):
            offset_curent = self.OFFSET_ROOT + (i * 16)
            date_slot = self.ram_buffer[offset_curent: offset_curent + 16]
            nume_b, ext_b, marime, ua_start, attr = struct.unpack('<8s3sHHB', date_slot)

            # Sarim peste sloturile deja goale
            if nume_b[0] == 0:
                continue

            nume = nume_b.decode('utf-8').strip('\x00').strip()
            ext = ext_b.decode('utf-8').strip('\x00').strip()

            # Verificam daca am gasit fisierul cerut
            if nume == nume_cautat and ext == ext_cautata:
                slot_gasit = i
                prima_ua = ua_start

                # Stergem intrarea din ROOT setand primul octet pe 0
                self.ram_buffer[offset_curent] = 0
                break

        if slot_gasit == -1:
            print(f" -> [WARNING] Fisierul '{nume_complet}' nu a fost gasit.")
            return

        # 2. Eliberam Unitatile de Alocare din FAT
        ua_curenta = prima_ua

        # Parcurgem lantul pana dam de 3 (EOF) sau 0 (ca masura de siguranta)
        while ua_curenta != 3 and ua_curenta != 0:
            offset_fat = self.OFFSET_FAT + (ua_curenta * 2)

            # Citim unde duce legatura mai departe
            octeti = self.ram_buffer[offset_fat: offset_fat + 2]
            ua_urmatoare = struct.unpack('<H', octeti)[0]

            # Eliberam unitatea curenta marcand-o cu 0 in RAM
            self.ram_buffer[offset_fat: offset_fat + 2] = struct.pack('<H', 0)

            # Trecem la urmatoarea veriga din lant
            ua_curenta = ua_urmatoare

        # 3. Salvam modificarile pe discul fizic
        self._salveaza_pe_disc()
        print(f" -> [SUCCES] Fisierul '{nume_complet}' a fost sters cu succes.")

    def comanda_rename(self, nume_vechi_complet, nume_nou_complet):
        """
        Executa comanda RENAME: Cauta fisierul in ROOT si ii actualizeaza
        doar cei 11 octeti corespunzatori numelui si extensiei.
        """
        # 1. Prelucram numele vechi
        if "." in nume_vechi_complet:
            nume_vechi, ext_veche = nume_vechi_complet.split(".", 1)
        else:
            nume_vechi, ext_veche = nume_vechi_complet, ""

        # 2. Prelucram si validam numele nou
        if "." in nume_nou_complet:
            nume_nou, ext_noua = nume_nou_complet.split(".", 1)
        else:
            nume_nou, ext_noua = nume_nou_complet, ""

        if len(nume_nou) > 8 or len(ext_noua) > 3:
            print(f" -> [WARNING] Noul nume '{nume_nou_complet}' depaseste limitele (8 nume, 3 extensie).")
            return

        # 3. Cautam fisierul vechi in ROOT
        slot_gasit = -1
        for i in range(self.MAX_FISIERE):
            offset_curent = self.OFFSET_ROOT + (i * 16)
            date_slot = self.ram_buffer[offset_curent: offset_curent + 16]
            nume_b, ext_b, _, _, _ = struct.unpack('<8s3sHHB', date_slot)

            if nume_b[0] == 0: continue

            nume = nume_b.decode('utf-8').strip('\x00').strip()
            ext = ext_b.decode('utf-8').strip('\x00').strip()

            if nume == nume_vechi and ext == ext_veche:
                slot_gasit = i
                break

        if slot_gasit == -1:
            print(f" -> [WARNING] Fisierul sursa '{nume_vechi_complet}' nu exista.")
            return

        # 4. Pregatim noile date in format de bytes
        nume_nou_b = nume_nou.encode('utf-8')[:8].ljust(8, b'\x00')
        ext_noua_b = ext_noua.encode('utf-8')[:3].ljust(3, b'\x00')

        # 5. Suprascriem strict zona de nume (8 octeti) si extensie (3 octeti) din ROOT
        offset_scriere = self.OFFSET_ROOT + (slot_gasit * 16)
        self.ram_buffer[offset_scriere: offset_scriere + 8] = nume_nou_b
        self.ram_buffer[offset_scriere + 8: offset_scriere + 11] = ext_noua_b

        # 6. Salvam pe disc
        self._salveaza_pe_disc()
        print(f" -> [SUCCES] Fisierul a fost redenumit in '{nume_nou_complet}'.")

    def comanda_copy(self, nume_sursa_complet, nume_dest_complet):
        """
        Executa comanda COPY: Citeste datele fisierului sursa mergand pe
        lantul FAT si creeaza un fisier identic pe disc.
        """
        # 1. Prelucram numele sursei si destinatiei
        if "." in nume_sursa_complet:
            nume_sursa, ext_sursa = nume_sursa_complet.split(".", 1)
        else:
            nume_sursa, ext_sursa = nume_sursa_complet, ""

        if "." in nume_dest_complet:
            nume_dest, ext_dest = nume_dest_complet.split(".", 1)
        else:
            nume_dest, ext_dest = nume_dest_complet, ""

        if len(nume_dest) > 8 or len(ext_dest) > 3:
            print(f" -> [WARNING] Numele destinatiei '{nume_dest_complet}' depaseste limitele (8.3).")
            return

        # 2. Cautam fisierul sursa in ROOT
        slot_gasit = -1
        marime_sursa = 0
        prima_ua_sursa = -1
        attr_sursa = 0

        for i in range(self.MAX_FISIERE):
            offset_curent = self.OFFSET_ROOT + (i * 16)
            date_slot = self.ram_buffer[offset_curent: offset_curent + 16]
            nume_b, ext_b, marime, ua_start, attr = struct.unpack('<8s3sHHB', date_slot)

            if nume_b[0] == 0: continue

            nume = nume_b.decode('utf-8').strip('\x00').strip()
            ext = ext_b.decode('utf-8').strip('\x00').strip()

            if nume == nume_sursa and ext == ext_sursa:
                slot_gasit = i
                marime_sursa = marime
                prima_ua_sursa = ua_start
                attr_sursa = attr
                break

        if slot_gasit == -1:
            print(f" -> [WARNING] Fisierul sursa '{nume_sursa_complet}' nu exista.")
            return

        # 3. Citim datele fizice ale fisierului sursa navigand prin FAT
        date_citite = bytearray()
        ua_curenta = prima_ua_sursa

        while ua_curenta != 3 and ua_curenta != 0:
            # Extragem blocul de 16 octeti
            offset_fizic = ua_curenta * self.UA
            bloc_date = self.ram_buffer[offset_fizic: offset_fizic + self.UA]
            date_citite.extend(bloc_date)

            # Citim din FAT adresa urmatoarei UA
            offset_fat = self.OFFSET_FAT + (ua_curenta * 2)
            ua_curenta = struct.unpack('<H', self.ram_buffer[offset_fat: offset_fat + 2])[0]

        # Taiem zerourile adaugate in plus (padding-ul) pentru a pastra marimea exacta
        date_citite = date_citite[:marime_sursa]

        # 4. Alocam spatiu si scriem fisierul nou
        necesar_ua = max(1, (marime_sursa + self.UA - 1) // self.UA)
        lista_ua_libere = self.gaseste_ua_libere(necesar_ua)

        if not lista_ua_libere:
            print(" -> [WARNING] Spatiu insuficient pe disc pentru a copia fisierul!")
            return

        # Folosim metodele deja existente pentru a construi clona
        prima_ua_dest = self.scrie_inlantuire_fat(lista_ua_libere)
        self.scrie_date_fisier(lista_ua_libere, date_citite)

        # 5. Salvam clona in ROOT
        rezultat = self.creeaza_intrare_root(nume_dest, ext_dest, marime_sursa, prima_ua_dest, attr_sursa)
        if rezultat:
            print(f" -> [SUCCES] Fisierul a fost copiat cu numele '{nume_dest_complet}'.")

    def porneste_sistem(self):
        """
        Verifică dacă există deja discul fizic. Dacă da, îl încarcă în RAM.
        Dacă nu, îl formatează de la zero.
        """
        if os.path.exists(self.nume_disc):
            print(f"[*] Se incarca discul existent '{self.nume_disc}'...")
            with open(self.nume_disc, "rb") as f:
                # Citim toti cei 64KB direct in buffer
                self.ram_buffer = bytearray(f.read())
        else:
            self.formateaza_disc()

    def ruleaza_shell(self):
        """
        Bucla principala care interactioneaza cu utilizatorul.
        """
        print("\n=== my_OS a pornit cu succes ===")
        print("Scrieti 'exit' pentru a inchide sistemul.\n")

        while True:
            # Citim input-ul și îl împărțim în cuvinte
            input_cmd = input("my_OS> ").strip().split()

            if not input_cmd:
                continue

            # Transformam prima portiune (comanda) in majuscule
            input_cmd[0] = input_cmd[0].upper()

            match input_cmd:
                case ["EXIT"]:
                    print("Sistemul se inchide...")
                    break

                case ["DIR"]:
                    self.comanda_dir(detaliat=False)

                # Permitem atat "dir -a" cat si "dir -A"
                case ["DIR", "-a"] | ["DIR", "-A"]:
                    self.comanda_dir(detaliat=True)

                case ["CREATE", nume_complet, dimensiune, model]:
                    # Fortam si modelul (-alfa, -num) sa fie majuscule pentru comparatia din cod
                    self.comanda_create(nume_complet, dimensiune, model.upper())

                case ["DELETE", nume]:
                    self.comanda_delete(nume)

                case ["RENAME", nume_vechi, nume_nou]:
                    self.comanda_rename(nume_vechi, nume_nou)

                case ["COPY", sursa, dest]:
                    self.comanda_copy(sursa, dest)

                case _:
                    print(" -> [WARNING] Comanda nerecunoscuta sau argumente gresite.")


# --- PUNCTUL DE INTRARE ÎN PROGRAM ---
if __name__ == "__main__":
    os_virtual = SistemDeFisiere()
    os_virtual.porneste_sistem()
    os_virtual.ruleaza_shell()