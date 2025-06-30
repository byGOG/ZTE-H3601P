import requests
import time
import re
import hashlib
import codecs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QTextEdit
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import QThread, Signal, Qt
from typing import Optional

# Modem bilgileri
MODEM_URL = "http://192.168.1.1"
USERNAME = "admin"
PASSWORD = "admin"

# GEREKLİ: pip install selenium
# Ayrica Chrome yüklü olmalı ve https://chromedriver.chromium.org/downloads adresinden uygun chromedriver.exe indirilip PATH'e eklenmeli veya script ile aynı klasöre konmalı.

# Başlatıcı ayarları (görünmez mod için)
chrome_options = Options()
chrome_options.add_argument('--headless')  # Artık başsız modda açar
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')

class ModemThread(QThread):
    status_update = Signal(str)

    def get_public_ip(self):
        try:
            ip = requests.get("https://api.ipify.org", timeout=5).text
            return ip
        except Exception:
            return None

    def check_internet(self):
        try:
            requests.get("https://www.google.com", timeout=5)
            return True
        except Exception:
            return False

    def run(self):
        try:
            self.status_update.emit("Eski IP alınıyor...")
            old_ip = self.get_public_ip()
            if old_ip:
                self.status_update.emit(f"Eski IP: {old_ip}")
            else:
                self.status_update.emit("Eski IP alınamadı!")

            self.status_update.emit("Giriş sayfası açılıyor...")
            browser = webdriver.Chrome(options=chrome_options)
            browser.get(MODEM_URL)
            time.sleep(2)

            self.status_update.emit("Giriş yapılıyor...")
            user_box = browser.find_element(By.NAME, "Frm_Username")
            pass_box = browser.find_element(By.NAME, "Frm_Password")
            user_box.clear()
            user_box.send_keys(USERNAME)
            pass_box.clear()
            pass_box.send_keys(PASSWORD)
            pass_box.send_keys(Keys.RETURN)
            time.sleep(3)

            self.status_update.emit("Yönetim ve Tanılama sekmesine geçiliyor...")
            mgr_and_diag_tab = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable((By.ID, "mgrAndDiag"))
            )
            mgr_and_diag_tab.click()
            time.sleep(1)

            self.status_update.emit("Sistem Yönetimi sekmesine geçiliyor...")
            dev_mgr_tab = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable((By.ID, "devMgr"))
            )
            dev_mgr_tab.click()

            self.status_update.emit("Yeniden Başlat butonuna tıklanıyor...")
            restart_btn = WebDriverWait(browser, 10).until(
                EC.visibility_of_element_located((By.ID, "Btn_restart"))
            )
            restart_btn.click()
            self.status_update.emit("Modem yeniden başlatılıyor!")
            try:
                ok_btn = WebDriverWait(browser, 5).until(
                    EC.element_to_be_clickable((By.ID, "confirmOK"))
                )
                ok_btn.click()
                self.status_update.emit("Onay penceresi: Tamam butonuna tıklandı.")
            except:
                self.status_update.emit("Onay penceresi çıkmadı veya buton bulunamadı.")
            browser.quit()

            # IP değişimini bekle
            self.status_update.emit("Yeni IP bekleniyor...")
            new_ip = None
            for i in range(60):  # 60 x 5sn = 5 dakika bekle
                time.sleep(5)
                ip = self.get_public_ip()
                if ip and ip != old_ip:
                    new_ip = ip
                    break
                self.status_update.emit(f"IP değişmedi, tekrar denenecek... ({i+1}/60)")
            if new_ip:
                self.status_update.emit(f"Yeni IP: {new_ip}")
            else:
                self.status_update.emit("Yeni IP alınamadı veya değişmedi!")

            # İnternet kontrolü
            self.status_update.emit("İnternet bağlantısı kontrol ediliyor...")
            if self.check_internet():
                self.status_update.emit("İnternet bağlantısı: VAR")
            else:
                self.status_update.emit("İnternet bağlantısı: YOK!")
            self.status_update.emit("İşlem tamamlandı!")
        except Exception as e:
            self.status_update.emit(f"Hata: {e}")

class ModemGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZTE:H3601P V9.0 [Yeniden Başlat!]")
        self.setGeometry(200, 200, 500, 450)
        layout = QVBoxLayout()
        # LOGO EKLEME
        self.logo_label = QLabel()
        pixmap = QPixmap(120, 120)
        pixmap.fill(Qt.GlobalColor.transparent)  # Arka planı şeffaf yap

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Arial", 40, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#1976D2"))  # Mavi renk
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "ZTE")
        painter.end()

        self.logo_label.setPixmap(pixmap)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWindowIcon(QPixmap(pixmap))
        layout.addWidget(self.logo_label)
        self.status_label = QLabel("Durum: Hazır")
        self.status_label.setMinimumHeight(30)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(200)
        self.start_btn = QPushButton("Başlat")
        self.close_btn = QPushButton("Kapat")
        layout.addWidget(self.status_label)
        layout.addWidget(self.log_box)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.close_btn)
        self.setLayout(layout)
        self.start_btn.clicked.connect(self.start_modem)
        self.close_btn.clicked.connect(self.close)
        self.thread: Optional[QThread] = None

    def start_modem(self):
        self.log_box.clear()
        self.status_label.setText("Durum: Başlatılıyor...")
        self.thread = ModemThread()
        self.thread.status_update.connect(self.update_status)
        self.thread.start()

    def update_status(self, msg):
        self.status_label.setText(f"Durum: {msg}")
        self.log_box.append(msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ModemGUI()
    gui.show()
    sys.exit(app.exec())
