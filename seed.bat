@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   Smart Warehouse ERP - Seed
echo ========================================
echo.

set PYTHON=.venv\Scripts\python.exe

if "%1"=="clear" (
    echo [*] Baza tozalanib, fake malumotlar qoshilmoqda...
    %PYTHON% manage.py seed --clear --users 8 --products 40 --sales 60 --expenses 50 --clients 15 --payments 40
) else if "%1"=="small" (
    echo [*] Kichik hajmda fake malumotlar...
    %PYTHON% manage.py seed --clear --users 3 --products 10 --sales 15 --expenses 10 --clients 5 --payments 10
) else if "%1"=="big" (
    echo [*] Katta hajmda fake malumotlar...
    %PYTHON% manage.py seed --clear --users 20 --products 100 --sales 200 --expenses 150 --clients 50 --payments 120
) else if "%1"=="fresh" (
    echo [*] Baza o'chirib, qayta yaratilmoqda...
    if exist db.sqlite3 del db.sqlite3
    %PYTHON% manage.py migrate
    %PYTHON% manage.py createsuperuser --username admin --email admin@warehouse.uz --noinput
    %PYTHON% -c "from apps.users.models import User; u=User.objects.get(username='admin'); u.set_password('admin123'); u.role='MANAGEMENT'; u.save()"
    %PYTHON% manage.py seed --users 8 --products 40 --sales 60 --expenses 50 --clients 15 --payments 40
    echo.
    echo [OK] Tayyor^!  admin / admin123
) else (
    echo [*] Standart seed - fake malumotlar qoshilmoqda...
    %PYTHON% manage.py seed --users 8 --products 40 --sales 60 --expenses 50 --clients 15 --payments 40
)

echo.
echo ========================================
echo   Bajarildi!
echo ========================================
