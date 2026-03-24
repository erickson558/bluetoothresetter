# Bluetooth Resetter V0.0.3

Aplicación de escritorio y toolkit de automatización para Windows 10/11 que recupera el stack de audio y Bluetooth después de suspensión o hibernación, orientado al problema recurrente de reconexión con audífonos como `Soundcore Q45`.

## Análisis inicial

### Estado actual del proyecto
- El repositorio estaba vacío a nivel funcional.
- Solo existía el ícono `tools_bluetooth_serial_utility_13004.ico`.

### Qué se puede mejorar
- Crear un backend robusto en PowerShell para recuperar audio y Bluetooth sin reiniciar la PC.
- Añadir una GUI no bloqueante de un clic.
- Persistir configuración en `config.json`.
- Centralizar logs en `log.txt`.
- Preparar build a `.exe`, documentación, versionado y release automático.

### Riesgos y consideraciones
- Las operaciones PnP, reinicio de servicios y eliminación de endpoints requieren privilegios de administrador.
- Forzar el perfil `Stereo` frente a `Hands-Free` en Windows no tiene una API oficial simple y estable; esta solución lo aborda deshabilitando endpoints `Hands-Free` detectados para el dispositivo objetivo en modo best effort.
- Los nombres visibles del dispositivo pueden variar según driver, idioma o versión de Windows; por eso el script usa keywords configurables (`Soundcore`, `Q45`).

### Qué no debía tocarse
- El ícono existente se conserva y se reutiliza tanto en GUI como en el empaquetado.

## Plan de mejora aplicado
- Separación clara entre frontend y backend.
- Backend PowerShell tolerante a fallos y con logging con timestamp.
- GUI Python moderna con Tkinter, ejecución en background y menú `About`.
- Persistencia automática de preferencias en `config.json`.
- Internacionalización base `es/en` escalable.
- Empaquetado a `.exe` sin consola con PyInstaller.
- Base lista para Git, tags y GitHub Actions.

## Características
- Reinicia `audiosrv`.
- Reinicia `bthserv`.
- Finaliza y reactiva `audiodg.exe`.
- Reinicia el adaptador Bluetooth vía `Disable-PnpDevice` / `Enable-PnpDevice`.
- Limpia `AudioEndpoint` fantasma relacionados con el dispositivo objetivo.
- Intenta forzar el perfil `Stereo` deshabilitando endpoints `Hands-Free` detectados.
- Muestra logs en consola y en GUI.
- Guarda logs en `log.txt`.
- Guarda configuración automáticamente en `config.json`.
- Recuerda tamaño, posición, idioma y preferencias.
- GUI con `Auto iniciar`, `Autocerrar`, countdown visible, `Salir`, atajos y `About`.

## Estructura recomendada

```text
bluetoothresetter/
|-- .github/
|   `-- workflows/
|       `-- release.yml
|-- scripts/
|   `-- Fix-AudioBluetooth.ps1
|-- src/
|   `-- bluetooth_resetter/
|       |-- i18n/
|       |   `-- translations.py
|       |-- services/
|       |   |-- app_paths.py
|       |   |-- config_service.py
|       |   |-- logging_service.py
|       |   `-- powershell_runner.py
|       |-- ui/
|       |   `-- main_window.py
|       |-- __init__.py
|       |-- app.py
|       `-- version.py
|-- Fix-AudioBluetooth-Admin.bat
|-- CHANGELOG.md
|-- LICENSE
|-- README.md
|-- app.py
|-- build.ps1
|-- requirements.txt
`-- tools_bluetooth_serial_utility_13004.ico
```

## Uso rápido

### Opción 1: script PowerShell
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Fix-AudioBluetooth.ps1
```

### Opción 2: un clic como administrador
```bat
.\Fix-AudioBluetooth-Admin.bat
```

### Opción 3: GUI Python
```powershell
py app.py
```

La GUI intentará elevar privilegios automáticamente. Si compilas a `.exe`, el resultado quedará en la misma carpeta del proyecto como `BluetoothResetter.exe`.

## Configuración persistente

El archivo `config.json` se crea automáticamente junto al `.py` o `.exe` y guarda:
- tamaño y posición de la ventana
- idioma
- `auto_run`
- `auto_close`
- tiempo de autocierre

## Logging

El archivo `log.txt` se guarda junto a la aplicación y usa formato:

```text
[YYYY-MM-DD HH:MM:SS] [LEVEL] Mensaje
```

## Seguridad
- No se hardcodean credenciales.
- Se validan entradas configurables básicas.
- Los errores se registran sin exponer secretos.
- La GUI mantiene las operaciones sensibles en un backend separado.
- Las acciones administrativas se ejecutan solo cuando son necesarias.

## Compilar a .exe

### Instalar dependencias de build
```powershell
py -m pip install -r requirements.txt
```

### Generar ejecutable
```powershell
.\build.ps1 -Clean
```

Resultado esperado:
- `BluetoothResetter.exe` en la raíz del proyecto.
- Sin consola extra.
- Con el ícono local.

## Versionado recomendado
- Usar formato `Vx.x.x`.
- Mantener la misma versión en:
  - `src/bluetooth_resetter/version.py`
  - GUI
  - `README.md`
  - `CHANGELOG.md`
  - tags y releases

## Comandos Git y GitHub paso a paso

### Inicializar repositorio local
```powershell
git init -b main
```
Crea el repositorio y define `main` como rama principal.

```powershell
git add .
```
Agrega todos los archivos del proyecto al staging.

```powershell
git commit -m "fix: resolve GitHub Actions version parsing in release workflow (V0.0.3)"
```
Crea el primer commit con un mensaje profesional y alineado al release inicial.

```powershell
git tag V0.0.3
```
Crea el tag inicial coherente con la versión visible en la app.

### Crear repositorio público en GitHub con GH CLI
```powershell
gh repo create bluetoothresetter --public --source . --remote origin --push
```
Crea el repositorio remoto público, enlaza `origin` y sube `main`.

### Próximo release
1. Incrementa versión en `version.py`, `README.md` y `CHANGELOG.md`.
2. Haz commit.
3. Haz push a `main`.
4. GitHub Actions compilará y publicará el release correspondiente.

## Release automático

El workflow `release.yml`:
- se ejecuta en cada `push` a `main`
- instala Python
- obtiene la versión desde el código
- compila el `.exe`
- adjunta el ejecutable al release de GitHub

## Licencia

Apache License 2.0.
