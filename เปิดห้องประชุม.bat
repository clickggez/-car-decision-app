@echo off
chcp 65001 >nul
title ห้องประชุม AI - CarDSS
cd /d "%~dp0"

where node >nul 2>&1
if errorlevel 1 (
  echo ไม่พบ Node.js บนเครื่อง กรุณาติดตั้งก่อน
  pause
  exit /b 1
)

echo กำลังเปิดห้องประชุม...
start "ห้องประชุม AI" /min cmd /c "node agent-docs\meeting\server.mjs serve"
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:7788

echo.
echo เปิดแล้วที่ http://127.0.0.1:7788
echo หน้าต่างเซิร์ฟเวอร์ย่อไว้ที่ทาสก์บาร์ ปิดหน้าต่างนั้นเพื่อหยุด
echo.
timeout /t 4 /nobreak >nul
