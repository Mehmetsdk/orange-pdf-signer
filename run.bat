@echo off
title PDF Signer
cd /d "%~dp0"

:: Sanal ortam varsa aktif et, yoksa global Python kullan
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo.
echo  ==========================================
echo    PDF Signer baslatiliyor...
echo  ==========================================
echo.

:: Tarayiciyi 2 saniye sonra ac (Streamlit'in ayaga kalkmasini bekle)
start "" cmd /c "timeout /t 2 >nul && start http://localhost:8501"

python -m streamlit run app.py --server.headless false

pause
