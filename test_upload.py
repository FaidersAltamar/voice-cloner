"""Test upload - run: python test_upload.py
   Asegurate de que app.py este corriendo en otra terminal."""
import sys

try:
    import requests
except ImportError:
    print("Instalando requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

url = "http://127.0.0.1:7860/upload"
file_path = r"c:\Users\faide\Downloads\1773696427421.mp3"

print(f"Subiendo {file_path} a {url}...")
try:
    with open(file_path, "rb") as f:
        r = requests.post(
            url,
            files={"files": ("1773696427421.mp3", f, "audio/mpeg")},
            data={"model_name": "mi_voz", "epochs": "200"},
            timeout=60,
        )
    print(f"Status: {r.status_code}")
    try:
        d = r.json()
        for k, v in d.items():
            print(f"  {k}: {v}")
    except:
        print(f"Response (raw): {r.text[:500]}")
except requests.exceptions.ConnectionError:
    print("ERROR: No se puede conectar. Inicia app.py en otra terminal.")
except Exception as e:
    print(f"ERROR: {e}")
