import os
import subprocess
import sys

# --- FILE CONTENTS ---

main_py = r'''import sys
from PyQt6.QtWidgets import QApplication
from studio.gui import HyperTierGUI
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Hyper-Tier Studio Pro")
    window = HyperTierGUI()
    window.show()
    sys.exit(app.exec())
'''

launch_py = r'''import os
import subprocess
import sys
import requests
def check_ollama():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get('models', [])
            for m in models:
                if 'phi3' in m.get('name', '').lower(): return True
        return False
    except: return False
def main():
    print("--- Hyper-Tier Studio Launcher ---")
    if not os.path.exists("venv"):
        print("Error: venv not found. Please run build_production.py first."); return
    ai_available = check_ollama()
    print(f"AI Status: {'Online (Phi-3)' if ai_available else 'Offline (Manual Mode Only)'}")
    env = os.environ.copy()
    env["HYPER_AI_AVAILABLE"] = "True" if ai_available else "False"
    
    python_exe = os.path.join("venv", "Scripts", "python.exe") if os.name == 'nt' else os.path.join("venv", "bin", "python")
    subprocess.run([python_exe, "main.py"], env=env)
if __name__ == "__main__":
    main()
'''

gui_py = r'''from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLineEdit, QComboBox, QLabel, QTableWidget, 
    QTableWidgetItem, QPlainTextEdit, QFileDialog, QFrame
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, QObject
from .core.engine import HyperEngine
from .utils.metrics import SystemMonitor
import duckdb
import os
import requests

class PreviewWorker(QObject):
    finished = pyqtSignal(list, list)
    error = pyqtSignal(str)
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
    def run(self):
        con = None
        try:
            con = duckdb.connect(database=':memory:')
            res = con.execute(f"SELECT * FROM read_csv_auto('{self.file_path}', all_varchar=True) LIMIT 100").fetchall()
            cols = con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{self.file_path}', all_varchar=True) LIMIT 0").fetchall()
            self.finished.emit([c[0] for c in cols], res)
        except Exception as e: self.error.emit(str(e))
        finally:
            if con: con.close()

class AIWorker(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, file_path, query):
        super().__init__()
        self.file_path = file_path
        self.query = query
    def run(self):
        con = None
        try:
            con = duckdb.connect(database=':memory:')
            res = con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{self.file_path}', all_varchar=True) LIMIT 0").fetchall()
            col_list = [c[0] for c in res]
            con.close()
            prompt = (f"DuckDB SQL Expert. Columns: {col_list}. User wants: {self.query}. "
                      f"Return ONLY the SQL query starting with 'SELECT * FROM read_csv_auto' using all_varchar=True. "
                      f"Limit 1000. No markdown, no explanation.")
            response = requests.post("http://localhost:11434/api/generate", 
                                     json={"model": "phi3:mini", "prompt": prompt, "stream": False},
                                     timeout=120)
            sql = response.json()['response'].strip().replace("```sql", "").replace("```", "").strip()
            self.finished.emit(sql)
        except Exception as e: self.error.emit(str(e))
        finally:
            if con: con.close()

class HyperTierGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hyper-Tier Studio | Pro Vector Edition")
        self.setMinimumSize(1200, 800)
        self.selected_file = None
        self.ai_available = os.environ.get("HYPER_AI_AVAILABLE", "False") == "True"
        self.init_ui()
        self.apply_styles()
        self.sys_timer = QTimer()
        self.sys_timer.timeout.connect(self.update_metrics)
        self.sys_timer.start(1000)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        left = QVBoxLayout()
        self.btn_load = QPushButton("📂 Open CSV / OBB")
        self.btn_load.clicked.connect(self.load_file)
        self.lbl_file = QLabel("No file selected")
        self.lbl_file.setStyleSheet("color:#7f8c8d; font-size:11px;")
        
        ai_frame = QFrame()
        ai_frame.setStyleSheet("background:#fdfdfd; border:1px solid #ddd; border-radius:8px;")
        ai_layout = QVBoxLayout(ai_frame)
        ai_layout.addWidget(QLabel("<b>AI DATA ASSISTANT</b>"))
        self.ai_input = QLineEdit()
        self.ai_input.setPlaceholderText("Find rows where...")
        self.btn_ai = QPushButton("⚡ Ask AI")
        self.btn_ai.clicked.connect(self.start_ai_query)
        ai_layout.addWidget(self.ai_input); ai_layout.addWidget(self.btn_ai)
        
        left.addWidget(self.btn_load); left.addWidget(self.lbl_file); left.addWidget(ai_frame)
        left.addWidget(QLabel("<b>VECTOR FILTER:</b>"))
        self.input_col = QLineEdit(); self.input_col.setPlaceholderText("Column")
        self.combo_op = QComboBox(); self.combo_op.addItems([">", "<", "=", "!=", "LIKE"])
        self.input_val = QLineEdit(); self.input_val.setPlaceholderText("Value")
        self.btn_run = QPushButton("🚀 Run Vector Process"); self.btn_run.setObjectName("runBtn")
        self.btn_run.clicked.connect(self.run_process)
        
        left.addWidget(self.input_col); left.addWidget(self.combo_op); left.addWidget(self.input_val); left.addWidget(self.btn_run)
        left.addWidget(QPushButton("Preview Data", clicked=self.start_preview))
        left.addWidget(QPushButton("Convert to Parquet", clicked=self.convert_to_parquet))
        left.addStretch()

        right = QVBoxLayout()
        kpi_l = QHBoxLayout()
        self.kpi_cpu = self.create_card("CPU Usage"); self.kpi_ram = self.create_card("RAM Usage"); self.kpi_speed = self.create_card("Throughput")
        kpi_l.addWidget(self.kpi_cpu); kpi_l.addWidget(self.kpi_ram); kpi_l.addWidget(self.kpi_speed)
        self.table = QTableWidget()
        self.lbl_status = QLabel("Engine Idle")
        self.log_win = QPlainTextEdit()
        self.log_win.setReadOnly(True)
        self.log_win.setStyleSheet("background:#1e1e1e; color:#00ff00; font-family:Consolas;")
        right.addLayout(kpi_l); right.addWidget(self.table); right.addWidget(self.lbl_status); right.addWidget(self.log_win)
        main.addLayout(left, 1); main.addLayout(right, 3)

    def create_card(self, title):
        f = QFrame(); f.setStyleSheet("background:white; border:1px solid #ddd; border-radius:8px;")
        l = QVBoxLayout(f)
        l.addWidget(QLabel(title, alignment=Qt.AlignmentFlag.AlignCenter))
        v = QLabel("0", alignment=Qt.AlignmentFlag.AlignCenter); v.setStyleSheet("font-weight:bold; font-size:16px;")
        l.addWidget(v); f.val_label = v
        return f

    def apply_styles(self):
        self.setStyleSheet("QMainWindow { background:#f5f6fa; } QPushButton { background:#2f3640; color:white; border-radius:5px; padding:10px; font-weight:bold; } QPushButton#runBtn { background:#e84118; }")

    def update_metrics(self):
        s = SystemMonitor.get_stats()
        self.kpi_cpu.val_label.setText(f"{s['cpu_sys']}%"); self.kpi_ram.val_label.setText(f"{s['ram']}%")

    def load_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open Data", "", "Data (*.csv *.parquet *.obb)")
        if p: self.selected_file = p; self.lbl_file.setText(os.path.basename(p))

    def start_ai_query(self):
        prompt = self.ai_input.text().strip()
        if not self.selected_file: self.log_win.appendPlainText("⚠️ Load file first."); return
        if not prompt: self.log_win.appendPlainText("⚠️ Enter AI prompt."); return
        self.lbl_status.setText("AI thinking...")
        self.ai_thread = QThread()
        self.ai_worker = AIWorker(self.selected_file, prompt)
        self.ai_worker.moveToThread(self.ai_thread)
        self.ai_thread.started.connect(self.ai_worker.run)
        self.ai_worker.finished.connect(self.execute_ai_query)
        self.ai_worker.error.connect(lambda e: self.log_win.appendPlainText(f"AI Error: {e}"))
        self.ai_worker.finished.connect(self.ai_thread.quit)
        self.ai_thread.start()

    def execute_ai_query(self, sql):
        con = duckdb.connect(database=':memory:')
        try:
            res = con.execute(f"{sql} LIMIT 100").fetchall()
            cols = [d[0] for d in con.description]
            self.update_table(cols, res)
            self.lbl_status.setText("AI Results Loaded")
        except Exception as e: self.log_win.appendPlainText(f"SQL Error: {e}")
        finally: con.close()

    def start_preview(self):
        if not self.selected_file: return
        self.lbl_status.setText("Previewing...")
        self.prev_thread = QThread()
        self.prev_worker = PreviewWorker(self.selected_file)
        self.prev_worker.moveToThread(self.prev_thread)
        self.prev_thread.started.connect(self.prev_worker.run)
        self.prev_worker.finished.connect(self.update_table)
        self.prev_worker.error.connect(lambda e: self.log_win.appendPlainText(e))
        self.prev_worker.finished.connect(self.prev_thread.quit)
        self.prev_thread.start()

    def update_table(self, cols, rows):
        self.table.setColumnCount(len(cols)); self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(rows))
        for r in range(len(rows)):
            for c in range(len(cols)): self.table.setItem(r, c, QTableWidgetItem(str(rows[r][c])))

    def run_process(self):
        if not self.selected_file: return
        self.btn_run.setEnabled(False)
        cfg = {'file_path': self.selected_file, 'column': self.input_col.text(), 'operator': self.combo_op.currentText(), 'value': self.input_val.text()}
        self.proc_thread = QThread()
        self.worker = HyperEngine(cfg)
        self.worker.moveToThread(self.proc_thread)
        self.proc_thread.started.connect(self.worker.run)
        self.worker.status.connect(self.lbl_status.setText)
        self.worker.finished.connect(self.on_done)
        self.worker.error.connect(self.log_win.appendPlainText)
        self.proc_thread.start()

    def on_done(self, res):
        self.btn_run.setEnabled(True)
        self.kpi_speed.val_label.setText(f"{res['throughput']:.2f} MB/s")
        self.log_win.appendPlainText(f"DONE: {res['rows']:,} rows saved to {res['output_file']} in {res['duration']:.2f}s")
        self.proc_thread.quit()

    def convert_to_parquet(self):
        if not self.selected_file: return
        self.lbl_status.setText("Converting...")
        e = HyperEngine({}); out = e.convert_to_parquet(self.selected_file)
        self.log_win.appendPlainText(f"Success: {out}")
        self.selected_file = out; self.lbl_file.setText(os.path.basename(out))
'''

engine_py = r'''import duckdb
import time
import os
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from .obb_handler import OBBHandler

class HyperEngine(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    def __init__(self, config):
        super().__init__()
        self.config = config
    def run(self):
        temp_path = None; con = None
        try:
            path = self.config['file_path']
            if path.endswith('.obb'):
                temp_path, msg = OBBHandler.handle_obb(path)
                if not temp_path: self.error.emit(msg); return
                path = temp_path
            
            temp_dir = os.path.join(os.getcwd(), "duckdb_cache")
            os.makedirs(temp_dir, exist_ok=True)

            con = duckdb.connect(database=':memory:')
            con.execute(f"SET temp_directory='{temp_dir}'")
            con.execute("SET memory_limit='6GB'") # Prevent OOM crashes
            con.execute("SET preserve_insertion_order=false")

            res = con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{path}', all_varchar=True) LIMIT 0").fetchall()
            cols = [c[0] for c in res]
            col = self.config.get('column') if self.config.get('column') in cols else cols[0]
            op, val = self.config['operator'], self.config['value']
            query = f"SELECT * FROM read_csv_auto('{path}', all_varchar=True) WHERE {col} {op} '{val}'"
            
            self.status.emit("Vector Scanning...")
            start_time = time.perf_counter()
            out_name = f"output_{datetime.now().strftime('%H%M%S')}.csv"
            con.execute(f"COPY ({query}) TO '{out_name}' (HEADER, DELIMITER ',')")
            
            duration = time.perf_counter() - start_time
            size = os.path.getsize(path) / (1024*1024)
            rows = con.execute(f"SELECT count(*) FROM read_csv_auto('{path}', all_varchar=True) WHERE {col} {op} '{val}'").fetchone()[0]
            self.finished.emit({"duration": duration, "throughput": size/duration if duration>0 else 0, "rows": rows, "output_file": out_name})
        except Exception as e: self.error.emit(f"Engine Error: {str(e)}")
        finally:
            if con: con.close()
            if temp_path and os.path.exists(temp_path): os.remove(temp_path)

    def convert_to_parquet(self, csv_path):
        try:
            con = duckdb.connect(database=':memory:')
            parquet_path = csv_path.replace('.csv', '.parquet')
            con.execute(f"COPY (SELECT * FROM read_csv_auto('{csv_path}', all_varchar=True)) TO '{parquet_path}' (FORMAT PARQUET)")
            con.close()
            return parquet_path
        except Exception as e: return f"Error: {str(e)}"
'''

obb_py = r'''import zipfile
import tempfile
import os
class OBBHandler:
    @staticmethod
    def handle_obb(path):
        try:
            with zipfile.ZipFile(path, 'r') as z:
                cs = [f for f in z.namelist() if f.endswith('.csv')]
                if not cs: return None, "No CSV found"
                t = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
                with z.open(cs[0]) as s, open(t.name, 'wb') as target: target.write(s.read())
                return t.name, cs[0]
        except Exception as e: return None, str(e)
'''

metrics_py = r'''import psutil
class SystemMonitor:
    @staticmethod
    def get_stats():
        return {"cpu_sys": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent}
'''

reqs = "pyqt6==6.7.0\nduckdb>=1.1.0\npsutil==5.9.8\nrequests==2.32.3"

# --- BUILD EXECUTION ---

def build():
    print("🏗️ Constructing Professional Build...")
    files = {
        "main.py": main_py, "launch.py": launch_py, "requirements.txt": reqs,
        "studio/__init__.py": "", "studio/gui.py": gui_py,
        "studio/core/__init__.py": "", "studio/core/engine.py": engine_py,
        "studio/core/obb_handler.py": obb_py, "studio/utils/__init__.py": "",
        "studio/utils/metrics.py": metrics_py,
    }
    for path, content in files.items():
        full_path = os.path.join(os.getcwd(), path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f: f.write(content)
        print(f"  ✅ Created: {path}")

    print("\n⚙️ Setting up Virtual Environment...")
    subprocess.run([sys.executable, "-m", "venv", "venv"])
    
    pip_exe = os.path.join(os.getcwd(), "venv", "Scripts", "pip.exe") if os.name == 'nt' else os.path.join(os.getcwd(), "venv", "bin", "pip")
    
    print("📦 Installing requirements (this may take a minute)...")
    subprocess.run([pip_exe, "install", "-r", "requirements.txt"], check=True)
    
    print("\n🚀 DONE! Run 'python launch.py' to start.")

if __name__ == "__main__":
    build()