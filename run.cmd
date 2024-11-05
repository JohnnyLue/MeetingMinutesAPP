@echo off
cd backend
start cmd /k python main.py
cd ..\frontend
start cmd /k python app.py
cd ..