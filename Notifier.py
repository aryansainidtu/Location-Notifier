import sys
import os
import sqlite3
import pywhatkit
import pyautogui
import time
import datetime
from PyQt5.QtWidgets import (
    QWidget, QApplication, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget, QSystemTrayIcon, 
    QMenu, QAction, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtPositioning import QGeoPositionInfoSource


class Notifier(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Location WhatsApp Notifier")
        self.setGeometry(300, 300, 600, 400)

        # --- Widgets ---
        self.label1 = QLabel("Whatsapp Number (+Country Code)")
        self.line1 = QLineEdit()
        self.label2 = QLabel("Destination Latitude")
        self.line2 = QLineEdit()
        self.label3 = QLabel("Destination Longitude")
        self.line3 = QLineEdit()
        self.label4 = QLabel("Frequency (Select Days or Once)")
        
        self.buttononce = QCheckBox("Once")
        self.days = {
            "Sunday": QCheckBox("Sunday"),
            "Monday": QCheckBox("Monday"),
            "Tuesday": QCheckBox("Tuesday"),
            "Wednesday": QCheckBox("Wednesday"),
            "Thursday": QCheckBox("Thursday"),
            "Friday": QCheckBox("Friday"),
            "Saturday": QCheckBox("Saturday")
        }

        self.label5 = QLabel("Custom Message (Optional)")
        self.line5 = QLineEdit()
        self.button1 = QPushButton("Save Reminder")
        self.button2 = QPushButton("Delete Reminder")
        self.list = QListWidget()

        # --- Database Setup (SQLite) ---
        try:
            # This creates 'reminders.db' automatically if it doesn't exist
            self.conn = sqlite3.connect("reminders.db")
            self.curs = self.conn.cursor()
            
            self.curs.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    whatsapp TEXT NOT NULL,
                    dest_lat REAL NOT NULL,
                    dest_long REAL NOT NULL,
                    message TEXT,
                    frequency TEXT DEFAULT 'Once',
                    last_sent TEXT DEFAULT NULL
                )
            """)
            self.conn.commit()
        except sqlite3.Error as err:
            QMessageBox.critical(self, "Database Error", f"Could not initialize SQLite database:\n{err}")
            sys.exit(1)

        self.insert = """INSERT INTO reminders (whatsapp, dest_lat, dest_long, message, frequency)
                         VALUES (?, ?, ?, ?, ?)"""
        self.load_reminders()

        # --- GPS Setup ---
        self.current = QGeoPositionInfoSource.createDefaultSource(self)
        if self.current:
            self.current.positionUpdated.connect(self.position)
            self.current.startUpdates()

        # --- Check Timer ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_location)
        self.timer.start(5000)

        # --- System Tray Integration ---
        self.tray_icon = QSystemTrayIcon(QIcon("icon.png"), self)
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        quit_action = QAction("Exit", self)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        show_action.triggered.connect(self.show_window)
        quit_action.triggered.connect(self.exit_app)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        self.initUI()

    def initUI(self):
        hbox = QHBoxLayout()
        hbox.addWidget(self.buttononce)
        for btn in self.days.values():
            hbox.addWidget(btn)

        vbox = QVBoxLayout()
        for widget in [self.label1, self.line1, self.label2, self.line2, self.label3,
                       self.line3, self.label4]:
            vbox.addWidget(widget)
        vbox.addLayout(hbox)
        for widget in [self.label5, self.line5, self.button1, self.button2, self.list]:
            vbox.addWidget(widget)

        self.setLayout(vbox)

        self.setStyleSheet("""
            QLabel, QPushButton { font-family: Calibri; margin: 0px; }
            QLabel { font-size: 16px; }
            QCheckBox { font-size: 14px; }
            QPushButton { font-size: 16px; background-color: #0078d7; color: white; border-radius:6px; padding:5px; }
            QPushButton:hover { background-color: #005a9e; }
            QLineEdit, QListWidget { font-size: 15px; }
        """)

        self.button1.clicked.connect(self.save)
        self.button2.clicked.connect(self.delete)

    def load_reminders(self):
        self.list.clear()
        get = "SELECT whatsapp, message, frequency FROM reminders"
        self.curs.execute(get)
        for w, m, f in self.curs.fetchall():
            self.list.addItem(f"{w} -> {m} -> ( {f} )")

    def save(self):
        whatsapp = self.line1.text().strip()
        if not whatsapp:
            QMessageBox.warning(self, "Error", "Please enter WhatsApp number.")
            return

        try:
            dlat = round(float(self.line2.text()), 2)
            dlong = round(float(self.line3.text()), 2)
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid latitude or longitude.")
            return

        message = self.line5.text().strip() or "Reached"
        frequency = self.get_selected_frequency()

        data = (whatsapp, dlat, dlong, message, frequency)
        self.curs.execute(self.insert, data)
        self.conn.commit()
        self.load_reminders()

    def get_selected_frequency(self):
        if self.buttononce.isChecked():
            return "Once"
        selected_days = [day for day, chk in self.days.items() if chk.isChecked()]
        return ",".join(selected_days) if selected_days else "Once"

    def delete(self):
        items = self.list.selectedItems()
        for item in items:
            whatsapp = item.text().split("->")[0].strip()
            delete_q = "DELETE FROM reminders WHERE whatsapp = ?"
            self.curs.execute(delete_q, (whatsapp,))
            self.conn.commit()
        self.load_reminders()

    def check_location(self):
        pass

    def position(self, info):
        coordinate = info.coordinate()
        clat = round(coordinate.latitude(), 2)
        clong = round(coordinate.longitude(), 2)
        current_day = datetime.datetime.now().strftime("%A")
        today = str(datetime.date.today())

        self.curs.execute("SELECT id, whatsapp, dest_lat, dest_long, message, frequency, last_sent FROM reminders")
        for rid, whatsapp, dlat, dlong, message, freq, last_sent in self.curs.fetchall():
            if round(dlat, 2) == clat and round(dlong, 2) == clong and str(last_sent) != today:
                if freq == "Once" or current_day in freq:
                    print(f"📍 Sending WhatsApp to {whatsapp} - {message}")
                    pywhatkit.sendwhatmsg_instantly(whatsapp, message, 10, True, 5)
                    time.sleep(10)
                    pyautogui.press("enter")

                    update = "UPDATE reminders SET last_sent = ? WHERE id = ?"
                    self.curs.execute(update, (today, rid))
                    self.conn.commit()

                    if freq == "Once":
                        delete_q = "DELETE FROM reminders WHERE id = ?"
                        self.curs.execute(delete_q, (rid,))
                        self.conn.commit()

    def show_window(self):
        self.showNormal()
        self.activateWindow()

    def exit_app(self):
        self.curs.close()
        self.conn.close()
        QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    notifier = Notifier()
    notifier.show()
    sys.exit(app.exec_())