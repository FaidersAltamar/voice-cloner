# Cómo publicar en GitHub

## 1. Crear el repositorio en GitHub

1. Entra en https://github.com/new
2. **Repository name**: `voice-cloner` (o el nombre que prefieras)
3. **Description**: "Clona tu voz con RVC - genera modelos .pth e .index"
4. Elige **Public**
5. **No** marques "Add a README" (ya tienes uno)
6. Clic en **Create repository**

## 2. Subir el código

En la terminal, desde la carpeta del proyecto:

```powershell
cd "c:\Users\faide\Downloads\voice-changer\voice-cloner"

# Añadir el repositorio remoto (sustituye TU_USUARIO por tu usuario de GitHub)
git remote add origin https://github.com/TU_USUARIO/voice-cloner.git

# Subir el código
git push -u origin main
```

Si tu rama se llama `master` en lugar de `main`:

```powershell
git branch -M main
git push -u origin main
```

## 3. Listo

Tu proyecto estará en: `https://github.com/TU_USUARIO/voice-cloner`
