import zipfile
import tempfile
import os

class OBBHandler:
    @staticmethod
    def handle_obb(path):
        try:
            with zipfile.ZipFile(path, 'r') as z:
                cs = [f for f in z.namelist() if f.endswith('.csv')]
                if not cs: return None, "No CSV found in OBB"
                t = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
                with z.open(cs[0]) as s, open(t.name, 'wb') as target:
                    target.write(s.read())
                return t.name, cs[0]
        except Exception as e: return None, str(e)
