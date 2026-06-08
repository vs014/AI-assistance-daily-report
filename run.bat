@echo off
cd /d "%~dp0"
pip install -r requirements.txt --quiet
start /b cmd /c "timeout /t 5 /nobreak >nul && start http://localhost:8501"
python -m streamlit run app.py --server.port 8501 --server.headless true
