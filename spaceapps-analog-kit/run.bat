@echo off
REM Starts the demo from this folder with static serving on (needed for the globe)
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
python -m streamlit run app.py --server.enableStaticServing true
pause
