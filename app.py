"""
Voice Cloner - Web UI
Upload MP3 samples -> Get .pth + .index
"""
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB
app.config["UPLOAD_FOLDER"] = Path(__file__).parent / "uploads"
app.config["OUTPUT_FOLDER"] = Path(__file__).parent / "output"
app.config["RVC_DIR"] = Path(__file__).parent / "rvc-no-gui"

app.config["UPLOAD_FOLDER"].mkdir(exist_ok=True)
app.config["OUTPUT_FOLDER"].mkdir(exist_ok=True)

# Training status
training_status = {"running": False, "job_id": None, "progress": "", "error": None, "done": False}
training_lock = threading.Lock()


def convert_mp3_to_wav(mp3_path: Path, wav_dir: Path) -> list[Path]:
    """Convert MP3 to WAV (40kHz mono)."""
    try:
        from pydub import AudioSegment
    except ImportError:
        subprocess.run(["pip", "install", "pydub", "-q"], check=True)
        from pydub import AudioSegment

    wav_dir.mkdir(parents=True, exist_ok=True)
    wav_path = wav_dir / f"{mp3_path.stem}.wav"
    audio = AudioSegment.from_mp3(str(mp3_path))
    audio = audio.set_frame_rate(40000).set_channels(1)
    audio.export(str(wav_path), format="wav", bitrate="320k")
    return [wav_path]


def find_output_files(model_name: str) -> tuple[Path | None, Path | None]:
    """Find .pth and .index files for a model (rvc-no-gui structure)."""
    rvc = app.config["RVC_DIR"]
    # rvc-no-gui: RVC/assets/weights/model_name.pth, RVC/logs/model_name/
    weights_file = rvc / "RVC" / "assets" / "weights" / f"{model_name}.pth"
    logs_dir = rvc / "RVC" / "logs" / model_name

    pth_file = None
    index_file = None
    if weights_file.exists():
        pth_file = weights_file
    else:
        for f in (rvc / "RVC" / "logs").rglob("*.pth"):
            if model_name in str(f):
                pth_file = f
                break
    for f in (rvc / "RVC").rglob("*.index"):
        if model_name in str(f):
            index_file = f
            break
    return pth_file, index_file


def run_training(job_id: str, model_name: str, wav_files: list[Path], epochs: int):
    """Run RVC training in background."""
    global training_status
    rvc_dir = app.config["RVC_DIR"]
    pipeline = rvc_dir / "pipeline.py"

    with training_lock:
        training_status["running"] = True
        training_status["job_id"] = job_id
        training_status["progress"] = "Iniciando..."
        training_status["error"] = None
        training_status["done"] = False

    try:
        with training_lock:
            training_status["progress"] = "Entrenando modelo (puede tardar 20-60 min)..."
        audio_args = [str(f) for f in wav_files]
        cmd = ["python", str(pipeline), "train", "-m", model_name, "-a", *audio_args, "-e", str(epochs)]
        proc = subprocess.Popen(
            cmd,
            cwd=str(rvc_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:
            if "epoch" in line.lower() or "step" in line.lower():
                with training_lock:
                    training_status["progress"] = line.strip()[:80]

        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"Training failed with code {proc.returncode}")

        pth, idx = find_output_files(model_name)
        if pth:
            dest = app.config["OUTPUT_FOLDER"] / f"{model_name}_{job_id}.pth"
            shutil.copy(pth, dest)
        if idx:
            dest = app.config["OUTPUT_FOLDER"] / f"{model_name}_{job_id}.index"
            shutil.copy(idx, dest)

        with training_lock:
            training_status["running"] = False
            training_status["progress"] = "Completado"
            training_status["done"] = True
    except Exception as e:
        with training_lock:
            training_status["running"] = False
            training_status["error"] = str(e)
            training_status["progress"] = f"Error: {e}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon():
    return "", 204  # No content, evita 404

@app.route("/upload", methods=["POST"])
def upload():
    try:
        keys = list(request.files.keys())
        files = []
        for key in keys:
            for f in request.files.getlist(key):
                if f and getattr(f, "filename", None) and str(f.filename or "").strip():
                    files.append(f)
        if not files:
            print(f"[upload] 400 - No files. Keys received: {keys}")
            return jsonify({
                "error": f"No se enviaron archivos. Claves recibidas: {keys}. Arrastra o selecciona MP3/WAV.",
                "keys": keys,
            }), 400

        job_id = str(uuid.uuid4())[:8]
        job_dir = app.config["UPLOAD_FOLDER"] / job_id
        job_dir.mkdir(exist_ok=True)
        wav_dir = job_dir / "wav"
        wav_dir.mkdir(exist_ok=True)
        wav_files = []
        model_name = request.form.get("model_name", "my_voice").strip() or "my_voice"
        epochs = int(request.form.get("epochs", 200))

        for f in files:
            if not f or not f.filename:
                continue
            if f.filename.lower().endswith(".mp3"):
                path = job_dir / f.filename
                f.save(str(path))
                try:
                    wavs = convert_mp3_to_wav(path, wav_dir)
                    wav_files.extend(wavs)
                except Exception as e:
                    return jsonify({"error": f"Error convirtiendo {f.filename}: {e}"}), 400
            elif f.filename.lower().endswith(".wav"):
                path = wav_dir / f.filename
                f.save(str(path))
                wav_files.append(path)
            else:
                return jsonify({"error": f"Formato no soportado: {f.filename}. Use MP3 o WAV."}), 400

        if not wav_files:
            return jsonify({"error": "No se encontraron archivos MP3 o WAV válidos"}), 400

        rvc_dir = Path(__file__).resolve().parent / "rvc-no-gui"
        rvc_path = rvc_dir / "pipeline.py"
        if not rvc_path.exists():
            print(f"[upload] 400 - RVC no encontrado en {rvc_path}")
            return jsonify({
                "error": f"RVC no instalado. Buscado en: {rvc_path}",
                "instruccion": "Ejecuta: cd voice-cloner && powershell -ExecutionPolicy Bypass -File setup.ps1"
            }), 400
        app.config["RVC_DIR"] = rvc_dir

        thread = threading.Thread(
            target=run_training,
            args=(job_id, model_name, wav_files, epochs),
        )
        thread.daemon = True
        thread.start()

        return jsonify({"job_id": job_id, "model_name": model_name, "message": "Entrenamiento iniciado"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/status")
def status():
    with training_lock:
        return jsonify(dict(training_status))


@app.route("/download/<job_id>/<filename>")
def download(job_id, filename):
    path = app.config["OUTPUT_FOLDER"] / filename
    if not path.exists():
        return "File not found", 404
    return send_file(path, as_attachment=True, download_name=filename)


@app.route("/outputs/<job_id>")
def outputs(job_id):
    """List output files for a job."""
    out = app.config["OUTPUT_FOLDER"]
    files = []
    for f in out.glob(f"*_{job_id}.*"):
        files.append(f.name)
    return jsonify({"files": files})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, debug=False)
