@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "PORT=8002"
set "PYTHONUTF8=1"
set "GOTOGYM_PROJECT_DIR=%~dp0..\gotogym"
set "ADMIN_EMAIL=admin@gotogym.com"
set "ADMIN_USERNAME=ericviana"
set "ADMIN_PASSWORD=EricViana@2026"

netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>nul
if %errorlevel%==0 (
    echo El puerto %PORT% esta ocupado. Se usara el puerto 8003.
    set "PORT=8003"
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

if not exist "%GOTOGYM_PROJECT_DIR%\db_local.sqlite3" (
    echo No se encontro la base comercial en "%GOTOGYM_PROJECT_DIR%\db_local.sqlite3".
    echo Este administrador debe estar junto a la carpeta gotogym del proyecto comercial.
    pause
    exit /b 1
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

python manage.py migrate
if errorlevel 1 (
    echo Fallaron las migraciones.
    pause
    exit /b 1
)

python manage.py seed_initial_data
if errorlevel 1 (
    echo No se pudieron crear las categorias y marca iniciales.
    pause
    exit /b 1
)

python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); email='%ADMIN_EMAIL%'; u,created=User.objects.get_or_create(email=email, defaults={'username':'%ADMIN_USERNAME%','first_name':'Eric','last_name':'Viana','is_staff':True,'is_superuser':True,'is_active':True}); u.username='%ADMIN_USERNAME%'; u.first_name='Eric'; u.last_name='Viana'; u.is_staff=True; u.is_superuser=True; u.is_active=True; u.set_password('%ADMIN_PASSWORD%'); u.save(); print('Administrador Eric Viana listo:', email)"
if errorlevel 1 (
    echo No se pudo crear o actualizar el administrador Eric Viana.
    pause
    exit /b 1
)

echo.
echo GoToGym Administracion listo.
echo URL: http://127.0.0.1:%PORT%/
echo Usuario: %ADMIN_EMAIL%
echo Contrasena: %ADMIN_PASSWORD%
echo Marca inicial: GoToGym
echo Categorias iniciales cargadas para crear productos.
echo Para detener el servidor presiona Ctrl+C.
echo.
python manage.py runserver 127.0.0.1:%PORT%
pause
