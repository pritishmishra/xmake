@echo off
::::::::::::::::::::::::::::::::::::::::::::
::
:: xmake, (c) 2013 SAP AG
::
:::::::::::::::::::::::::::::::::::::::::::

setlocal

:: determine whether python is available in PATH
@where python
if ERRORLEVEL 1 GOTO err_no_python

:: determine if this xmake was isntalled, or fetched from GIT --> different tool structure
:: the file buildversion.txt is generated at build time and packed into installer

SET XMAKE_PATH=%~dp0..

::invoke xmake
python "%XMAKE_PATH%\xmake\bootstrap.py" %*

goto :EOF

:err_no_python
echo ERROR: python was not found in PATH
EXIT /B 1

