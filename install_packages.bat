@echo off
echo ================================
echo  Installing required packages...
echo ================================
echo.

C:/Users/HP/AppData/Local/Programs/Python/Python314/python.exe -m pip install pyserial
echo.
C:/Users/HP/AppData/Local/Programs/Python/Python314/python.exe -m pip install websockets
echo.
echo ================================
echo  Done! Now run: python bridge.py
echo ================================
pause
