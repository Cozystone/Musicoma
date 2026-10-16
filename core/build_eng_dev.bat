@echo off
call "C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
cmake -S . -B build-eng -G Ninja -DCMAKE_BUILD_TYPE=Release >nul || exit /b 1
cmake --build build-eng --target %1 || exit /b 1
echo BUILD_OK
