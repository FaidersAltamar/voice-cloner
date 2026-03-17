"""
Voice Cloner - Aplicación de escritorio independiente
Sube muestras MP3/WAV -> Obtén .pth + .index
Ejecutar: python voice_cloner_app.py
Para .exe más adelante: pyinstaller voice_cloner_app.spec
"""
import os
import re
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:
    print("tkinter no disponible. Instala Python con tkinter.")
    exit(1)

# Rutas base (compatible con PyInstaller .exe)
import sys
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
RVC_DIR = BASE_DIR / "rvc-no-gui"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def convert_mp3_to_wav(mp3_path: Path, wav_dir: Path) -> Path:
    """Convierte MP3 a WAV (40kHz mono)."""
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
    return wav_path


def find_output_files(model_name: str) -> tuple[Path | None, Path | None]:
    """Busca .pth e .index del modelo."""
    rvc_base = RVC_DIR / "RVC"
    logs_model = rvc_base / "logs" / model_name
    weights_dir = rvc_base / "assets" / "weights"

    # 1. .pth: assets/weights (formato final)
    pth_file = (weights_dir / f"{model_name}.pth") if (weights_dir / f"{model_name}.pth").exists() else None
    # 2. Fallback: G_2333333.pth en logs
    if not pth_file and logs_model.exists():
        g_final = logs_model / "G_2333333.pth"
        if g_final.exists():
            pth_file = g_final
    # 3. Fallback: último G_*.pth por número de época
    if not pth_file and logs_model.exists():
        g_files = list(logs_model.glob("G_*.pth"))
        if g_files:
            def _epoch_num(p: Path) -> int:
                try:
                    return int(p.stem.split("_")[1])
                except (IndexError, ValueError):
                    return 0
            pth_file = max(g_files, key=_epoch_num)
    # 4. Fallback: buscar en todo RVC (por si la estructura cambió)
    if not pth_file and rvc_base.exists():
        candidates = [f for f in rvc_base.rglob("G_*.pth") if model_name in str(f)]
        if candidates:
            def _epoch_num(p: Path) -> int:
                try:
                    return int(p.stem.split("_")[1])
                except (IndexError, ValueError):
                    return 0
            pth_file = max(candidates, key=_epoch_num)

    # .index: preferir added_* sobre trained_* (added es el que usa inference)
    index_file = None
    added, trained, other = [], [], []
    for f in rvc_base.rglob("*.index"):
        if model_name not in str(f):
            continue
        if "added_" in f.name:
            added.append(f)
        elif "trained_" in f.name:
            trained.append(f)
        else:
            other.append(f)
    index_file = added[0] if added else (trained[0] if trained else (other[0] if other else None))
    return pth_file, index_file


def _parse_progress(line: str, total_epochs: int) -> tuple[int | None, str | None]:
    """Parsea la salida y devuelve (porcentaje, etapa) o (None, None)."""
    line_lower = line.lower()
    # Etapas iniciales
    if "step 1" in line_lower and "setting up" in line_lower:
        return 5, "Configurando RVC..."
    if "step 2" in line_lower and "preparing" in line_lower:
        return 10, "Preparando dataset..."
    if "preprocessing" in line_lower or "preprocess" in line_lower:
        return 20, "Preprocesando audio..."
    if "extracting f0" in line_lower or "f0 extraction" in line_lower:
        return 30, "Extrayendo F0 (tono)..."
    if "f0 extraction completed" in line_lower:
        return 40, "F0 completado"
    if "extracting features" in line_lower:
        return 45, "Extrayendo features..."
    if "feature extraction completed" in line_lower or "all-feature-done" in line_lower:
        return 52, "Features completados"
    if "training faiss" in line_lower or "training index" in line_lower:
        return 55, "Entrenando índice FAISS..."
    if "dataset preparation completed" in line_lower or "index saved" in line_lower:
        return 60, "Dataset listo"
    if "step 3" in line_lower and "training" in line_lower:
        return 65, "Entrenando modelo..."
    # Progreso por época: "Train Epoch: 1 [25%]"
    m = re.search(r"Train Epoch:\s*(\d+)\s*\[(\d+)%\]", line, re.I)
    if m:
        epoch_num = int(m.group(1))
        batch_pct = int(m.group(2))
        # 65-100% para el entrenamiento
        train_progress = (epoch_num - 1 + batch_pct / 100) / max(1, total_epochs)
        pct = int(65 + 35 * min(1.0, train_progress))
        return pct, f"Época {epoch_num}/{total_epochs} ({batch_pct}%)"
    if "====> Epoch:" in line:
        m2 = re.search(r"Epoch:\s*(\d+)", line)
        if m2:
            ep = int(m2.group(1))
            pct = int(65 + 35 * ep / max(1, total_epochs))
            return min(pct, 99), f"Época {ep}/{total_epochs} completada"
    if "training is done" in line_lower or "saving final" in line_lower:
        return 100, "¡Completado!"
    return None, None


def run_training(model_name: str, wav_files: list[Path], epochs: int, use_gpu: bool | None, on_progress, on_progress_bar, on_done, on_error):
    """Ejecuta entrenamiento en segundo plano. use_gpu: True=GPU, False=CPU, None=auto.
    on_progress(msg), on_progress_bar(percent, stage)"""
    pipeline = RVC_DIR / "pipeline.py"
    if not pipeline.exists():
        on_error(f"RVC no instalado. Ejecuta setup.ps1")
        return

    job_id = str(uuid.uuid4())[:8]
    output_files = []
    device = "gpu" if use_gpu is True else ("cpu" if use_gpu is False else "auto")

    def _run():
        try:
            on_progress("Iniciando entrenamiento...")
            on_progress_bar(0, "Iniciando...")
            cmd = ["python", str(pipeline), "train", "-m", model_name, "-a"] + [str(f) for f in wav_files] + ["-e", str(epochs), "-d", device]
            proc = subprocess.Popen(cmd, cwd=str(RVC_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                if line.strip():
                    on_progress(line.strip()[:120])
                    pct, stage = _parse_progress(line.strip(), epochs)
                    if pct is not None and stage is not None:
                        on_progress_bar(pct, stage)
            proc.wait()
            # RVC train.py usa os._exit(2333333) al completar; no es error
            if proc.returncode != 0 and proc.returncode != 2333333:
                on_error(f"Entrenamiento falló (código {proc.returncode})")
                return
            pth, idx = find_output_files(model_name)
            # Si hay .index pero no .pth, intentar convertir checkpoint (savee puede haber fallado)
            if idx and not pth:
                on_progress("Convirtiendo checkpoint a .pth...")
                subprocess.run(
                    ["python", str(pipeline), "ensure-weights", "-m", model_name],
                    cwd=str(RVC_DIR), capture_output=True, timeout=60
                )
                pth, idx = find_output_files(model_name)
            if pth:
                dest = OUTPUT_DIR / f"{model_name}_{job_id}.pth"
                shutil.copy(pth, dest)
                output_files.append(dest)
            if idx:
                dest = OUTPUT_DIR / f"{model_name}_{job_id}.index"
                shutil.copy(idx, dest)
                output_files.append(dest)
            on_done(output_files)
        except Exception as e:
            on_error(str(e))

    threading.Thread(target=_run, daemon=True).start()


class VoiceClonerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Voice Cloner")
        self.root.geometry("520x480")
        self.root.minsize(400, 400)

        self.files: list[Path] = []
        self.output_files: list[Path] = []

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # Archivos
        ttk.Label(main, text="Archivos de audio (MP3 o WAV):").pack(anchor=tk.W)
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(btn_frame, text="Añadir archivos...", command=self._add_files).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Limpiar", command=self._clear_files).pack(side=tk.LEFT)

        self.file_listbox = tk.Listbox(main, height=6, selectmode=tk.EXTENDED)
        self.file_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Opciones
        opt_frame = ttk.Frame(main)
        opt_frame.pack(fill=tk.X, pady=4)
        ttk.Label(opt_frame, text="Nombre modelo:").pack(side=tk.LEFT, padx=4)
        self.model_var = tk.StringVar(value="mi_voz")
        ttk.Entry(opt_frame, textvariable=self.model_var, width=15).pack(side=tk.LEFT, padx=12)
        ttk.Label(opt_frame, text="Épocas:").pack(side=tk.LEFT, padx=4)
        self.epochs_var = tk.StringVar(value="200")
        ttk.Entry(opt_frame, textvariable=self.epochs_var, width=6).pack(side=tk.LEFT)

        # Dispositivo (GPU/CPU)
        opt2 = ttk.Frame(main)
        opt2.pack(fill=tk.X, pady=4)
        ttk.Label(opt2, text="Dispositivo:").pack(side=tk.LEFT, padx=4)
        self.device_var = tk.StringVar(value="auto")
        device_combo = ttk.Combobox(opt2, textvariable=self.device_var, width=12, state="readonly")
        device_combo["values"] = ("auto", "gpu", "cpu")
        device_combo.pack(side=tk.LEFT, padx=4)
        ttk.Label(opt2, text="(auto=GPU si hay NVIDIA)").pack(side=tk.LEFT)

        # Botón entrenar
        self.train_btn = ttk.Button(main, text="Entrenar y generar .pth + .index", command=self._start_training)
        self.train_btn.pack(fill=tk.X, pady=8)

        # Barra de progreso
        prog_frame = ttk.Frame(main)
        prog_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(prog_frame, text="Progreso:").pack(anchor=tk.W)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(prog_frame, variable=self.progress_var, maximum=100, length=300)
        self.progress_bar.pack(fill=tk.X, pady=(2, 2))
        self.stage_var = tk.StringVar(value="")
        ttk.Label(prog_frame, textvariable=self.stage_var, foreground="gray").pack(anchor=tk.W)

        # Log / Estado
        ttk.Label(main, text="Estado:").pack(anchor=tk.W)
        self.progress_text = tk.Text(main, height=6, state=tk.DISABLED, wrap=tk.WORD)
        self.progress_text.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Botones resultado
        self.result_frame = ttk.Frame(main)
        self.result_frame.pack(fill=tk.X)

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar archivos",
            filetypes=[("Audio", "*.mp3 *.wav"), ("MP3", "*.mp3"), ("WAV", "*.wav"), ("Todos", "*.*")]
        )
        for p in paths:
            if p.lower().endswith((".mp3", ".wav")):
                self.files.append(Path(p))
                self.file_listbox.insert(tk.END, Path(p).name)

    def _clear_files(self):
        self.files.clear()
        self.file_listbox.delete(0, tk.END)

    def _log(self, msg: str):
        self.progress_text.config(state=tk.NORMAL)
        self.progress_text.insert(tk.END, msg + "\n")
        self.progress_text.see(tk.END)
        self.progress_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def _update_progress(self, percent: float, stage: str):
        self.progress_var.set(percent)
        self.stage_var.set(stage)
        self.root.update_idletasks()

    def _start_training(self):
        if not self.files:
            messagebox.showwarning("Aviso", "Añade al menos un archivo MP3 o WAV.")
            return
        model_name = self.model_var.get().strip() or "mi_voz"
        try:
            epochs = int(self.epochs_var.get())
        except ValueError:
            epochs = 200

        pipeline = RVC_DIR / "pipeline.py"
        if not pipeline.exists():
            messagebox.showerror("Error", f"RVC no instalado.\n\nEjecuta:\npowershell -ExecutionPolicy Bypass -File setup.ps1")
            return

        self.train_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.stage_var.set("")
        self.progress_text.config(state=tk.NORMAL)
        self.progress_text.delete(1.0, tk.END)
        self.progress_text.config(state=tk.DISABLED)

        job_dir = UPLOAD_DIR / str(uuid.uuid4())[:8]
        job_dir.mkdir(exist_ok=True)
        wav_dir = job_dir / "wav"
        wav_dir.mkdir(exist_ok=True)
        wav_files = []

        def do_convert():
            for f in self.files:
                if f.suffix.lower() == ".mp3":
                    try:
                        wav_files.append(convert_mp3_to_wav(f, wav_dir))
                    except Exception as e:
                        self.root.after(0, lambda: self._on_error(str(e)))
                        return
                else:
                    dest = wav_dir / f.name
                    shutil.copy(f, dest)
                    wav_files.append(dest)
            dev = self.device_var.get()
            use_gpu = {"auto": None, "gpu": True, "cpu": False}.get(dev, None)
            run_training(
                model_name, wav_files, epochs, use_gpu,
                on_progress=lambda m: self.root.after(0, lambda: self._log(m)),
                on_progress_bar=lambda p, s: self.root.after(0, lambda pp=p, ss=s: self._update_progress(pp, ss)),
                on_done=lambda files: self.root.after(0, lambda: self._on_done(files)),
                on_error=lambda e: self.root.after(0, lambda: self._on_error(e)),
            )

        threading.Thread(target=do_convert, daemon=True).start()

    def _on_done(self, files: list):
        self.train_btn.config(state=tk.NORMAL)
        self.progress_var.set(100)
        self.stage_var.set("¡Completado!")
        self.output_files = files
        self._log("\n¡Completado!")
        for f in files:
            self._log(f"  → {f}")
        self._log("\nArchivos guardados en: " + str(OUTPUT_DIR))
        names = [f.name for f in files]
        has_pth = any(f.suffix.lower() == ".pth" for f in files)
        msg = f"Modelo generado.\n\nArchivos en:\n{OUTPUT_DIR}\n\n" + "\n".join(names)
        if not has_pth and files:
            msg += "\n\n⚠ Falta el .pth (pesos del modelo). Revisa rvc-no-gui/RVC/logs/" + self.model_var.get().strip() + "/"
        messagebox.showinfo("Listo", msg)
        # Abrir carpeta (Windows)
        if files:
            try:
                os.startfile(OUTPUT_DIR)
            except Exception:
                pass

    def _on_error(self, msg: str):
        self.train_btn.config(state=tk.NORMAL)
        self.stage_var.set("Error")
        self._log(f"\nError: {msg}")
        messagebox.showerror("Error", msg)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    VoiceClonerApp().run()
