@echo off
:begin
if "%1"=="" goto :end
if "%1"=="--version" echo CURRENT NPM VERSION IS 1.0.0
shift
goto :begin
:end