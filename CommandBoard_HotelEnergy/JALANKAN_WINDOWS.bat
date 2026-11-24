@echo off
chcp 65001 >nul
title Hotel Energy Command Board
cd /d "%~dp0"

echo ==========================================================
echo   Hotel Energy Command Board - versi web
echo ==========================================================
echo.

rem --- cari Python (py launcher atau python) ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY goto :nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if errorlevel 1 goto :nopython

rem --- virtual environment (sekali saja) ---
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Membuat virtual environment .venv ...
  %PY% -m venv .venv
  if errorlevel 1 goto :error
)

echo [2/3] Memeriksa / memasang library (pertama kali bisa 2-5 menit) ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r command_board\requirements-web.txt
if errorlevel 1 goto :error

echo [3/3] Menjalankan server di http://localhost:8600
echo.
echo   Browser akan terbuka otomatis. Jika tidak, buka alamat di atas secara manual.
echo   Untuk menghentikan: tutup jendela ini atau tekan Ctrl+C.
echo.
start "" cmd /c "timeout /t 5 >nul & start http://localhost:8600"
".venv\Scripts\python.exe" -m uvicorn server:app --app-dir command_board --host 127.0.0.1 --port 8600
pause
exit /b 0

:nopython
echo [!] Python 3.10 atau lebih baru tidak ditemukan.
echo     Pasang dari https://www.python.org/downloads/ lalu CENTANG "Add python.exe to PATH".
echo     Setelah itu jalankan file ini lagi.
pause
exit /b 1

:error
echo.
echo [!] Terjadi kesalahan. Lihat pesan di atas, atau baca CARA_MENJALANKAN.txt bagian "Masalah umum".
pause
exit /b 1
