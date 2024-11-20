@echo off
cd backend
if $@ == "-k" (
    start cmd /k python main.py
    cd ..\frontend
    start cmd /k python app.py
) else (
    start cmd /c python main.py
    cd ..\frontend
    start cmd /c python app.py
)
cd ..