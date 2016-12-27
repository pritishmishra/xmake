'''
Created on 18.09.2015
@author: I050906, I051432, I079877, I051375
'''

import sys
import time
import log
import zipfile
import httplib
import urllib2
import re
import os
import tempfile
import json
import xml.etree.ElementTree as ET
import HTMLParser
from multipartform import MultiPartForm
from xml.sax.saxutils import escape

from urlparse import urlparse
import base64
import ssl

import tuning


class StagingAPI():
    '''
        Class that wraps the Nexus HTTP REST API for staging.
    '''
    def __init__(self, restApiUrl, username=None, password=None, profileId=None, proxies=None, tmpFolder=None, debugActivated=False):
        log.info('init Nexus Staging Rest API')
        self._reJsonRespRepoId = r'(?P<repoId>[^\/]+)$'
        self._htmlParser = HTMLParser.HTMLParser()
        self._username = username
        self._password = password
        self._debugActivated = debugActivated

        if tmpFolder is None:
            self._tmpFolder = tempfile.gettempdir()

        if restApiUrl is None:
            raise Exception('rest api url is not set')
        # find base url of service
        self._restApiUrl = restApiUrl
        if restApiUrl.endswith('/'):
            self._restApiUrl = restApiUrl[0:len(restApiUrl)]

        if '/profiles' in restApiUrl:
            self._restApiUrl = restApiUrl[0:restApiUrl.find('/profiles')]
            # decode profile from restApiUrl
            reProfileId = r'.*profiles\/(?P<profileId>[^\/]+)'
            m = re.search(reProfileId, restApiUrl)
            if m:
                profileIdFromRestApiUrl = m.group('profileId')
                if profileId and profileIdFromRestApiUrl:
                    if profileIdFromRestApiUrl != profileId:
                        raise Exception('profileId provided explicitly (\'{}\') and also implicitely via nexus url (\'{}\'). The values does not match.'.format(profileId, profileIdFromRestApiUrl))
                profileId = profileIdFromRestApiUrl

        if profileId:
            self._profileId = profileId
        else:
            self._profileId = None

        if self._profileId is None:
            raise Exception('profileId is not set')

        handler = urllib2.HTTPHandler(debuglevel=1 if debugActivated else 0)
        self._opener = urllib2.build_opener(handler)

        if username:
            if password is None:
                raise Exception('username was set without password. If password is empty please set an empty string in constructor argument')

            log.debug('username/password were set for Nexus Staging Rest API')
            log.debug('username/password are valid for all urls starting by {}'.format(self._restApiUrl))
        else:
            log.debug('No username/password were set for Nexus Staging Rest API')

        if proxies:
            self._opener.add_handler(urllib2.ProxyHandler(proxies))

    def start(self, data, userAgent=None):
        '''
            Entry point to trigger staging repository creation.
        '''

        log.info('CREATE a new staging repository')
        url = '{}/profiles/{}/{}'.format(self._restApiUrl, self._profileId, 'start')

        headers = {}
        headers['Cache-Control'] = 'no-cache'
        headers['Content-Type'] = 'application/xml'
        if userAgent:
            headers['User-Agent'] = userAgent

        response = self._request(url, headers, byteRequest=bytearray(self._buildRequest(data)))
        if response:
            xmlResponse = ET.fromstring(response)
            oresponse = {}
            oresponse['stagedRepositoryId'] = xmlResponse.find('data').find('stagedRepositoryId').text
            if 'stagedRepositoryId' in oresponse and oresponse['stagedRepositoryId']:
                repoId = oresponse['stagedRepositoryId']
                if repoId:
                    def checkStatus():
                        return self.getrepositorystatus(repoId, userAgent)

                    def isStatusValid(status):
                        if 'type' in status and status['type'] == 'open':
                            log.info('\trepository status is \'{}\''.format(status['type']))
                            return 0

                        if 'notifications' in status and status['notifications'] != '0':
                            log.error('\tlast operation on nexus server failed with {} notifications'.format(status['notifications']))
                            self._logActivityForStep(repoId)
                            return 1

                        log.warning('\trepository is not created yet... Nexus still working expected status \'{}\' got status \'{}\''.format('open', status['type']))
                        return 2

                    if self._requestManyTimes(checkStatus, isStatusValid, cbLogMessage=lambda tryNumber: log.info('\ttry {} to check if staging repository is created on nexus'.format(tryNumber))):
                        log.info('staging repository created with id {}'.format(repoId))
                        return repoId

        log.error('fail to create staging repository')
        return None

    def drop(self, stagedRepositoryId):
        '''
            Entry point to trigger staging repository drop (remove repository and it's contents without promoting it).
        '''

        log.info('DROP staging repository id {}'.format(stagedRepositoryId))
        url = '{}/profiles/{}/{}'.format(self._restApiUrl, self._profileId, 'drop')

        headers = {}
        headers['Cache-Control'] = 'no-cache'
        headers['Content-Type'] = 'application/xml'

        response = self._request(url, headers, byteRequest=bytearray(self._buildRequest({'stagedRepositoryId': stagedRepositoryId})))
        if response == '':
            def checkStatus():
                return self._request('{}/repository/{}'.format(self._restApiUrl, stagedRepositoryId), returnOnlyHttpCode=True)

            def isStatusValid(status):
                if status == 404:
                    log.info('\tstaging repository is no more available on Nexus')
                    return 0
                if status is None:
                    log.error('\tcannot check if staging repository is dropped on Nexus')
                    return 1
                log.warning('\tstaging repository is still available... Nexus still working resource respond {}'.format(status))
                return 2

            if self._requestManyTimes(checkStatus, isStatusValid, cbLogMessage=lambda tryNumber: log.info('\ttry {} to check if staging repository is dropped on nexus'.format(tryNumber))):
                log.info('staging repository {} dropped'.format(stagedRepositoryId))
                return True

        if response:
            log.error(response)

        log.error('fail to drop staging repository {}'.format(stagedRepositoryId))
        return False

    def finish(self, stagedRepositoryId):
        '''
            Entry point to trigger staging repository close (finish deploy and close staging repository).
        '''

        log.info('CLOSE staging repository id {}'.format(stagedRepositoryId))
        url = '{}/profiles/{}/{}'.format(self._restApiUrl, self._profileId, 'finish')

        headers = {}
        headers['Cache-Control'] = 'no-cache'
        headers['Content-Type'] = 'application/xml'

        response = self._request(url, headers, byteRequest=bytearray(self._buildRequest({'stagedRepositoryId': stagedRepositoryId})))
        if response == '':
            def checkStatus():
                return self.getrepositorystatus(stagedRepositoryId)

            def isStatusValid(status):
                if 'type' in status and status['type'] == 'closed':
                    log.info('\trepository status is \'{}\''.format(status['type']))
                    return 0

                if 'notifications' in status and status['notifications'] != '0':
                    log.error('\tlast operation on nexus server failed with {} notifications'.format(status['notifications']))
                    return 1

                log.warning('\trepository is not closed yet... Nexus still working expected status \'{}\' got status \'{}\''.format('closed', status['type']))
                return 2

            if self._requestManyTimes(checkStatus, isStatusValid, nbTry=tuning.CLOSE_REQ_ATTEMPTS, waitSecond=tuning.CLOSE_DELAY_BETWEEN_REQ_ATTEMPTS, cbLogMessage=lambda tryNumber: log.info('\ttry {} to check if staging repository is closed on nexus'.format(tryNumber))):
                log.info('staging repository {} closed'.format(stagedRepositoryId))
                return True

        if response:
            log.error(response)
        self._logActivityForStep(stagedRepositoryId)
        log.error('fail to close staging repository {}'.format(stagedRepositoryId))
        return False

    def promote(self, stagedRepositoryId, targetRepositoryId):
        '''
            Entry point to trigger staging repository promotion.
        '''

        log.info('PROMOTE staging repository id {}'.format(stagedRepositoryId))
        url = '{}/profiles/{}/{}'.format(self._restApiUrl, self._profileId, 'promote')

        headers = {}
        headers['Cache-Control'] = 'no-cache'
        headers['Content-Type'] = 'application/xml'

        response = self._request(url, headers, byteRequest=bytearray(self._buildRequest({'stagedRepositoryId': stagedRepositoryId, 'targetRepositoryId': targetRepositoryId})))
        if response == '':
            def checkStatus():
                return self.getrepositorystatus(stagedRepositoryId)

            def isStatusValid(status):
                if 'type' in status and status['type'] == 'released':
                    log.info('\trepository status is \'{}\''.format(status['type']))
                    return 0

                if 'notifications' in status and status['notifications'] != '0':
                    log.error('\tlast operation on nexus server failed with {} notifications'.format(status['notifications']))
                    return 1

                log.info('\trepository is not promoted yet... Nexus still working expected status \'{}\' got status \'{}\''.format('released', status['type']))
                return 2

            if self._requestManyTimes(checkStatus, isStatusValid, nbTry=tuning.PROMOTE_REQ_ATTEMPTS, waitSecond=tuning.PROMOTE_DELAY_BETWEEN_REQ_ATTEMPTS, cbLogMessage=lambda tryNumber: log.info('\ttry {} to check if staging repository is promoted on nexus'.format(tryNumber))):
                log.info('staging repository {} promoted successfully'.format(stagedRepositoryId))
                return True

            log.error('could not confirm promote of staging repository {} (check status in nexus)'.format(stagedRepositoryId))
            return False

        if response:
            log.error(response)

        self._logActivityForStep(stagedRepositoryId)
        log.error('promote command to nexus failed')
        return False

    def upload(self, stagedRepositoryId, artifact, description, userAgent=None):
        '''
            Handles the upload of artifact.
        '''

        log.info('UPLOAD artifact {}.{} in staging repository {}'.format(artifact['group'], artifact['artifact'], stagedRepositoryId))
        form = MultiPartForm()
        form.add_field('r', stagedRepositoryId)
        form.add_field('g', artifact['group'])
        form.add_field('a', artifact['artifact'])
        form.add_field('v', artifact['version'])
        form.add_field('p', artifact['package'])
        form.add_field('c', artifact['classifier'])
        form.add_field('e', artifact['extension'])
        form.add_field('desc', description)

        form.add_file('file', artifact['filename'], fileHandle=open(artifact['path'], 'rb'))
        body = str(form)

        url = '{}/{}'.format(self._restApiUrl, 'upload')

        headers = {}
        headers['Content-Type'] = form.get_content_type()
        headers['Content-Length'] = len(body)
        if userAgent:
            headers['User-Agent'] = userAgent

        response = self._request(url, headers, byteRequest=body)
        if response:
            oresponse = json.loads(response)
            if 'repositoryId' in oresponse:
                repoId = oresponse['repositoryId']
                if repoId:
                    def checkStatus():
                        return self.repository_content(stagedRepositoryId, artifact['relpath'].replace(artifact['filename'], ''))

                    def isStatusValid(content_items):
                        if content_items is None:
                            log.error('\tcannot check if file is available on Nexus')
                            return 1

                        for content_item in content_items:
                            if 'text' in content_item and content_item['text'] == artifact['filename']:
                                log.info('\tthe file is available on Nexus')
                                return 0

                        log.warning('\tthe file is not fully uploaded yet... Nexus still working')
                        return 2

                    if self._requestManyTimes(checkStatus, isStatusValid, cbLogMessage=lambda tryNumber: log.info('\ttry {} to check if file is uploaded on nexus'.format(tryNumber))):
                        log.info('artifact {}.{} uploaded in staging repository {}'.format(artifact['group'], artifact['artifact'], repoId))
                        return repoId

        log.error('fail to upload artifact {}.{} in staging repository {}'.format(artifact['group'], artifact['artifact'], stagedRepositoryId))
        return None

    def bundle_upload(self, artifactFolder, relativePath, userAgent=None):
        '''
            Handles the upload of bundle.
        '''

        log.info('UPLOAD BUNDLE in new staging repository')
        log.info('create bundle.zip')
        zf = zipfile.ZipFile(os.path.join(self._tmpFolder, 'bundle.zip'), mode='w')
        filesTocheck = []
        relativePath = relativePath.replace('\\', '/')
        relativePath = relativePath[1:] if relativePath.startswith('/') else relativePath
        relativePath = relativePath[:-1] if relativePath.endswith('/') else relativePath
        try:
            for root, dirs, files in os.walk(artifactFolder):
                for name in files:
                    filePath = os.path.join(root, name)
                    filesTocheck.append(name)
                    log.info('adding {}'.format(filePath))
                    zf.write(filePath, name)
        finally:
            log.info('closing bundle.zip')
            zf.close()

        form = MultiPartForm()
        form.add_file('file', 'bundle.zip', fileHandle=open(os.path.join(self._tmpFolder, 'bundle.zip'), 'rb'))
        body = str(form)

        url = '{}/{}'.format(self._restApiUrl, 'bundle_upload')

        headers = {}
        headers['Content-Type'] = form.get_content_type()
        headers['Content-Length'] = len(body)
        if userAgent:
            headers['User-Agent'] = userAgent

        response = self._request(url, headers, byteRequest=body)
        if response:
            oresponse = json.loads(response)
            if oresponse and 'repositoryUris' in oresponse and isinstance(oresponse['repositoryUris'], list):
                m = re.search(self._reJsonRespRepoId, oresponse['repositoryUris'][0])
                if m:
                    repoId = m.group('repoId')
                    if repoId:
                        def checkStatus():
                            content_items = self.repository_content(repoId, relativePath)
                            if content_items is None:
                                return None

                            for filename in filesTocheck:
                                for content_item in content_items:
                                    if 'text' in content_item and content_item['text'] == filename:
                                        break
                                else:
                                    return 404

                            return 200

                        def isStatusValid(status):
                            if status == 200:
                                log.info('\tthe bundle is available on Nexus')
                                return 0
                            if status is None:
                                log.error('\tcannot check if bundle is available on Nexus')
                                return 1
                            log.warning('\tthe bundle is not fully uploaded yet... Nexus still working resource respond {}'.format(status))
                            return 2

                        if self._requestManyTimes(checkStatus, isStatusValid, cbLogMessage=lambda tryNumber: log.info('\ttry {} to check if bundle is uploaded on nexus'.format(tryNumber))):
                            log.info('bundle uploaded in staging repository {}'.format(repoId))
                            return m.group('repoId')

        log.error('fail to upload bundle in new staging repository')
        return None

    def _formbased_post_file(self, url, httpHeaders, fileUploadHandle, returnOnlyHttpCode=True):
        o = urlparse(url)

        if not httpHeaders:
            httpHeaders = {}
        httpHeaders['Content-Length'] = os.fstat(fileUploadHandle.fileno()).st_size

        try:
            conn = httplib.HTTPConnection(o.hostname, o.port, timeout=1800) if o.scheme == 'http' else httplib.HTTPSConnection(o.hostname, o.port, context=ssl._create_unverified_context(), timeout=1800)
            conn.set_debuglevel(1 if self._debugActivated else 0)
            conn.putrequest('POST', o.path)

            if self._username is not None:
                userAndPass = base64.standard_b64encode(self._username+':'+self._password).decode('ascii')
                conn.putheader('Authorization', 'Basic %s' % userAndPass)

            for key in httpHeaders:
                conn.putheader(key, httpHeaders[key])

            conn.endheaders()

            fileUploadHandle.seek(0)
            while 1:
                filebytes = fileUploadHandle.read(1024)
                if not filebytes:
                    break
                conn.send(filebytes)
                conn.set_debuglevel(0) # Only print the first packet, no need to dump all the upload otherwise it will generate a too much big log ! (DTXMAKE-1149)

            conn.set_debuglevel(1 if self._debugActivated else 0) # re-enable answer if in debug as was disabled after the first packet sent not to generate a to big log (DTXMAKE-1149)
            resp = conn.getresponse()
            if resp.status >= 400:
                strExtendedError = resp.read()
                if strExtendedError is not None:
                    log.error(strExtendedError)
                if returnOnlyHttpCode:
                    conn.close()
                    return resp.status
            conn.close()
            return resp.status
        except Exception as e:
            log.error('_formbased_post_file catched Exception: '+str(e))
            return None

        return None

    def deployByRepositoryId(self, stagedRepositoryId, artifact, userAgent=None):
        '''
            Handles the upload of file.
        '''

        url = '{}/deployByRepositoryId/{}/{}'.format(self._restApiUrl, stagedRepositoryId, artifact['relpath'].replace('\\', '/'))
        log.info('DEPLOY local file {} in staging repository {} to {}'.format(artifact['filename'], stagedRepositoryId, url))
        form = MultiPartForm()
        f = open(artifact['path'], 'rb')
        form.add_file_handle('file', artifact['filename'], fileHandle=f)
        fileUploadHandle = form.file()
        f.close()

        headers = {}
        headers['Content-Type'] = form.get_content_type()
        if userAgent:
            headers['User-Agent'] = userAgent

        def uploadRequest():
            return self._formbased_post_file(url, headers, fileUploadHandle, returnOnlyHttpCode=True)

        def uploadStatus(status):
            if status >= 200 and status < 400:
                log.info('\tthe deploy request was received by Nexus http {}'.format(status))
                return 0

            if status == 400:
                log.info('\tthe deploy request failed. Nexus returned http {}'.format(status))
                return 2

            if status > 400:
                log.info('\tthe deploy request failed. Nexus returned http {}'.format(status))
                return 1

            log.error('\tcannot check if upload is correctly executed on Nexus')
            return 2

        def uploadRetryLog(tryNumber):
            log.info('\ttry {} to deploy on nexus'.format(tryNumber))

        if self._requestManyTimes(uploadRequest, uploadStatus, nbTry=tuning.DEPLOY_FILE_REQ_ATTEMPTS, waitSecond=tuning.DEPLOY_FILE_DELAY_BETWEEN_REQ_ATTEMPTS, cbLogMessage=uploadRetryLog):
            def checkStatus():
                return self.repository_content(stagedRepositoryId, artifact['relpath'].replace(artifact['filename'], ''))

            def isStatusValid(content_items):
                if content_items is None:
                    log.error('\tcannot check if file is available on Nexus')
                    return 1

                for content_item in content_items:
                    if 'text' in content_item and content_item['text'] == artifact['filename']:
                        log.info('\tthe file is available on Nexus')
                        return 0

                log.warning('\tthe file is not fully uploaded yet... Nexus still working')
                return 2

            if self._requestManyTimes(checkStatus, isStatusValid, cbLogMessage=lambda tryNumber: log.info('\ttry {} to check if file is uploaded on nexus'.format(tryNumber))):
                log.info('file {} deployed in staging repository {}'.format(artifact['filename'], stagedRepositoryId))
                fileUploadHandle.close()
                return True

#         if response:
#             log.error(response)

        log.error('fail to deploy file {} in staging repository {}'.format(artifact['filename'], stagedRepositoryId))
        fileUploadHandle.close()
        return False

    def getrepositorystatus(self, stagedRepositoryId, userAgent=None):
        '''
            Gets the status of staged repository.
        '''

        url = '{}/repository/{}'.format(self._restApiUrl, stagedRepositoryId)
        headers = {}
        headers['Cache-Control'] = 'no-cache'
        if userAgent:
            headers['User-Agent'] = userAgent

        response = self._request(url, headers)
        if not response:
            return None

        xmlResponse = ET.fromstring(response)
        oresponse = {}
        oresponse['profileId'] = xmlResponse.find('profileId').text
        oresponse['profileName'] = xmlResponse.find('profileName').text
        oresponse['profileType'] = xmlResponse.find('profileType').text
        oresponse['repositoryId'] = xmlResponse.find('repositoryId').text
        oresponse['type'] = xmlResponse.find('type').text
        oresponse['policy'] = xmlResponse.find('policy').text
        oresponse['userId'] = xmlResponse.find('userId').text
        oresponse['userAgent'] = xmlResponse.find('userAgent').text
        oresponse['ipAddress'] = xmlResponse.find('ipAddress').text
        oresponse['repositoryURI'] = xmlResponse.find('repositoryURI').text
        oresponse['created'] = xmlResponse.find('created').text
        oresponse['createdDate'] = xmlResponse.find('createdDate').text
        oresponse['createdTimestamp'] = xmlResponse.find('createdTimestamp').text
        oresponse['updated'] = xmlResponse.find('updated').text
        oresponse['updatedDate'] = xmlResponse.find('updatedDate').text
        oresponse['updatedTimestamp'] = xmlResponse.find('updatedTimestamp').text
        oresponse['description'] = xmlResponse.find('description').text
        oresponse['provider'] = xmlResponse.find('provider').text
        oresponse['releaseRepositoryId'] = xmlResponse.find('releaseRepositoryId').text
        oresponse['releaseRepositoryName'] = xmlResponse.find('releaseRepositoryName').text
        oresponse['notifications'] = xmlResponse.find('notifications').text
        oresponse['transitioning'] = xmlResponse.find('transitioning').text

        return oresponse

    def activity(self, stagedRepositoryId):
        '''
            Get the activity by action step (open, closed, promoted)
        '''
        url = '{}/repository/{}/activity'.format(self._restApiUrl, stagedRepositoryId)
        headers = {}
        headers['Cache-Control'] = 'no-cache'

        response = self._request(url, headers)
        if not response:
            return None

        xmlResponse = ET.fromstring(response)
        activities = []
        for stagingActivity in xmlResponse.iter('stagingActivity'):
            activity = {}

            activity['name'] = self._htmlParser.unescape(stagingActivity.find('name').text).encode('ascii', 'ignore')
            activity['started'] = self._htmlParser.unescape(stagingActivity.find('started').text).encode('ascii', 'ignore')
            activityStopped = stagingActivity.find('stopped')
            if activityStopped is not None:
                activity['stopped'] = self._htmlParser.unescape(activityStopped.text).encode('ascii', 'ignore')
            else:
                activity['stopped'] = 'never'

            activity['events'] = []
            for stagingActivityEvent in stagingActivity.find('events').iter('stagingActivityEvent'):
                event = {}
                event['timestamp'] = stagingActivityEvent.find('timestamp').text
                event['name'] = self._htmlParser.unescape(stagingActivityEvent.find('name').text).encode('ascii', 'ignore')
                event['severity'] = self._htmlParser.unescape(stagingActivityEvent.find('severity').text).encode('ascii', 'ignore')
                event['properties'] = []
                for stagingProperty in stagingActivityEvent.find('properties').iter('stagingProperty'):
                    property = {}
                    property['name'] = self._htmlParser.unescape(stagingProperty.find('name').text).encode('ascii', 'ignore')
                    property['value'] = self._htmlParser.unescape(stagingProperty.find('value').text).encode('ascii', 'ignore')
                    event['properties'].append(property)

                activity['events'].append(event)

            activities.append(activity)

        return activities

    def repository_content(self, stagedRepositoryId, relpath):
        url = '{}/deployByRepositoryId/{}/{}'.format(self._restApiUrl, stagedRepositoryId, relpath.replace('\\', '/'))
        headers = {}
        headers['Cache-Control'] = 'no-cache'

        response = self._request(url, headers)
        if not response:
            return None

        xmlResponse = ET.fromstring(response)
        content_items = []
        for contentItem in xmlResponse.iter('content-item'):
            content_item = {}
            content_item['resourceURI'] = contentItem.find('resourceURI').text
            content_item['relativePath'] = contentItem.find('relativePath').text
            content_item['text'] = contentItem.find('text').text
            content_item['leaf'] = True if contentItem.find('leaf').text.lower() == 'true' else False
            content_item['lastModified'] = contentItem.find('lastModified').text
            content_item['sizeOnDisk'] = contentItem.find('sizeOnDisk').text
            content_items.append(content_item)

        return content_items

    def getFilteredRepos(self, scm,  version, scm_equals, *types):
        '''
            Search repositories applying given filters.
        '''
        all_repos = self._getAllRepos()

        log.info('fetching all repositories...')
        log.info('found {} repositories'.format(len(all_repos)))
        log.info('filtering by profileId --> {} '.format(self._profileId))
        log.info('filtering by status --> {}'.format(types))
        if scm_equals:
            log.info('filtering by scm --> {} '.format(scm))
        else:
            log.info('filtering by scm starts with  --> {} '.format(scm))
        log.info('filtering by version  --> {} '.format(version))

        filtered_repoIds = []

        # Filter repositories
        mandatoryKeys = ('profileId', 'type', 'userAgent')
        for dict_elem in all_repos:
            if not set(mandatoryKeys).issubset(dict_elem):
                continue
            try:
                tab = json.loads(dict_elem['userAgent'], 'utf-8')
                mandatoryUAKeys = ('version', 'scm')
                if not set(mandatoryUAKeys).issubset(tab):
                    continue
            except ValueError as err:
                log.warning('problem reading user-agent \'{}\' for staging repo \'{}\'. {} '.format(dict_elem['userAgent'], dict_elem['repositoryId'], err))
                continue

            if dict_elem['profileId'] == self._profileId and tab['version'] == version and ((tab['scm'] == scm) if scm_equals else ('scm' in tab and tab['scm'] and tab['scm'].startswith(scm))):
                for type in types:
                    if dict_elem['type'] == type:
                        filtered_repoIds.append(dict_elem['repositoryId'])

        log.info('after filter found {} repositorie(s)'.format(len(filtered_repoIds)))
        return filtered_repoIds

    def _getAllRepos(self):
        '''
            Fetch all repositories
        '''

        url = '{}/{}'.format(self._restApiUrl, 'profile_repositories')

        headers = {}
        headers['Cache-Control'] = 'no-cache'

        response = self._request(url, headers)
        repo_list = []
        if response:
            root = ET.fromstring(response)
            for stagingProfileRepository in root.iter('stagingProfileRepository'):
                repos_ua = dict()
                repos_ua['userAgent'] = stagingProfileRepository.find('userAgent').text
                repos_ua['repositoryId'] = stagingProfileRepository.find('repositoryId').text
                repos_ua['profileId'] = stagingProfileRepository.find('profileId').text
                repos_ua['type'] = stagingProfileRepository.find('type').text
                repo_list.append(repos_ua)

        return repo_list

    def _logActivityForStep(self, stagedRepositoryId):
        logMessages = None
        activities = self.activity(stagedRepositoryId)
        for activity in activities:
            for event in activity['events']:
                if event['severity'] != '0':
                    if not logMessages:
                        logMessages = {}
                    if activity['name'] not in logMessages:
                        logMessages[activity['name']] = []
                    logMessages[activity['name']].append('event: {}'.format(event['name']))
                    for property in event['properties']:
                        logMessages[activity['name']].append('\t{}: {}'.format(property['name'], property['value']))

        if logMessages:
            log.error('\terror on nexus server')
            for step in logMessages:
                log.error('\t> on {}'.format(step))
                log.error('\t' + '-' * 80)
                for logMessage in logMessages[step]:
                    log.error('\t' + logMessage)
                log.error('\t' + '-' * 80)
        else:
            log.info('\tno issue found on nexus server')

    def _request(self, url, httpHeaders=None, httpMethod=None, byteRequest=None, returnOnlyHttpCode=False):
        '''
            Does the http request.
        '''

        if byteRequest:
            request = urllib2.Request(url, data=byteRequest)
            if (httpHeaders is None or 'Content-Length' not in httpHeaders):
                if not httpHeaders:
                    httpHeaders = {}
                httpHeaders['Content-Length'] = '{}'.format(len(byteRequest))
        else:
            request = urllib2.Request(url)

        if httpHeaders:
            for key in httpHeaders:
                request.add_header(key, httpHeaders[key])

        if self._username is not None:
            userAndPass = base64.standard_b64encode(self._username+':'+self._password).decode('ascii')
            request.add_header('Authorization', 'Basic %s' % userAndPass)

        if httpMethod:
            request.get_method = lambda: httpMethod

        def logRequest():
            if httpMethod is None:
                if byteRequest is None:
                    log.debug('HTTP request GET {}'.format(url))
                else:
                    log.debug('HTTP request POST {}'.format(url))
            else:
                log.debug('HTTP request {} {}'.format(httpMethod, url))

            if httpHeaders:
                log.debug('http headers')
                strHeaders = ''
                for k, v in request.header_items():
                    # hide Authorization value
                    if k.startswith('Authorization'):
                        strHeaders += '{0}: {1}\r\n\t'.format(k, "**********")
                    else:
                        strHeaders += '{0}: {1}\r\n\t'.format(k, v)
                log.debug('size of headers {} bytes'.format(sys.getsizeof(strHeaders)))
                log.debug(strHeaders)

            log.debug('http request')

            if byteRequest:
                if len(byteRequest) < 1000:
                    log.debug(byteRequest)
                else:
                    log.debug('{}...'.format(byteRequest[:100]))

        try:
            logRequest()
            handler = self._opener.open(request, timeout=1800)
            response = handler.read()
            httpcode = handler.getcode()
        except urllib2.HTTPError, e:
            log.error(e)
            strError = e.read()
            if strError is not None:
                log.error(strError)

            if returnOnlyHttpCode:
                return e.getcode()

            return None
        except (urllib2.URLError, httplib.BadStatusLine), e:
            log.error(e)
            return None

        if returnOnlyHttpCode:
            return httpcode

        return response

    def _requestManyTimes(self, cbRequest, cbValidateCondition, nbTry=tuning.REQ_ATTEMPTS, waitSecond=tuning.DELAY_BETWEEN_REQ_ATTEMPTS, cbLogMessage=None):
        '''
            Invokes an http request multiple times.
            Sample of execution:
            if the number of attemp is 5 and delay between requests is 60s
            attempt#1
                send the request and return if rc is 0 or 1
                wait 1*60=60s
            attempt#2
                send the request and return if rc is 0 or 1
                wait 2*60=120s
            attempt#3
                send the request and return if rc is 0 or 1
                wait 3*60=180s
            attempt#4
                send the request and return if rc is 0 or 1
                wait 4*60=240s
            attempt#5
                send the request and return if rc is 0 or 1
        '''

        for i in range(1, nbTry + 1):  # [1,2,...,nbTry]
            if cbLogMessage:
                cbLogMessage(i)

            response = cbRequest()

            rc = cbValidateCondition(response)
            if rc == 0:
                return True
            if rc == 1:
                return False

            if i < nbTry:
                totalWaitSecond = waitSecond*i
                log.info('\tplease wait next attempt in {} seconds'.format(totalWaitSecond))
                time.sleep(totalWaitSecond)

        return False

    def _buildRequest(self, data):
        xmlData = []
        for key in data:
            xmlData.append('<{0}>{1}</{0}>'.format(key, escape(data[key])))

        return '''<promoteRequest>
    <data>
        {}
    </data>
</promoteRequest>'''.format('\n\t\t'.join(xmlData))
