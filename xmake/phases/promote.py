'''
Created on 08.09.2015

@author: I051375
'''
import json
import log
from nexusstaging import StagingAPI
from phases.deploy import resolve_deployment_credentials
from xmake_exceptions import XmakeException
import ConfigParser

def execute_promote(build_cfg):

    '''Drop the given repository if --drop-staging used'''
    if build_cfg.do_drop_staging():
        repoId=build_cfg.get_staging_repoid_parameter()
        if not repoId:
            raise XmakeException('drop of staging repository failed. Must give a valid repositoryId. Found: {}'.format(repoId))
        log.info( 'dropping staging repository with  repositoryId: {}'.format(repoId))
        nexusApi = getNexusInstance(build_cfg)
        drop_status = nexusApi.drop(repoId)
        if  drop_status==False:
            raise XmakeException('cannot drop repository {}.'.format(repoId))

    '''performs the xmake PROMOTE phase'''
    if not build_cfg.do_promote():
        log.info( "skipping staged nexus promotion")
        return

    promoted = False
    #Get staging repositories to be promoted corresponding to the given commit Id
    nexusApi = getNexusInstance(build_cfg)

    repoId=build_cfg.get_staging_repoid_parameter() # If staging repo id set on commmand line, take it
    if not repoId:
        repoId=build_cfg.get_created_staging_repoid() # if created during the same build life cycle so during the deploy step, no need to search
        if not repoId:
            repos = nexusApi.getFilteredRepos(build_cfg.scm_snapshot_url(), build_cfg.version(),True, 'closed')
            if len(repos)!= 1:
                log.error( 'expecting one repository Id. Got {}: {}'.format(len(repos), ', '.join(repos)))
            else:
                # promote staging
                repoId = repos[0]

    if repoId:
        promoted = nexusApi.promote(repoId, 'Maven2')
    if not promoted:
        log.error('promote phase has error')
        raise XmakeException('promote phase has error')

    # Ignore commit id when cleaning
    ua_scm_snapshot_url=build_cfg.scm_snapshot_url()
    ua_version=build_cfg.version()
    ua_treeish=""

    # If one of these variable not defined, try to find it automatically in the current staging repository
    if not ua_scm_snapshot_url or not ua_version:
        log.info('need to read repository status for repositoryId: {}'.format(repoId))
        oresponse=nexusApi.getrepositorystatus(repoId)
        if oresponse and 'userAgent' in oresponse:
            try:
                userAgent=json.loads(oresponse['userAgent'])
                if userAgent:
                    if 'scm' in userAgent and not ua_scm_snapshot_url:
                        ua_scm_snapshot_url=userAgent['scm']
                        log.info('scm_snapshot_url read from staging repository: {}'.format(ua_scm_snapshot_url))
                    if 'version' in userAgent and not ua_version:
                        ua_version=userAgent['version']
                        log.info('version read from staging repository: {}'.format(ua_version))
            except ValueError:
                pass

    projectId=None
    if ua_scm_snapshot_url:
        splitted_ua_scm_snapshot_url=ua_scm_snapshot_url.split('@')
        tokens =  splitted_ua_scm_snapshot_url[:-1]
        projectId =  ua_scm_snapshot_url
        if tokens:
            projectId = '@'.join(tokens)
            ua_treeish=splitted_ua_scm_snapshot_url[1]

    # Store Promote properties to file
    _storePromoteProps(nexusApi, build_cfg, repoId, ua_treeish, ua_version);

    log.info( "try to clean obsolete repositories for this project")
    if projectId:
        toBeDropped = nexusApi.getFilteredRepos(projectId, ua_version, False, 'closed', 'open')

        for repoId in toBeDropped:
            try:
                nexusApi.drop(repoId)
            except Exception as e:
                log.warning('cannot drop repository {}. {}'.format(repoId, str(e)))
    else:
        log.warning('no scm_snapshot_url specified/found for trying to clean obsolete repositories')



def _storePromoteProps(nexusApi, build_cfg, repoId, treeish, version):

    status = nexusApi.getrepositorystatus(repoId)
    base_group = build_cfg.base_group()
    base_artifact = build_cfg.base_artifact()

    groupPath = base_group

    if status == None or not ('repositoryURI' in status and 'releaseRepositoryId' in status):
        log.error('impossible to store promote properties. Can not have repository status: {} '.format(status))
        return
    urlTab = status['repositoryURI'].split('/')[:-1]
    rootPath = '/'.join(urlTab)

    metadataPath=None
    if groupPath is not None and base_artifact is not None and version is not None:
        metadataPath = '{}/{}/{}/{}/{}/{}-{}-releaseMetadata.zip'.format(rootPath,status['releaseRepositoryId'],groupPath.replace('.','/'), base_artifact,version,base_artifact,version)
        log.info('write the releaseMetadata.zip url {} in {}'.format(metadataPath, build_cfg.promote_props_file()))

    config = ConfigParser.ConfigParser()
    config.add_section('promote')
    if metadataPath is not None:
        config.set('promote','release.metadata.url', metadataPath)
    if base_group is not None:
        config.set('promote','base.group',base_group)
    if base_artifact is not None:
        config.set('promote','base.artifact',base_artifact)
    if version is not None:
        config.set('promote','base.version',version)
    if treeish is not None:
        config.set('promote','base.treeish', treeish)

    with open (build_cfg.promote_props_file(), 'w') as f:
        config.write(f)

def getNexusInstance(build_cfg):
    resolve_deployment_credentials(build_cfg)
    nexusApi = StagingAPI(build_cfg.export_repo(), username=build_cfg.deploy_user(),
        password=build_cfg.deploy_password(),
        tmpFolder=build_cfg.temp_dir(),
        debugActivated=build_cfg.is_tool_debug())
    return nexusApi
