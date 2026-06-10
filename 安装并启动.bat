@echo off
chcp 65001 > nul
title 课堂实录评分工具 - 安装并启动

echo ===================================================
echo   课堂实录评分工具 - 安装并启动
echo ===================================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] 未检测到 Python，请先安装 Python 3.9 或以上版本
    echo     下载地址：https://www.python.org/downloads/
    echo     安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)
echo [OK] Python 已安装

REM 安装依赖
echo.
echo [1/3] 正在安装 Python 依赖包（首次运行需 2-5 分钟）...
pip install -r requirements.txt -q --no-warn-script-location
if errorlevel 1 (
    echo [X] 依赖安装失败，请检查网络后重试
    pause
    exit /b 1
)
echo [OK] 依赖安装完成

REM 检查 ffmpeg
echo.
echo [2/3] 检查 ffmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [!] 未检测到 ffmpeg，正在尝试安装...
    where winget >nul 2>&1
    if not errorlevel 1 (
        winget install FFmpeg -h --accept-source-agreements --silent
        echo [OK] ffmpeg 安装完成，请重启电脑后重新运行本脚本
        pause
        exit /b 0
    ) else (
        echo [!] 无法自动安装 ffmpeg，请手动安装：
        echo     方式1：winget install FFmpeg
        echo     方式2：前往 https://www.gyan.dev/ffmpeg/builds/ 下载，解压后将 bin 目录加入 PATH
        echo.
        echo     安装完成后重新运行本脚本
        pause
        exit /b 1
    )
) else (
    echo [OK] ffmpeg 已安装
)

REM 启动服务
echo.
echo [3/3] 启动课堂实录评分工具...
echo ===================================================
echo   服务启动后，浏览器会自动打开：http://localhost:8501
echo   如果没有自动打开，请手动访问：http://localhost:8501
echo   关闭本窗口即可停止服务
echo ===================================================
echo.

streamlit run app.py --server.maxUploadSize 1024 --server.port 8501

pause
