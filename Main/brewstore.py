import sys
import json
import urllib.request
import subprocess
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QLabel, QLineEdit, 
                             QPushButton, QScrollArea, QFrame, QTextEdit)
from PyQt6.QtCore import Qt, QProcess, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics

CASK_API_URL = "https://formulae.brew.sh/api/cask.json"

def get_brew_path():
    paths = ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]
    for path in paths:
        if os.path.exists(path): return path
    return "brew"

BREW_PATH = get_brew_path()

class ApiLoader(QThread):
    finished = pyqtSignal(list, set)
    def run(self):
        all_apps, installed = [], set()
        try:
            inst_proc = subprocess.run([BREW_PATH, "list", "--cask"], capture_output=True, text=True)
            if inst_proc.returncode == 0:
                installed = set(inst_proc.stdout.split())
            with urllib.request.urlopen(CASK_API_URL) as url:
                all_apps = json.loads(url.read().decode())
        except: pass
        self.finished.emit(all_apps, installed)

class AppCard(QFrame):
    def __init__(self, app_data, action_callback, is_installed):
        super().__init__()
        self.token = app_data.get("token")
        self.names = app_data.get("name", ["Unknown"])
        
        raw_name = self.names[0]
        prefixes = ["Microsoft ", "Google ", "Adobe ", "Apple "]
        for p in prefixes:
            if raw_name.startswith(p) and len(raw_name) > len(p):
                raw_name = raw_name[len(p):]
        
        self.title_text = raw_name
        self.desc_text = app_data.get("desc") or "No description available."
        self.action_callback = action_callback
        self.process = None
        self.is_installed = is_installed
        
        self.setObjectName("appCard")
        self.setMinimumWidth(300) 
        self.setFixedHeight(280) 
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QHBoxLayout()
        self.title_label = QLabel(self.title_text)
        self.title_label.setObjectName("appTitle")
        self.adjust_font_to_fit(self.title_label, self.title_text, 180)
        
        pill = QLabel(f"id: {self.token}")
        pill.setObjectName("appPill")
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(pill)
        layout.addLayout(header)

        desc = QLabel(self.desc_text)
        desc.setObjectName("appDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setObjectName("progressConsole")
        self.console.setFixedHeight(70)
        self.console.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.console.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.console.hide()
        layout.addWidget(self.console)

        layout.addStretch()

        footer = QHBoxLayout()
        footer.addStretch()
        self.btn = QPushButton()
        self.btn.setObjectName("actionBtn")
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self.btn)
        layout.addLayout(footer)

        self.refresh_button_ui()

    def adjust_font_to_fit(self, label, text, max_width):
        font = QFont("SF Pro", 17)
        font.setBold(True)
        metrics = QFontMetrics(font)
        while metrics.horizontalAdvance(text) > max_width and font.pointSize() > 10:
            font.setPointSize(font.pointSize() - 1)
            metrics = QFontMetrics(font)
        label.setFont(font)

    def enterEvent(self, event):
        self.setStyleSheet("QFrame#appCard { background-color: #1c2029; border: 1px solid #3b82f6; }")
    def leaveEvent(self, event):
        self.setStyleSheet("QFrame#appCard { background-color: #161920; border: 1px solid #2d3139; }")

    def refresh_button_ui(self, busy=False):
        try: self.btn.clicked.disconnect()
        except: pass
        if busy:
            self.btn.setText("Cancel")
            self.btn.clicked.connect(self.cancel_task)
            self.btn.setStyleSheet("background-color: #374151; color: #f8fafc; border: 1px solid #4b5563; border-radius: 10px; padding: 8px 18px; font-weight: 700;")
        elif self.is_installed:
            self.btn.setText("Uninstall")
            self.btn.clicked.connect(lambda: self.action_callback(self.token, self, "uninstall"))
            self.btn.setStyleSheet("background-color: #ef4444; color: white; border-radius: 10px; padding: 8px 18px; font-weight: 700; border: none;")
        else:
            self.btn.setText("Install")
            self.btn.clicked.connect(lambda: self.action_callback(self.token, self, "install"))
            self.btn.setStyleSheet("background-color: #4f46e5; color: white; border-radius: 10px; padding: 8px 18px; font-weight: 700; border: none;")

    def cancel_task(self):
        if self.process:
            self.process.kill()
            self.console.append("\nAction Cancelled.")
            self.refresh_button_ui(busy=False)

class BrewStore(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BrewStore")
        self.resize(1200, 900)
        
        self.all_apps_data = []
        self.filtered_data = []
        self.installed_casks = set()
        self.loaded_count = 0
        self.page_size = 24
        self.current_filter = "all"
        
        self.initUI()
        self.applyStyles()
        
        self.loader = ApiLoader()
        self.loader.finished.connect(self.on_data_ready)
        self.loader.start()

    def initUI(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(30, 20, 30, 20)

        topbar = QHBoxLayout()
        title = QLabel("BrewStore")
        title.setObjectName("brandTitle")
        
        self.filter_container = QHBoxLayout()
        self.filter_container.setSpacing(10)
        
        self.btn_all = QPushButton("All")
        self.btn_inst = QPushButton("Installed")
        self.btn_uninst = QPushButton("Available")
        
        for btn, f_type in [(self.btn_all, "all"), (self.btn_inst, "installed"), (self.btn_uninst, "uninstalled")]:
            btn.setCheckable(True)
            btn.setObjectName("filterBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, t=f_type: self.set_filter(t))
            self.filter_container.addWidget(btn)
        
        self.btn_all.setChecked(True)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Connecting...")
        self.search_input.setObjectName("searchInput")
        self.search_input.setFixedWidth(250)
        self.search_input.textChanged.connect(self.run_filter_logic)

        topbar.addWidget(title)
        topbar.addStretch()
        topbar.addLayout(self.filter_container)
        topbar.addSpacing(20)
        topbar.addWidget(self.search_input)
        layout.addLayout(topbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("mainScroll")
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.verticalScrollBar().valueChanged.connect(self.handle_scroll)
        
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(25)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll.setWidget(self.grid_container)
        layout.addWidget(self.scroll)

    def set_filter(self, filter_type):
        self.current_filter = filter_type
        self.btn_all.setChecked(filter_type == "all")
        self.btn_inst.setChecked(filter_type == "installed")
        self.btn_uninst.setChecked(filter_type == "uninstalled")
        self.run_filter_logic()

    def run_filter_logic(self):
        query = self.search_input.text().lower().strip()
        scored_results = []
        for app in self.all_apps_data:
            token = app.get('token', '').lower()
            names = [n.lower() for n in app.get('name', [])]
            is_inst = token in self.installed_casks
            if self.current_filter == "installed" and not is_inst: continue
            if self.current_filter == "uninstalled" and is_inst: continue
            
            score = 0
            if not query:
                score = 1
            else:
                desc = (app.get('desc') or "").lower()
                if any(query == n for n in names) or query == token:
                    score = 10
                elif any(query in n for n in names) or query in token or query in token.replace("-", ""):
                    score = 5
                elif query in desc:
                    score = 1
            if score > 0:
                scored_results.append((score, app))
        
        scored_results.sort(key=lambda x: x[0], reverse=True)
        self.filtered_data = [item[1] for item in scored_results]
        self.refresh_grid()

    def on_data_ready(self, apps, installed):
        self.all_apps_data = apps
        self.filtered_data = apps
        self.installed_casks = installed
        self.search_input.setPlaceholderText(f"Search {len(apps)} apps...")
        self.run_filter_logic()

    def load_more_apps(self):
        if not self.filtered_data:
            return
            
        start = self.loaded_count
        end = min(start + self.page_size, len(self.filtered_data))
        available_width = self.scroll.width() - 80 
        cols = max(1, available_width // 350) 
        
        for c in range(cols):
            self.grid_layout.setColumnStretch(c, 1)

        for i in range(start, end):
            app = self.filtered_data[i]
            is_inst = app.get('token') in self.installed_casks
            card = AppCard(app, self.handle_action, is_inst)
            self.grid_layout.addWidget(card, i // cols, i % cols)
        self.loaded_count = end

    def resizeEvent(self, event):
        if self.all_apps_data: 
            self.refresh_grid()
        super().resizeEvent(event)

    def refresh_grid(self):
        for c in range(self.grid_layout.columnCount()):
            self.grid_layout.setColumnStretch(c, 0)
        
        # Proper cleanup to prevent cards becoming independent windows
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        self.loaded_count = 0
        self.load_more_apps()

    def handle_scroll(self, value):
        max_scroll = self.scroll.verticalScrollBar().maximum()
        if value > max_scroll * 0.85 and self.loaded_count < len(self.filtered_data):
            self.load_more_apps()

    def handle_action(self, token, card, action_type):
        card.refresh_button_ui(busy=True)
        card.console.show()
        card.console.clear()
        verb = "install" if action_type == "install" else "uninstall"
        process = QProcess(self)
        card.process = process
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(lambda: card.console.append(process.readAllStandardOutput().data().decode()))
        process.finished.connect(lambda: self.on_finish(token, card, process, action_type))
        process.start(BREW_PATH, [verb, "--cask", token])

    def on_finish(self, token, card, process, action_type):
        if process.exitStatus() == QProcess.ExitStatus.NormalExit and process.exitCode() == 0:
            card.is_installed = (action_type == "install")
            if card.is_installed: self.installed_casks.add(token)
            else: self.installed_casks.discard(token)
            card.console.append("\nSUCCESS")
        card.refresh_button_ui(busy=False)
        QTimer.singleShot(4000, card.console.hide)

    def applyStyles(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { 
                background-color: #0b0e14; color: #f8fafc; 
                font-family: "SF Pro", "Helvetica Neue", Arial, sans-serif; 
            }
            QLabel { background-color: transparent; border: none; }
            QLabel#brandTitle { font-size: 26px; font-weight: 800; color: white; }
            QLineEdit#searchInput { 
                background: #1a1d23; border: 1px solid #2d3139; border-radius: 10px; 
                padding: 10px; color: white; 
            }
            QPushButton#filterBtn {
                background-color: #1a1d23; border: 1px solid #2d3139; 
                border-radius: 8px; padding: 6px 14px; color: #94a3b8; font-weight: 600;
            }
            QPushButton#filterBtn:hover { border-color: #3b82f6; color: white; }
            QPushButton#filterBtn:checked { 
                background-color: #3b82f6; border-color: #3b82f6; color: white; 
            }
            QFrame#appCard { background-color: #161920; border: 1px solid #2d3139; border-radius: 20px; }
            QLabel#appTitle { font-size: 17px; font-weight: 700; color: white; background: transparent; }
            QLabel#appDesc { color: #94a3b8; font-size: 13px; line-height: 1.4; background: transparent; }
            QLabel#appPill { 
                background-color: #2d3139; color: #64748b; border-radius: 6px; 
                padding: 2px 8px; font-size: 10px; font-family: "Menlo"; 
            }
            QTextEdit#progressConsole { 
                background-color: #000; color: #4ade80; border-radius: 10px; 
                font-family: "Menlo"; font-size: 11px; border: none; 
            }
            QScrollArea { border: none; background: transparent; }
        """)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = BrewStore()
    win.show()
    sys.exit(app.exec())