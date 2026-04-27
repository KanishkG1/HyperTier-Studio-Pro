import duckdb
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
        temp_path = None
        con = None
        try:
            path = self.config['file_path']
            if path.endswith('.obb'):
                self.status.emit("OBB Streaming...")
                temp_path, msg = OBBHandler.handle_obb(path)
                if not temp_path: self.error.emit(msg); return
                path = temp_path
            
            # Create temp dir for DuckDB to prevent crashes
            temp_dir = os.path.join(os.getcwd(), "duckdb_tmp")
            if not os.path.exists(temp_dir): os.makedirs(temp_dir, exist_ok=True)

            con = duckdb.connect(database=':memory:')
            con.execute(f"SET temp_directory='{temp_dir}'")
            
            res = con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{path}', all_varchar=True) LIMIT 0").fetchall()
            cols = [c[0] for c in res]
            col = self.config['column'] if self.config['column'] in cols else cols[0]
            op, val = self.config['operator'], self.config['value']
            query = f"SELECT * FROM read_csv_auto('{path}', all_varchar=True) WHERE {col} {op} '{val}'"
            
            self.status.emit("Vector Scanning...")
            start_time = time.perf_counter()
            out_name = f"output_{datetime.now().strftime('%H%M%S')}.csv"
            out_path = os.path.join(os.getcwd(), out_name)
            
            con.execute(f"COPY ({query}) TO '{out_path}' (HEADER, DELIMITER ',')")
            
            duration = time.perf_counter() - start_time
            size = os.path.getsize(path) / (1024*1024)
            rows = con.execute(f"SELECT count(*) FROM read_csv_auto('{path}', all_varchar=True) WHERE {col} {op} '{val}'").fetchone()[0]
            
            self.finished.emit({"duration": duration, "throughput": size/duration if duration>0 else 0, "rows": rows, "output_file": out_name})
        except Exception as e: 
            self.error.emit(f"Engine Error: {str(e)}")
        finally:
            if con: con.close()
            if temp_path and os.path.exists(temp_path): 
                try: os.remove(temp_path)
                except: pass

    # THIS IS THE MISSING METHOD THAT WAS CAUSING THE ERROR
    def convert_to_parquet(self, csv_path):
        """Converts a CSV file to Parquet for high-performance reading."""
        try:
            con = duckdb.connect(database=':memory:')
            # Create the output path by replacing .csv with .parquet
            parquet_path = csv_path.replace('.csv', '.parquet')
            
            # High-performance copy command
            con.execute(f"COPY (SELECT * FROM read_csv_auto('{csv_path}', all_varchar=True)) TO '{parquet_path}' (FORMAT PARQUET)")
            con.close()
            return parquet_path
        except Exception as e:
            return f"Error: {str(e)}"
