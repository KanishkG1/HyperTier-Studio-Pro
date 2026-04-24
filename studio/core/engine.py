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
            
            # --- 1. OBB HANDLING ---
            if path.endswith('.obb'):
                self.status.emit("OBB Streaming...")
                temp_path, msg = OBBHandler.handle_obb(path)
                if not temp_path: 
                    self.error.emit(msg)
                    return
                path = temp_path
            
            # --- 2. PERFORMANCE DIRECTORIES ---
            # Create a local temp folder for high-speed disk spilling
            temp_dir = os.path.join(os.getcwd(), "duckdb_cache")
            if not os.path.exists(temp_dir): 
                os.makedirs(temp_dir, exist_ok=True)

            # --- 3. DUCKDB INITIALIZATION ---
            con = duckdb.connect(database=':memory:')
            
            # Optimization Settings for 10M+ rows
            con.execute(f"SET temp_directory='{temp_dir}'")
            con.execute("SET memory_limit='4GB'") # Limits RAM usage to prevent system crash
            con.execute("SET preserve_insertion_order=false") # Speed boost for parallel reads
            con.execute("SET parallel_threads=8") # Utilize multi-core CPUs

            # --- 4. SCHEMA SNIFFING ---
            res = con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{path}', all_varchar=True) LIMIT 0").fetchall()
            cols = [c[0] for c in res]
            
            # Validate target column
            col = self.config.get('column')
            if not col or col not in cols:
                col = cols[0]
                
            op = self.config.get('operator', '=')
            val = self.config.get('value', '')
            
            # --- 5. VECTORIZED QUERY EXECUTION ---
            query = f"SELECT * FROM read_csv_auto('{path}', all_varchar=True) WHERE {col} {op} '{val}'"
            
            self.status.emit("Vector Scanning 12.7M Rows...")
            start_time = time.perf_counter()
            
            out_name = f"output_{datetime.now().strftime('%H%M%S')}.csv"
            out_path = os.path.join(os.getcwd(), out_name)
            
            # High-speed COPY directly to CSV
            con.execute(f"COPY ({query}) TO '{out_path}' (HEADER, DELIMITER ',')")
            
            duration = time.perf_counter() - start_time
            size_mb = os.path.getsize(path) / (1024 * 1024)
            
            # Fast count for the final report
            rows = con.execute(f"SELECT count(*) FROM read_csv_auto('{path}', all_varchar=True) WHERE {col} {op} '{val}'").fetchone()[0]
            
            # Return metrics to GUI
            self.finished.emit({
                "duration": duration, 
                "throughput": size_mb / duration if duration > 0 else 0, 
                "rows": rows, 
                "output_file": out_name
            })

        except Exception as e: 
            self.error.emit(f"Engine Failure: {str(e)}")
        finally:
            if con: 
                con.close()
            # Clean up temporary OBB CSV if it was created
            if temp_path and os.path.exists(temp_path): 
                try:
                    os.remove(temp_path)
                except:
                    pass

    def convert_to_parquet(self, csv_path):
        """Industrial grade CSV to Parquet conversion."""
        try:
            con = duckdb.connect(database=':memory:')
            parquet_path = csv_path.replace('.csv', '.parquet')
            # Using ZSTD compression for best balance of speed and size
            con.execute(f"COPY (SELECT * FROM read_csv_auto('{csv_path}', all_varchar=True)) TO '{parquet_path}' (FORMAT PARQUET, COMPRESSION 'ZSTD')")
            con.close()
            return parquet_path
        except Exception as e:
            return f"Error: {str(e)}"