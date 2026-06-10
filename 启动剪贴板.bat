@echo off
chcp 65001 >nul
title 历史剪贴板

:: 检查 Python 是否可用
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ════════════════════════════════════
    echo   Python 未安装或未添加到 PATH！
    echo.
    echo   请按以下步骤安装 Python：
    echo.
    echo   1. 打开 Microsoft Store
    echo   2. 搜索 "Python 3.12" 并安装
    echo   3. 安装完成后重新双击本文件
    echo.
    echo   或者访问 https://www.python.org
    echo ════════════════════════════════════
    pause
    exit /b
)

:: 启动剪贴板历史软件
python "%~dp0clipboard_history.py"
pause
