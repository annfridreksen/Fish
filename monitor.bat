@echo off

start app.exe

TIMEOUT /T 2 /NOBREAK
 
start http://127.0.0.1:5000/
 
exit