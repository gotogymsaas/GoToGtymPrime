@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "PORT=8000"
set "PYTHONUTF8=1"

netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>nul
if %errorlevel%==0 (
    echo El puerto %PORT% esta ocupado. Se usara el puerto 8001.
    set "PORT=8001"
)

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_CMD=python"
    ) else (
        echo No se encontro Python. Instala Python 3.11 o superior desde https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual local...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo No se pudieron instalar las dependencias.
    pause
    exit /b 1
)

cd gotogym
python manage.py migrate --settings=gotogym.settings_local
if errorlevel 1 (
    echo Fallaron las migraciones locales.
    pause
    exit /b 1
)

python manage.py check --settings=gotogym.settings_local
if errorlevel 1 (
    echo La validacion de Django encontro errores.
    pause
    exit /b 1
)

if not exist "static\images\img\Nuestros productos\Camiseta.png" (
    echo No se encontro la imagen de Camisetas en static\images\img\Nuestros productos.
    pause
    exit /b 1
)
if not exist "static\images\img\Nuestros productos\Conjunto 31.png" (
    echo No se encontro la imagen de Sets en static\images\img\Nuestros productos.
    pause
    exit /b 1
)
if not exist "static\images\img\Nuestros productos\Topito.png" (
    echo No se encontro la imagen de Tops en static\images\img\Nuestros productos.
    pause
    exit /b 1
)
if not exist "static\images\img\Nuestros productos\Leggins blanco.png" (
    echo No se encontro la imagen de Leggings en static\images\img\Nuestros productos.
    pause
    exit /b 1
)

echo.
echo Proyecto listo.
echo Abre http://127.0.0.1:%PORT%/ en el navegador.
echo Admin: http://127.0.0.1:%PORT%/admin/
echo Para detener el servidor presiona Ctrl+C.
echo.
python manage.py runserver 127.0.0.1:%PORT% --settings=gotogym.settings_local
pause
