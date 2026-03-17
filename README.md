# Voice Cloner

Sube muestras de audio (MP3 o WAV) y obtén tu modelo **.pth** + **.index** para [voice-changer](https://github.com/w-okada/voice-changer).

---

## Instalación (una vez)

```powershell
cd voice-cloner
powershell -ExecutionPolicy Bypass -File setup.ps1
```

---

## Aplicación de escritorio (recomendada)

Ejecutable independiente, sin navegador.

```powershell
python voice_cloner_app.py
```

O doble clic en **`EJECUTAR_APP.bat`**

### Generar .exe (opcional, más adelante)

```powershell
pip install pyinstaller
pyinstaller voice_cloner_app.spec
```

El .exe estará en `dist/VoiceCloner.exe`. La carpeta `rvc-no-gui` debe estar junto al .exe.

---

## Interfaz web (alternativa)

```powershell
python app.py
```

Abre http://localhost:7860

---

## Uso

1. Añade archivos MP3 o WAV (10-30 min de voz recomendado)
2. Nombre del modelo y épocas (200-400)
3. Clic en **Entrenar**
4. Espera 20-60 min
5. Los archivos .pth e .index se guardan en la carpeta `output/`

---

## Requisitos

- Python 3.8+
- Git, FFmpeg
- GPU NVIDIA (recomendado)
