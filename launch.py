import os
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
        print("Error: venv not found."); return
    ai_available = check_ollama()
    print(f"AI Status: {'Online' if ai_available else 'Offline'}")
    env = os.environ.copy()
    env["HYPER_AI_AVAILABLE"] = "True" if ai_available else "False"
    python_exe = os.path.join("venv", "Scripts", "python.exe")
    subprocess.run([python_exe, "main.py"], env=env)
if __name__ == "__main__":
    main()
