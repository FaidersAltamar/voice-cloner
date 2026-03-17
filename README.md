# Voice Cloner

Sube muestras de audio (MP3 o WAV) y obtén tu modelo **.pth** + **.index** para [voice-changer](https://github.com/w-okada/voice-changer).

---

## Instalación (una vez)

```powershell
cd voice-cloner
powershell -ExecutionPolicy Bypass -File setup.ps1
```

---

## Ejecución

**Doble clic en `EJECUTAR_APP.bat`** o:

```powershell
python voice_cloner_app.py
```

O interfaz web:

```powershell
python app.py
```

Abre http://localhost:7860

---

## Uso

1. Añade archivos MP3 o WAV (10-30 min de voz recomendado)
2. Nombre del modelo, épocas (200-400) y dispositivo (GPU/CPU)
3. Clic en **Entrenar**
4. Espera 20-60 min (GPU) o más (CPU)
5. Los archivos .pth e .index se guardan en `output/`

---

## Requisitos

- Python 3.10+
- Git, FFmpeg
- GPU NVIDIA (recomendado, opcional)
