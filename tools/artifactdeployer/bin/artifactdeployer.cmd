::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
::
:: Artifact Deployer, (c) 2013 SAP SE
::
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

@echo off
setlocal

set ARTIFACTDEPLOYER_HOME=%~dp0..
SET ARTIFACTDEPLOYER_JAVA_EXECUTABLE=java.exe
IF DEFINED JAVA_HOME SET ARTIFACTDEPLOYER_JAVA_EXECUTABLE="%JAVA_HOME%\bin\java.exe"

%ARTIFACTDEPLOYER_JAVA_EXECUTABLE% %ARTIFACTDEPLOYER_OPTS% -cp "%ARTIFACTDEPLOYER_HOME%\lib\*;" com.sap.prd.commonrepo.artifactdeployer.commands.ArtifactDeployerCommand %*
