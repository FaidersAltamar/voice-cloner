# Voice Cloner

Sube muestras de audio (MP3 o WAV) y obtén tu modelo **.pth** + **.index** para [voice-changer](https://github.com/w-okada/voice-changer).

---

## Instalación y ejecución (todo en uno)

**Doble clic en `INSTALAR_Y_EJECUTAR.bat`**

Instala automáticamente Python, Git, FFmpeg (si faltan), dependencias y modelos RVC. La primera vez puede tardar 15-40 min.

**Si falla con "Microsoft Visual C++ 14.0 required"** (fairseq no pudo usar el wheel precompilado):
1. Ejecuta como **Administrador**: `INSTALAR_CPP_BUILD_TOOLS.bat`
2. Espera a que termine (5-15 min)
3. Abre una **nueva** terminal y vuelve a ejecutar `INSTALAR_Y_EJECUTAR.bat`

*Nota: En Windows con Python 3.11 se usa un wheel precompilado de fairseq; normalmente no se requiere C++ Build Tools.*

---

## Ejecución (si ya está instalado)

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
