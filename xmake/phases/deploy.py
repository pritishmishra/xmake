'''
Created on 23.07.2014

@author: D051236
'''
import os
import log
import config
import json
import urlparse
import urllib
import ConfigParser
import tuning
from nexusstaging import StagingAPI
from os.path import join
from ExternalTools import OS_Utils
from xmake_exceptions import XmakeException
from artifact import Artifact


def resolve_deployment_credentials(build_cfg, t=config.COMMONREPO):
    # skip resolving if either no credential key was defined or user and password were specified
    if build_cfg.deploy_cred_key(t) is None or build_cfg.deploy_user(t) is not None and build_cfg.deploy_password(t) is not None:
        return
    prodpassaccess = build_cfg.tools().prodpassaccess()

    log.info("accessing credential key "+build_cfg.deploy_cred_key(t)+" for repository type "+t)

    # user
    log.info("call prodpassaccess to retrieve user")
    (rc, stdout, _) = OS_Utils.exec_script([prodpassaccess, 'get', build_cfg.deploy_cred_key(t), 'user'])
    if rc > 0:
        raise XmakeException('prodpassaccess returned %s' % str(rc))
    build_cfg.set_deploy_user(stdout.strip(), t)
    log.info("user retrieved")

    # password
    log.info("call prodpassaccess to retrieve password")
    (rc, stdout, _) = OS_Utils.exec_script([prodpassaccess, 'get', build_cfg.deploy_cred_key(t), 'password'])
    if rc > 0:
        raise XmakeException('prodpassaccess returned %s' % str(rc))
    build_cfg.set_deploy_password(stdout.strip(), t)
    log.info("password retrieved")

    # creds = [stdout.strip() for (rc,stdout,stderr) in [OS_Utils.exec_script([prodpassaccess, 'get', build_cfg.deploy_cred_key(t), ct]) for ct in ['user', 'password']]]
    # build_cfg.set_deploy_user(creds[0],t)
    # build_cfg.set_deploy_password(creds[1],t)


def execute_create_staging(build_cfg):
    if not build_cfg.do_create_staging():
        log.info("skipping staging repository creation, because the according option '--create-staging' was not set")
        return
    (jsonUserAgent, nexusApi, repoDescription) = _nexus_staging_init(build_cfg)
    repoId = _nexus_staging_create(build_cfg, jsonUserAgent, nexusApi, repoDescription)
    build_cfg.set_staging_repoid_parameter(repoId)  # Will avoid automatic closing during deployment as staging repo creation asked from command line


def execute_close_staging(build_cfg):
    if not build_cfg.do_close_staging():
        log.info("skipping staging repository closure, because the according option '--close-staging' was not set")
        return
    (_, nexusApi, _) = _nexus_staging_init(build_cfg)
    repoId = build_cfg.get_staging_repoid_parameter()
    if not repoId:
        repoId = build_cfg.get_created_staging_repoid()
    if not repoId:
        raise XmakeException("staging repository management failed. Impossible to close staging repository on nexus")
    else:
        _nexus_staging_close(build_cfg, nexusApi, repoId)


def execute_deployment(build_cfg):
    '''performs the xmake DEPLOY phase (deploys contents exported in the EXPORT phase to the specified maven repository)'''
    if not build_cfg.do_deploy():
        log.info("skipping deployment, because the according option '-d' was not set")
        return
    if build_cfg.do_custom_deploy():
        log.info("skipping nexus deployment, because of custom deployment")
        return
    if not os.path.exists(build_cfg.export_file()):
        log.warning("no export file found at: " + build_cfg.export_file())
        return  # TODO: consider breaking w/ err code

    isDiskDeployment = build_cfg.export_repo().startswith("file://")
    isStaging = build_cfg.is_release()

    # Deploy to nexus
    if not isDiskDeployment and not isStaging:
        _nexus_deployment(build_cfg, build_cfg.export_repo())
        return

    # Deploy to disk
    diskDeploymentPath = join(build_cfg.temp_dir(), 'stagingDeployment')
    local_repo_url = urlparse.urljoin('file:', urllib.pathname2url(diskDeploymentPath))

    log.info('deploying on disk {}'.format(diskDeploymentPath))
    _disk_deployment(build_cfg, local_repo_url)
    # Find artifacts in deployment folder
    artifacts = Artifact.gather_artifacts(diskDeploymentPath)

    if isStaging:
        (jsonUserAgent, nexusApi, repoDescription) = _nexus_staging_init(build_cfg)
        repoId = _nexus_staging_create(build_cfg, jsonUserAgent, nexusApi, repoDescription)
        status = _nexus_staging_push(build_cfg, jsonUserAgent, nexusApi, repoId, diskDeploymentPath)

        # If staging repo id set on commmand line, do not close it, except if promoting is requested in the same life cycle
        if not build_cfg.get_staging_repoid_parameter() or build_cfg.do_promote():
            status = _nexus_staging_close(build_cfg, nexusApi, repoId)

            # Create deployment descriptor file
            log.info("creating deploy.json file")
            if status and 'repositoryURI' in status:
                _create_deployment_file_descriptor(build_cfg, artifacts, local_repo_url, status['repositoryURI'])
            else:
                log.error('cannot create deployment file. Staging repository status returned by nexus does not contain the repository URI')
    else:
        log.info("deployment in a file share. Creating deploy.json file")
        # Create deployment descriptor file
        _create_deployment_file_descriptor(build_cfg, artifacts, local_repo_url, build_cfg.export_repo())
        # Deploy really to the definive disk place
        _disk_deployment(build_cfg, build_cfg.export_repo())


def _disk_deployment(build_cfg, export_repo_url):
    args = [build_cfg.tools().artifact_deployer(),
            'deploy',
            '-p', build_cfg.export_file(),
            '--repo-url', export_repo_url,
            '--artifact-version', build_cfg.base_version()]

    suffix = build_cfg.version_suffix()
    if suffix is not None and len(suffix) > 0:
        args.extend(['--artifact-version-suffix=-'+suffix])
    log.info('calling '+' '.join(args))

    # no version suffixe set to avoid deploying snapshot on disk
    rc = log.log_execute(args)
    if rc == 0:
        log.info("deployment of exported build results succeeded")
        log.info("deployed version: " + build_cfg.version())
    else:
        log.info("deployment returned w/ RC==" + str(rc))
        log.error("deployment of exported build results resulted in an error. See log output for further hints", log.INFRA)
        raise XmakeException("deployment failed")


def _nexus_deployment(build_cfg, export_repo_url):
    resolve_deployment_credentials(build_cfg)
    args = [build_cfg.tools().artifact_deployer(),
            'deploy',
            '-p', build_cfg.export_file(),
            '--repo-url', export_repo_url,
            '--artifact-version', build_cfg.base_version(),
            '--request-timeout', str(tuning.AD_TIMEOUT),
            '--write-artifact-info', build_cfg.deployment_info_log()]

    suffix = build_cfg.version_suffix()
    if suffix is not None and len(suffix) > 0:
        args.extend(['--artifact-version-suffix=-'+suffix])
    log.info('calling '+' '.join(args))

    if build_cfg.deploy_user():
        args.extend(['--repo-user', build_cfg.deploy_user()])
    if build_cfg.deploy_password():
        args.extend(['--repo-passwd', build_cfg.deploy_password()])

    rc = log.log_execute(args)
    if rc == 0:
        log.info("deployment of exported build results succeeded")
        log.info("deployed version: " + build_cfg.base_version() + (('-'+suffix) if suffix is not None else ''))
    else:
        log.info("deployment returned w/ RC==" + str(rc))
        log.error("deployment of exported build results resulted in an error. See log output for further hints", log.INFRA)
        raise XmakeException("deployment failed")


def _nexus_staging_init(build_cfg):
    resolve_deployment_credentials(build_cfg)
    nexusApi = StagingAPI(build_cfg.export_repo(),
                          username=build_cfg.deploy_user(),
                          password=build_cfg.deploy_password(),
                          tmpFolder=build_cfg.temp_dir(),
                          debugActivated=build_cfg.is_tool_debug())
    # build description that we will put in nexus staging repository
    repoDescription = {}
    repoDescription['description'] = 'Staging repository for {} project version {}'.format(build_cfg.scm_snapshot_url(), build_cfg.base_version())
    # build user agent that we will put as json structure in nexus staging repository
    userAgent = {}
    userAgent['scm'] = build_cfg.scm_snapshot_url()
    userAgent['version'] = build_cfg.version()
    userAgent['release-mode'] = 'milestone' if build_cfg.is_release() == 'milestone' or build_cfg.is_milestone() else 'customer'
    # Read and store Jenkins env variables
    jobName = os.getenv('JOB_NAME')
    if jobName is None:
        log.warning('jenkins job name is not set. Please set env JOB_NAME')
    else:
        userAgent['job'] = jobName
    buildNumber = os.getenv('BUILD_NUMBER')
    if buildNumber is None:
        log.warning('jenkins build number is not set. Please set env BUILD_NUMBER')
    else:
        userAgent['build-number'] = buildNumber
    buildUserId = os.getenv('BUILD_USER_ID')
    if buildUserId is None:
        log.warning('jenkins build user ID is not set. Please set env BUILD_USER_ID')
    else:
        userAgent['build-user-id'] = buildUserId
    parentJob = os.getenv('JOB_PARENT_NAME')
    if parentJob is None:
        log.warning('jenkins parent job name is not set. Please set env JOB_PARENT_NAME')
    else:
        userAgent['parentJob'] = parentJob
    treeish = os.getenv('TREEISH')
    if treeish is None:
        log.warning('jenkins treeish is not set. Please set env TREEISH')
    else:
        userAgent['treeish'] = treeish
    pomPath = os.getenv('POM_PATH')
    if pomPath is None:
        log.warning('maven pom path is not set')
    else:
        userAgent['pom-path'] = pomPath
    mavenVersion = os.getenv('MAVEN_VERSION')
    if mavenVersion is None:
        log.warning('maven version is not set')
    else:
        userAgent['maven-version'] = mavenVersion
    jdkVersion = os.getenv('JDK_VERSION')
    if jdkVersion is None:
        log.warning('jdk version is not set')
    else:
        userAgent['jdk-version'] = jdkVersion
    tychoVersion = os.getenv('TYCHO_VERSION')
    if tychoVersion is None:
        log.warning('tycho version is not set')
    else:
        userAgent['tycho-version'] = tychoVersion

    jsonUserAgent = json.dumps(userAgent)

    return(jsonUserAgent, nexusApi, repoDescription)


def _nexus_staging_create(build_cfg, jsonUserAgent, nexusApi, repoDescription):
    repoId = build_cfg.get_staging_repoid_parameter()
    if not repoId:
        repoId = build_cfg.get_created_staging_repoid()
        if not repoId:
            repoId = nexusApi.start(repoDescription, userAgent=jsonUserAgent)
            build_cfg.set_created_staging_repoid(repoId)
            if not repoId:
                raise XmakeException("staging failed. Impossible to create staging repository on nexus")

    # Write staging data to gen/tmp/staging.properties
    line = 'release_version={}\nrepository_id={}'.format(build_cfg.version(), repoId)
    with open(build_cfg.staging_props_file(), 'w') as f:
        f.write(line)

    return repoId


def _nexus_staging_push(build_cfg, jsonUserAgent, nexusApi, repoId, diskDeploymentPath):
    for root, dirs, files in os.walk(diskDeploymentPath):
        for name in files:
            artifact = {}
            artifact['filename'] = name
            artifact['path'] = os.path.join(root, name)
            artifact['relpath'] = artifact['path'].replace(diskDeploymentPath, '').replace('\\', '/')
            if artifact['relpath'].startswith('/'):
                artifact['relpath'] = artifact['relpath'][1:]

            succeeded = nexusApi.deployByRepositoryId(repoId, artifact, userAgent=jsonUserAgent)
            if not succeeded:
                raise XmakeException('Failed to deploy file {} to repository {}'.format(artifact, repoId))

    status = nexusApi.getrepositorystatus(repoId)
    log.info('build results pushed into staging repo \'{}\'. This staging repo is not closed yet.'.format(status['repositoryURI']))

    return status


def _nexus_staging_close(build_cfg, nexusApi, repoId):
    if not nexusApi.finish(repoId):
        raise XmakeException('close of staging repository failed. Analyse the build log and look at repository id: {}.'.format(repoId))
    status = nexusApi.getrepositorystatus(repoId)
    ua_scm_snapshot_url = build_cfg.scm_snapshot_url()
    if not ua_scm_snapshot_url:
        try:
            userAgent = json.loads(status['userAgent'])
            if userAgent:
                if 'scm' in userAgent:
                    ua_scm_snapshot_url = userAgent['scm']
                    log.info('scm_snapshot_url read from staging repository: {}'.format(ua_scm_snapshot_url))
        except ValueError:
            pass

    _storeStageCloseProps(nexusApi, build_cfg, repoId, ua_scm_snapshot_url)

    log.info('*' * 100)
    log.info('build results are available in staging repository:')
    log.info(status['repositoryURI'])
    log.info('scm_snapshot_url:')
    log.info(ua_scm_snapshot_url)
    log.info('*' * 100)

    return status


def _create_deployment_file_descriptor(build_cfg, artifacts, initial_repo_url, final_repo_url):
    '''Create a deployment descriptor file'''

    # Build array of artifacts deployed
    artifactsToDeploy = []
    for key in artifacts:
        artifactValues = artifacts[key]
        for artifactObj in artifactValues:
            log.info("artifact to deploy " + artifactObj.path)
            deployUrl = urlparse.urljoin('file:', urllib.pathname2url(artifactObj.path))
            deployUrl = deployUrl.replace(initial_repo_url, final_repo_url)

            jsonArtifact = {
                "groupId": artifactObj.gid,
                "artifactId": artifactObj.aid,
                "version": artifactObj.version,
                "deployUrl": deployUrl
            }

            if artifactObj.classifier:
                jsonArtifact["classifier"] = artifactObj.classifier

            if artifactObj.extension:
                jsonArtifact["extension"] = artifactObj.extension

            artifactsToDeploy.append(jsonArtifact)

    # Wrtie on json file on disk
    jsonfilepath = join(build_cfg.temp_dir(), "deploy.json")
    with open(jsonfilepath, "w") as jsonfile:
        json.dump(artifactsToDeploy, jsonfile, indent=2)
    log.info("created file " + jsonfilepath)


def _storeStageCloseProps(nexusApi, build_cfg, repoId, snapshot_url):

    status = nexusApi.getrepositorystatus(repoId)

    config = ConfigParser.ConfigParser()
    config.add_section('stageclose')
    config.set('stageclose', 'staging.repo.url', status['repositoryURI'])
    config.set('stageclose', 'staging.repo.id', repoId)
    config.set('stageclose', 'git.repo', snapshot_url.split('@')[0])
    config.set('stageclose', 'git.treeish', snapshot_url.split('@')[1])
    with open(build_cfg.close_stage_props_file(), 'w') as f:
        config.write(f)
