@echo off
rem Musicoma 엔진 빌드 (MSVC x64 + Ninja, Release)
call "C:\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
if not exist build\build.ninja cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release || exit /b 1
cmake --build build --parallel || exit /b 1
copy /y "..\third_party\sfizz\bin\Release\sfizz.dll" "build\musicoma_engine_artefacts\Release\" >nul
echo BUILD_OK
