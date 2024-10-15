@echo off
cd backend
start cmd /c python main.py
cd ..\frontend
start cmd /c python app.py
cd ..