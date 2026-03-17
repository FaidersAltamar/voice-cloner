"""
Voice Cloner - Aplicación de escritorio independiente
Sube muestras MP3/WAV -> Obtén .pth + .index
Ejecutar: python voice_cloner_app.py
Para .exe más adelante: pyinstaller voice_cloner_app.spec
"""
import os
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
    weights_file = RVC_DIR / "RVC" / "assets" / "weights" / f"{model_name}.pth"
    pth_file = weights_file if weights_file.exists() else None
    if not pth_file:
        for f in (RVC_DIR / "RVC" / "logs").rglob("*.pth"):
            if model_name in str(f):
                pth_file = f
                break
    index_file = None
    for f in (RVC_DIR / "RVC").rglob("*.index"):
        if model_name in str(f):
            index_file = f
            break
    return pth_file, index_file


def run_training(model_name: str, wav_files: list[Path], epochs: int, on_progress, on_done, on_error):
    """Ejecuta entrenamiento en segundo plano."""
    pipeline = RVC_DIR / "pipeline.py"
    if not pipeline.exists():
        on_error(f"RVC no instalado. Ejecuta setup.ps1")
        return

    job_id = str(uuid.uuid4())[:8]
    output_files = []

    def _run():
        try:
            on_progress("Entrenando (20-60 min)...")
            cmd = ["python", str(pipeline), "train", "-m", model_name, "-a"] + [str(f) for f in wav_files] + ["-e", str(epochs)]
            proc = subprocess.Popen(cmd, cwd=str(RVC_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                if line.strip():
                    on_progress(line.strip()[:100])
            proc.wait()
            if proc.returncode != 0:
                on_error(f"Entrenamiento falló (código {proc.returncode})")
                return
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

        # Botón entrenar
        self.train_btn = ttk.Button(main, text="Entrenar y generar .pth + .index", command=self._start_training)
        self.train_btn.pack(fill=tk.X, pady=8)

        # Progreso
        ttk.Label(main, text="Estado:").pack(anchor=tk.W)
        self.progress_text = tk.Text(main, height=8, state=tk.DISABLED, wrap=tk.WORD)
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
            run_training(
                model_name, wav_files, epochs,
                on_progress=lambda m: self.root.after(0, lambda: self._log(m)),
                on_done=lambda files: self.root.after(0, lambda: self._on_done(files)),
                on_error=lambda e: self.root.after(0, lambda: self._on_error(e)),
            )

        threading.Thread(target=do_convert, daemon=True).start()

    def _on_done(self, files: list):
        self.train_btn.config(state=tk.NORMAL)
        self.output_files = files
        self._log("\n¡Completado!")
        for f in files:
            self._log(f"  → {f}")
        self._log("\nArchivos guardados en: " + str(OUTPUT_DIR))
        names = [f.name for f in files]
        messagebox.showinfo("Listo", f"Modelo generado.\n\nArchivos en:\n{OUTPUT_DIR}\n\n" + "\n".join(names))
        # Abrir carpeta (Windows)
        if files:
            try:
                os.startfile(OUTPUT_DIR)
            except Exception:
                pass

    def _on_error(self, msg: str):
        self.train_btn.config(state=tk.NORMAL)
        self._log(f"\nError: {msg}")
        messagebox.showerror("Error", msg)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    VoiceClonerApp().run()
