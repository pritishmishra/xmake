::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
::
:: Artifact Importer, (c) 2012 SAP AG
::
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

@echo off
setlocal

set ARTIFACTIMPORTER_HOME=%~dp0..
SET ARTIFACTIMPORTER_JAVA_EXECUTABLE=java.exe
IF DEFINED JAVA_HOME SET ARTIFACTIMPORTER_JAVA_EXECUTABLE="%JAVA_HOME%\bin\java.exe"

%ARTIFACTIMPORTER_JAVA_EXECUTABLE% %ARTIFACTIMPORTER_OPTS% -cp "%ARTIFACTIMPORTER_HOME%\lib\*;" com.sap.prd.commonrepo.artifactimporter.commands.ArtifactImporterCommand %*
