::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
::
:: ProdPassAccess Tool, (c) 2013 SAP AG
::
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

@echo off
setlocal

set PRODPASSACCESS_HOME=%~dp0..
SET PRODPASSACCESS_JAVA_EXECUTABLE=java.exe
IF DEFINED JAVA_HOME SET PRODPASSACCESS_JAVA_EXECUTABLE="%JAVA_HOME%\bin\java.exe"

%PRODPASSACCESS_JAVA_EXECUTABLE% %PRODPASSACCESS_OPTS% -cp "%PRODPASSACCESS_HOME%\lib\*;" com.sap.prd.access.credentials.cli.ProdPassAccessCLI %*
