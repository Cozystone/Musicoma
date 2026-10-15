@echo off
rem Musicoma Core build (MSVC x64 + Ninja, Release) - output: core\build\musicoma-core.exe
call "C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
if not exist build\build.ninja cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release || exit /b 1
cmake --build build --parallel || exit /b 1
echo BUILD_OK
