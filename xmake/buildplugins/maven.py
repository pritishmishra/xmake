'''
Created on 27.03.2015

@author: I050906, I051432, I079877, I051375
'''
import log
import os
import xml.etree.ElementTree as ET
import inst
import re
import shlex
import urlparse
import urllib
import shutil
import tempfile
from artifact import Artifact
from string import Template
from ExternalTools import OS_Utils
from os.path import join
from xmake_exceptions import XmakeException
from spi import JavaBuildPlugin


class build(JavaBuildPlugin):
    '''
        Xmake maven plugin class that provides the ability to build maven project
    '''
    RESERVED_OPTIONS = ('validate', 'compile', 'test', 'package', 'integration-test', 'verify', 'install', 'deploy')

    ###############################################################################
    #  PLUGIN initialization
    ###############################################################################
    def __init__(self, build_cfg):
        JavaBuildPlugin.__init__(self, build_cfg)
        self._maven_version = '3.3.1'
        self._fortify_plugin_version = '1.7.0'
        self._tycho_set_version_version = '0.23.1'
        self._m2_home = ''
        self._maven_cmd = ''
        self._maven_settings_noproxy = None
        self._ldi_metadata = False
        self._maven_settings_xml_file = ''
        self._maven_jvm_options = []
        self._maven_user_options = []
        self._maven_depencies = []
        self._maven_build_dependencies_file = ''
        self._maven_repository_dir = ''
        self._maven_installed_files = []
        self._localDeploymentPath = join(self.build_cfg.temp_dir(), 'localDeployment')
        self._ads = join(self.build_cfg.temp_dir(), 'export.ads')
        self._copied_src_dir = join(self.build_cfg.temp_dir(), 'src')
        self._relative_pom_path = self.build_cfg.alternate_path()

        self._profilings = self.build_cfg.profilings()
        if self._profilings is None:
            self._do_build = True
            self._do_fortify_build = False
        elif len(self._profilings) == 1 and ('FORTIFY' in self._profilings or 'fortify' in self._profilings):
            self._do_build = False
            self._do_fortify_build = True
            self.build_cfg.set_custom_deploy(True)
        else:
            self._do_build = False
            self._do_fortify_build = False

        # Take in account arguments after the --
        # All these arguments will be passed to the mvn command
        if self.build_cfg.build_args():
            for arg in self.build_cfg.build_args():
                log.info('  using custom option ' + arg)
                if arg not in build.RESERVED_OPTIONS:
                    self._maven_user_options.append(arg)
                else:
                    log.warning('  ignoring custom option {}. Only xmake can manage this option.'.format(arg))

        self.build_cfg.set_export_script(self._ads)

    def java_set_option(self, o, v):
        if o == 'maven-version' or o == 'version':
            log.info('  using maven version ' + v)
            self._maven_version = v
        elif o == 'fortify-plugin-version':
            log.info('  using fortify-plugin version ' + v)
            self._fortify_plugin_version = v
        elif o == 'ldi-metadata':
            self._ldi_metadata = v and v.lower() in ('true', 'y', 'yes')
            if self._ldi_metadata:
                log.info('  using ldi-metadata={}. leandi metadata enabled'.format(self._ldi_metadata))
            else:
                log.info('  using ldi-metadata={}. leandi metadata disabled'.format(self._ldi_metadata))
        elif o == 'noproxy':
            self._maven_settings_noproxy = v and v.lower() in ('true', 'y', 'yes')
            if self._maven_settings_noproxy:
                log.info('  using noproxy={}. Proxy setting will be deactivated in settings.xml'.format(self._maven_settings_noproxy))
            else:
                log.info('  using noproxy={}. Proxy setting will be activated in settings.xml'.format(self._maven_settings_noproxy))
        elif o == 'options':
            values = v.split(',')
            for value in values:
                log.info('  using custom option ' + value)
                if value not in build.RESERVED_OPTIONS:
                    self._maven_user_options.append(value)
                else:
                    log.warning('  ignoring custom option {}. Only xmake can manage this option.'.format(value))
        elif o == 'tycho-setversion-version':
            log.info('  using tycho plugins version ' + v + ' for setting pom.xml(s) version(s)')
            self._tycho_set_version_version = v
        else:
            if o is not None:
                v = '%s=%s' % (o, v)  # does not correspond to one of the option above remangle it as originally splitted by JavaBuildPlugin if it was containing an equal char
            log.info('  using custom option ' + v)
            self._maven_user_options.append(v)

    def java_required_tool_versions(self):
        return {'maven': self._maven_version}

    def variant_cosy_gav(self):
        return None

    ###############################################################################
    #  XMAKE phase callbacks
    ###############################################################################
    def after_IMPORT(self, build_cfg):

        self.java_set_environment(True)
        # Setup maven
        self._setup()

        # If set-version option is on
        if build_cfg.get_next_version() is not None:
            self._set_version_in_pom(build_cfg.get_next_version(), build_cfg.component_dir())
            # Always copy src see BESTL-8640 Related to Cloud Foundry deployment
            self._copy_src_dir_to(self._copied_src_dir)

        elif build_cfg.base_version() == 'NONE':
            # Always copy src see BESTL-8640 Related to Cloud Foundry deployment
            self._copy_src_dir_to(self._copied_src_dir)
            self._get_version_from_effective_pom()

        # If get-version option is on
        if build_cfg.get_project_version() is True:

            status = self._check_project_version_compliance()
            if status[0] is False:
                raise XmakeException(status[1])
            else:

                stripped_version = self._remove_leading_zero(self.build_cfg.base_version())
                self.build_cfg.set_base_version(stripped_version)

                log.info('write project version {} in {}'.format(self.build_cfg.base_version(), self.build_cfg.project_version_file()))
                with open(self.build_cfg.project_version_file(), 'w') as f:
                    f.write(self.build_cfg.base_version())

    def after_BUILD(self, build_cfg):
        # Generate ads file before the export phase
        if not os.path.exists(build_cfg.export_script()):
            log.info('building artifact deployer script (ads file)')
            self._generate_ads_file()
            log.info('artifact deployer script generated')

    def after_DEPLOY(self, build_cfg):
        # custom deployment
        if self._do_fortify_build and self.build_cfg.do_deploy():
            self._fortifyDeploy()

    ###############################################################################
    #  XMAKE build phase & prepare deployment
    ###############################################################################
    def java_run(self):
        '''
            Callback invoked by xmake to execute the build phase
        '''

        self._clean_if_requested()

        if self._do_build:
            self._build()
        elif self._do_fortify_build:
            self._fortifyBuild()
        else:
            raise XmakeException('one of these profilings: "{}" is not supported'.format(','.join(self._profilings)))

    ###############################################################################
    #  Setup maven files, environment variables
    ###############################################################################
    def _setup(self):
        '''
            Setup all the attributes of the class
        '''

        self._m2_home = self.build_cfg.tools()['maven'][self._maven_version]
        self._maven_cmd = self._find_maven_executable()
        self._user_home_dir = join(self.build_cfg.temp_dir(), 'user.home')
        self._dotm2_dir = join(self._user_home_dir, '.m2')
        self._maven_settings_xml_file = join(self._dotm2_dir, 'settings.xml')
        self._maven_jvm_options = ['-Djavax.net.ssl.trustStore='+join(inst.get_installation_dir(), 'xmake', 'template', 'maven', 'keystore'),
                                   '-Dmaven.wagon.http.ssl.insecure=true',  # Use keystore because these two VM options have no effect on maven...
                                   '-Dmaven.wagon.http.ssl.allowall=true']  # Also tried to use maven_jvm_opS but no effect as well
        self._maven_build_dependencies_file = join(self.build_cfg.temp_dir(), 'dependencies')
        self._maven_repository_dir = join(self.build_cfg.temp_dir(), 'repository')
        self._setup_settings_xml()
        self.java_exec_env.env['VERSION'] = self.build_cfg.base_version()
        self.java_exec_env.env['REPOSITORY'] = self._maven_repository_dir
        self.java_exec_env.env['MAVEN_OPTS'] = (self.java_exec_env.env['MAVEN_OPTS']+' ' if 'MAVEN_OPTS' in self.java_exec_env.env else '')+'-Duser.home='+self._user_home_dir+' -Dmaven.repo.local='+self._maven_repository_dir
        self.java_exec_env.env['HOME'] = self._user_home_dir

        if self._m2_home:
            self.java_exec_env.env['M2_HOME'] = self._m2_home

            m2_bin = os.path.join(self._m2_home, 'bin')
            path = self.java_exec_env.env['PATH']
            if path is None:
                self.java_exec_env.env['PATH'] = m2_bin
            elif path.find(m2_bin) < 0:
                self.java_exec_env.env['PATH'] = os.pathsep.join([m2_bin, path])

    def _setup_settings_xml(self):
        '''
            Build a custom settings.xml file from a template located in [install_dir]/xmake/template/maven/settings.xml
            Mainly two fields are customized:
             - localRepository
             - mirrors: adding <mirror> one per import repository
            This new file is saved into [component_dir]/gen/tmp/settings.xml
        '''

        # Add xml namespaces
        ET.register_namespace('', 'http://maven.apache.org/SETTINGS/1.0.0')
        ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        ET.register_namespace('xsi:schemaLocation', 'http://maven.apache.org/SETTINGS/1.0.0 http://maven.apache.org/xsd/settings-1.0.0.xsd')

        # Parse template/settings.xml
        templateSettingsXmlFile = join(inst.get_installation_dir(), 'xmake', 'template', 'maven', 'settings.xml')
        xmlSettingsContent = ''
        with open(templateSettingsXmlFile, 'r') as f:
            xmlSettingsContent = f.read()

        xmlSettingsContent = Template(xmlSettingsContent).substitute(
            proxyactivated='false' if self._maven_settings_noproxy else 'true', 
            mavensettingsxml=self._maven_settings_xml_file)

        tree = ET.fromstring(xmlSettingsContent)
        if tree is None:
            raise XmakeException('cannot generate specific settings.xml for maven')

        # Search fileds to update
        namespace = '{http://maven.apache.org/SETTINGS/1.0.0}'
        localRepository = tree.find('./{}localRepository'.format(namespace))
        mirrorsUrl = tree.find('./{0}mirrors'.format(namespace))
        sonarproperties = tree.find('./{0}profiles/{0}profile[{0}id="sonar"]/{0}properties'.format(namespace))
        sonarjdbcurl = sonarproperties.find('{0}sonar.jdbc.url'.format(namespace))
        sonarjdbcdriver = sonarproperties.find('{0}sonar.jdbc.driver'.format(namespace))
        sonarjdbcusername = sonarproperties.find('{0}sonar.jdbc.username'.format(namespace))
        sonarjdbcpassword = sonarproperties.find('{0}sonar.jdbc.password'.format(namespace))
        sonarhosturl = sonarproperties.find('{0}sonar.host.url'.format(namespace))
        repos = tree.find('./{0}profiles/{0}profile[{0}id="customized.repo"]/{0}repositories'.format(namespace))
        pluginrepositoryListUrl = tree.find('./{0}profiles/{0}profile[{0}id="customized.repo"]/{0}pluginRepositories'.format(namespace))

        if localRepository is None and mirrorsUrl is None:
            raise XmakeException('cannot generate specific settings.xml for maven')

        # Add specific fields
        localRepository.text = self._maven_repository_dir

        if self.build_cfg.is_release() is None:
            i = 1
            for repo in self.build_cfg.import_repos():
                pluginrepository = ET.SubElement(pluginrepositoryListUrl, 'pluginRepository')
                ET.SubElement(pluginrepository, 'id').text = 'repo%d' % i \
                    if i < len(self.build_cfg.import_repos()) else "central"
                ET.SubElement(pluginrepository, 'url').text = repo
                snapshots = ET.SubElement(pluginrepository, 'snapshots')
                ET.SubElement(snapshots, 'enabled').text = 'true'
                i += 1

        i = 1
        for import_repo in self.build_cfg.import_repos():
            additional_mirror = ET.SubElement(mirrorsUrl, 'mirror')
            ET.SubElement(additional_mirror, 'id').text = 'mirror%d' % i
            ET.SubElement(additional_mirror, 'url').text = import_repo
            ET.SubElement(additional_mirror, 'mirrorOf').text = 'repo%d' % i \
                if i < len(self.build_cfg.import_repos()) else "central"
            i += 1

        i = 1
        for repo in self.build_cfg.import_repos():
            additional_repo = ET.SubElement(repos, 'repository')
            ET.SubElement(additional_repo, 'id').text = 'repo%d' % i \
                if i < len(self.build_cfg.import_repos()) else "central"
            ET.SubElement(additional_repo, 'url').text = repo
            i += 1

        # sonar properties
        jdbcurl = os.getenv('SONAR_JDBC_URL')  # jdbc:mysql://ldisonarci.wdf.sap.corp:3306/sonar?useUnicode=true&characterEncoding=utf8
        jdbcdriver = os.getenv('SONAR_JDBC_DRIVER')  # com.mysql.jdbc.Driver
        jdbcusername = os.getenv('SONAR_JDBC_USERNAME')  # sonar
        jdbcpassword = os.getenv('SONAR_JDBC_PASSWORD')  # sonar
        hosturl = os.getenv('SONAR_HOST_URL')  # http://ldisonarci.wdf.sap.corp:8080/sonar

        logWarnings = []

        # Check server utl is set
        if jdbcurl is None:
            logWarnings.append('jdbc url is not set for sonar. Please set env SONAR_JDBC_URL')
        if jdbcdriver is None:
            logWarnings.append('jdbc driver is not set for sonar. Please set env SONAR_JDBC_DRIVER')
        if jdbcusername is None:
            logWarnings.append('jdbc username is not set for sonar. Please set env SONAR_JDBC_USERNAME')
        if jdbcpassword is None:
            logWarnings.append('jdbc password is not set for sona. Please set env SONAR_JDBC_PASSWORD')
        if hosturl is None:
            logWarnings.append('sonar host url is not set. Please set env SONAR_HOST_URL')

        if len(logWarnings) > 0:
            for logWarning in logWarnings:
                log.warning(logWarning, log.INFRA)
        else:
            sonarjdbcurl.text = jdbcurl
            sonarjdbcdriver.text = jdbcdriver
            sonarjdbcusername.text = jdbcusername
            sonarjdbcpassword.text = jdbcpassword
            sonarhosturl.text = hosturl

        # Write settings.xml in component/tmp directory
        log.info('write maven settings in ' + self._maven_settings_xml_file)
        if not os.path.isdir(self._dotm2_dir):
            os.makedirs(self._dotm2_dir)
        with open(self._maven_settings_xml_file, 'w') as f:
            f.write(ET.tostring(tree))

    def _find_maven_executable(self):
        '''
            Find the mvn command path according to the operating system
        '''

        if OS_Utils.is_UNIX():
            path = join(self._m2_home, 'bin', 'mvn')
        else:
            path = join(self._m2_home, 'bin', 'mvn.cmd')
            if not os.path.isfile(path):
                path = join(self._m2_home, 'bin', 'mvn.bat')
        return path

    def _mvn(self, args, fromdir=None):
        '''
            Shortcut to invoke the maven executable
        '''

        if fromdir is None:
            fromdir = self._copied_src_dir

        maven_args = [self._maven_cmd]
        maven_args.extend(args)
        if self._relative_pom_path is not None:
            maven_args.extend(['-f', join(self._relative_pom_path, 'pom.xml')])  # use alternate pom file given by project portal
        maven_args.append('-B')  # in non-interactive (batch)
        maven_args.append('-e')  # Produce execution error messages
        maven_args.extend(['-settings', self._maven_settings_xml_file])
        maven_args.extend(self._maven_jvm_options)

        # manage ldi variables
        if self.build_cfg.is_release() == 'direct-shipment' or self.build_cfg.is_release() == 'indirect-shipment':
            maven_args.append('-Dldi.releaseBuild=true')
            maven_args.append('-Dldi.releaseType=customer')
        elif self.build_cfg.is_release() == 'milestone':
            maven_args.append('-Dldi.releaseBuild=true')
            maven_args.append('-Dldi.releaseType=milestone')

        log.info('from dir:', fromdir)
        log.info('invoking maven: {}'.format(' '.join(self._hide_password_in_maven_args_for_log(maven_args))))
        if self.java_exec_env.env['MAVEN_OPTS']:
            log.info('MAVEN_OPTS environment variable is:', self.java_exec_env.env['MAVEN_OPTS'])
        cwd = os.getcwd()
        try:
            os.chdir(fromdir)
            rc = self.java_exec_env.log_execute(maven_args)
            if rc > 0:
                raise XmakeException('maven returned %s' % str(rc))
        finally:
            os.chdir(cwd)

    def _get_version_from_effective_pom(self):
        '''
            Compute maven effective pom to find the version of the project
        '''

        maven_args = ['help:effective-pom', '-Dtycho.mode=maven', '-Doutput={}{}effective-pom.xml'.format(self.build_cfg.temp_dir(), os.sep)]

        self._mvn(maven_args)

        f = join(self.build_cfg.temp_dir(), 'effective-pom.xml')
        pom = ET.parse(f)
        root = pom.getroot()
        if root.tag is None:
            raise XmakeException('version entry not found in effective-pom xml')

        namespace = '{http://maven.apache.org/POM/4.0.0}'
        group = None
        artifact = None
        version = None
        tag = root.tag.split('}', 1)[-1]
        if tag == 'project':
            group = pom.find('{}groupId'.format(namespace))
            artifact = pom.find('{}artifactId'.format(namespace))
            version = pom.find('{}version'.format(namespace))
        elif tag == 'projects':
            group = pom.find('{0}project/{0}groupId'.format(namespace))
            artifact = pom.find('{0}project/{0}artifactId'.format(namespace))
            version = pom.find('{0}project/{0}version'.format(namespace))

        if not (version is None or group is None or artifact is None):
            strippedVersion = re.sub(r'\-(?i)(SNAPSHOT|RELEASE|MILESTONE)$', '', version.text)
            log.info('version after cleaning redundant suffixe: ' + strippedVersion)
            self.build_cfg.set_base_version(strippedVersion)
            if self.build_cfg.version_suffix():
                self.build_cfg.set_version('{}-{}'.format(strippedVersion, self.build_cfg.version_suffix()))
            else:
                self.build_cfg.set_version(strippedVersion)
            self.build_cfg.set_base_group(group.text)
            self.build_cfg.set_base_artifact(artifact.text)
        else:
            raise XmakeException('group, artifact or version entry not found in effective-pom xml')

    def _set_version_in_pom(self, version, fromdir=None):
        '''
            Set the given version to the project poms
        '''

        maven_args = ['org.eclipse.tycho:tycho-versions-plugin:{}:set-version'.format(self._tycho_set_version_version), '-Dtycho.mode=maven', '-DnewVersion={}'.format(version), '-Dldi.tycho-parent.tycho-version={}'.format(self._tycho_set_version_version)]
        self._mvn(maven_args, fromdir=fromdir)

    def _run_metadata_quality_check(self, *qualtity_check_config):
        '''
            During the release build, the metadata-quality-report plugin is used to perform certain checks on the project
        '''
        maven_args = []
        maven_args.append('com.sap.ldi:metadata-quality-report:1.18.0:check')
        maven_args.append('-Dmetadata-quality-report.dependencies=com.sap.prd.xmake:mqr-config:2.35.0')
        maven_args.append('-Dtycho.mode=maven')
        for arg in qualtity_check_config:
            maven_args.append(arg)

        self._mvn(maven_args)

    def _store_ldi_metadata(self):
        releaseMetadataFile = self._copied_src_dir
        if self._relative_pom_path is not None:
            releaseMetadataFile = join(releaseMetadataFile, self._relative_pom_path)  # use alternate pom file given by project portal
        releaseMetadataFile = join(releaseMetadataFile, 'target/com.sap.ldi.releasemetadata/leandi/releaseMetadata.xml')

        v = self.required_tool_versions()

        self._mvn(['com.sap.ldi.releasetools:release-metadata:scan', '-Dtycho.mode=maven'])
        self._mvn(['com.sap.ldi.releasetools:release-metadata:generate-module-metadata', '-DmavenVersion='+v['maven']])

        mavenGav = self.build_cfg.tools()['maven'].imports(v['maven'])[0] if self.build_cfg.tools()['maven'].imports(v['maven']) else 'org.apache.maven:apache-maven:zip:bin:'+v['maven']
        jdkGav = self.build_cfg.tools()['java'].imports(v['java'])[0] if self.build_cfg.tools()['java'].imports(v['java']) else 'org.apache.maven:apache-maven:zip:bin:'+v['java']
        workspace = os.getenv('WORKSPACE') if os.getenv('WORKSPACE') else '.'
        releaseBuildType = 'milestone' if self.build_cfg.is_release() == 'milestone' else 'customer'
        releaseUser = os.getenv('BUILD_USER_ID') if os.getenv('BUILD_USER_ID') else ''
        projectPortalUUID = os.getenv('BUILD_PP_UUID') if os.getenv('BUILD_PP_UUID') else ''
        treeish = ''
        scm_snapshot_url = self.build_cfg.scm_snapshot_url() if self.build_cfg.scm_snapshot_url() else ''
        if scm_snapshot_url:
            splitted_scm_snapshot_url = scm_snapshot_url.split('@')
            tokens = splitted_scm_snapshot_url[:-1]
            if tokens:
                scm_snapshot_url = '@'.join(tokens)
                treeish = splitted_scm_snapshot_url[1]
        ''' mvn com.sap.ldi.releasetools:release-metadata:generate -DscmUrl=scmUrl -Dworkspace=. -DjdkGav=com.oracle.download.java:jdk:1.8.0_66-sap-01 -DmavenGav=org.apache:maven:3.3.3 -DscmRevision=scmRevision  -DreleaseBuildType=customer -DreleaseUser=i051432 -Dldi.projectUuid=dddd
        '''
        self._mvn([
            'com.sap.ldi.releasetools:release-metadata:generate',
            '-Dtycho.mode=maven',
            '-DscmUrl='+scm_snapshot_url,
            '-Dworkspace='+workspace,
            '-DjdkGav='+jdkGav,
            '-DmavenGav='+mavenGav,
            '-DscmRevision='+treeish,
            '-DreleaseBuildType='+releaseBuildType,
            '-DreleaseUser='+releaseUser,
            '-Dldi.projectUuid='+projectPortalUUID
        ])

        self.build_cfg.add_metadata_file(releaseMetadataFile)

    def _build(self):
        '''
            Build source files
        '''
        # Maven phases:
        #  validate - validate the project is correct and all necessary information is available
        #  compile - compile the source code of the project
        #  test - test the compiled source code using a suitable unit testing framework. These tests should not require the code be packaged or deployed
        #  package - take the compiled code and package it in its distributable format, such as a JAR.
        #  integration-test - process and deploy the package if necessary into an environment where integration tests can be run
        #  verify - run any checks to verify the package is valid and meets quality criteria
        #  install - install the package into the local repository, for use as a dependency in other projects locally
        #  deploy - done in an integration or release environment, copies the final package to the remote repository for sharing with other developers and projects.

        # Metadata quality check only for release or milestone build
        # See details of checks in https://wiki.wdf.sap.corp/wiki/display/LeanDI/Release+Build+Details#ReleaseBuildDetails-VersionUpdates

        if self.build_cfg.is_release() == 'direct-shipment' or self.build_cfg.is_release() == 'indirect-shipment':
            # For a customer release build use quality-check-config-customer.xml
            self._run_metadata_quality_check('-Dmetadata-quality-report.configuration=quality-check-config-customer.xml', '-Dcodesign.sap.realcodesigning=true')
        elif self.build_cfg.is_release() == 'milestone':
            # For a milestone build use quality-check-config-milestone.xml
            self._set_version_in_pom(self.build_cfg.base_version())
            self._run_metadata_quality_check('-Dmetadata-quality-report.configuration=quality-check-config-milestone.xml')

        # Compile sources and install binaries in local repository
        maven_args = []

        # Manage clean phase
        if self.build_cfg.do_clean():
            maven_args.append('clean')

        # prepare filesystem for local deployment
        if os.path.exists(self._localDeploymentPath):
            OS_Utils.rm_dir(self._localDeploymentPath)
        localDeploymentUrl = urlparse.urljoin('file:', urllib.pathname2url(self._localDeploymentPath))

        # Go until install phase to install package locally and
        # to be able to use it as dependency in other local projects
        maven_args.append('deploy')
        maven_args.append('-DaltDeploymentRepository=local::default::{}'.format(localDeploymentUrl))
        maven_args.append('-DuniqueVersion=false')

        # add options for signing
        '''
        History:
            1- _maven_jarsigner_plugin_options() was initially called with is_release_build() as parameter
            2- is_release() was introduced for leandi
            3- is_release_build() was reneamed into is_milestone() for xmake-dev (in xmake-dev we talk about "milestone release" builds)
            4- Certainly instead of renaming is_release_build() to is_milestone() in the _maven_jarsigner_plugin_options() call, it was renamed into is_release(), by the way signing worked only for leandi and not anymore for xmake-dev
            5- to work under both systems the call must be done with this value as parameter: self._maven_jarsigner_plugin_options(self.build_cfg.is_release() or self.build_cfg.is_milestone())
            Comment: Signing env vars are checked in the _maven_jarsigner_plugin_options() method. SNAPSHOT suffixs are checked in is_milestone() which also ensure that it does not run in is_release() mode
        +-----------+---------------+--------------+------------+------------------+-------------------+
        |  System   |  Build type   | is_milestone | is_release | Signing env vars | Signing activated |
        +-----------+---------------+--------------+------------+------------------+-------------------+
        | xMake-Dev |               |              |            |                  |                   |
        |           | CI/Voter/PR   | No           | No         | No               | No                |
        |           | OD Milestones | Yes          | No         | No               | No                |
        |           | OD Releases   | Yes          | No         | Yes              | Yes               |
        | xMake-Ldi |               |              |            |                  |                   |
        |           | OD Release    | No           | Yes        | Yes              | Yes               |
        +-----------+---------------+--------------+------------+------------------+-------------------+
        ASCII Table was generated with: https://ozh.github.io/ascii-tables/
        '''
        maven_args.extend(self._maven_jarsigner_plugin_options(self.build_cfg.is_release() or self.build_cfg.is_milestone()))

        if self.build_cfg.skip_test():
            maven_args.append('-Dmaven.test.skip=true')

        # add user options
        maven_args.extend(shlex.split(' '.join(self._maven_user_options)))

        # call mvn command
        self._mvn(maven_args)

        # Store build dependencies, should be done before _store_build_dependencies to ensure that the leandi plugin used for
        # generating metadata are also stored in the dependencies for reproducing the build with the exact leandi plugin versions for metadata generation
        # Generate release metadata data only in customer or in milestone
        if self.build_cfg.is_release():
            if self._ldi_metadata:
                log.info('building leandi metadata')
                self._store_ldi_metadata()
            else:
                log.info('leandi metadata generation disabled')

        # Store build dependencies
        log.info('building dependencies')
        self._store_build_dependencies()

    def _maven_jarsigner_plugin_options(self, releaseBuild):
        '''
            Signing with Lean DI (during a release build) ensures that build results are signed with valid certificates.
            released artifacts are signed with official SAP certificate
            locally build artifacts are signed with a self-signed certificate
            For signing during the release build, artifacts must be registered at final assembly.
        '''
        options = []

        # Read option values from os environment
        serverurl = os.getenv('SIGNING_PROXY_URL')  # https://signproxy.wdf.sap.corp:28443/sign
        keystore = os.getenv('SIGNING_KEYSTORE_PATH')
        keystorepass = os.getenv('SIGNING_KEYSTORE_PASSWORD')
        truststore = os.getenv('SIGNING_TRUSTSTORE_PATH')
        truststorepass = os.getenv('SIGNING_TRUSTSTORE_PASSWORD')

        logWarnings = []

        # Check server utl is set
        if serverurl is None:
            logWarnings.append('signing server url not set. Please set env SIGNING_PROXY_URL')
        elif not serverurl.startswith('http://') and not serverurl.startswith('https://'):
            logWarnings.append('bad signing server url waiting for http/https url: {}'.format(serverurl))

        # Check keystore exists
        if keystore is None:
            logWarnings.append('signing keystore path not set. Please set env SIGNING_KEYSTORE_PATH')
        elif not os.path.exists(keystore):
            logWarnings.append('signing keystore path does not exist {}'.format(keystore))
        elif os.path.isdir(keystore):
            logWarnings.append('signing keystore path does not point to a file {}'.format(keystore))

        if keystorepass is None:
            logWarnings.append('signing keystore password not set. Please set env SIGNING_KEYSTORE_PASSWORD')

        # Check truststore exists
        if truststore is None:
            logWarnings.append('signing truststore path not set. Please set SIGNING_TRUSTSTORE_PATH')
        elif not os.path.exists(truststore):
            logWarnings.append('signing truststore path does not exist {}'.format(truststore))
        elif os.path.isdir(truststore):
            logWarnings.append('signing truststore path does not point to a file {}'.format(truststore))

        if truststorepass is None:
            logWarnings.append('signing truststore password not set. Please set SIGNING_TRUSTSTORE_PASSWORD')

        if len(logWarnings) > 0:
            for logWarning in logWarnings:
                log.warning(logWarning, log.INFRA)
            log.warning('real singning parameters not set')
            return options

        if releaseBuild:
            log.info('real jar signing activated')
        options.append('-Dcodesign.sap.realcodesigning={}'.format('true' if releaseBuild else 'false'))
        options.append('-Dcodesign.sap.server.url={}'.format(serverurl))
        options.append('-Dcodesign.sap.ssl.keystore={}'.format(keystore))
        options.append('-Dcodesign.sap.ssl.keystore.pass={}'.format(keystorepass))
        options.append('-Dcodesign.sap.ssl.truststore={}'.format(truststore))
        options.append('-Dcodesign.sap.ssl.truststore.pass={}'.format(truststorepass))
        return options

    def _fortifyBuild(self):
        '''
            Build source files with fortify
        '''

        log.info('fortify translate and scan')

        # Compile sources and install binaries in local repository
        base_maven_args = []
        base_maven_args.append('-Dmaven.test.skip=true')

        # add user options
        base_maven_args.extend(shlex.split(' '.join(self._maven_user_options)))

        # fortify translate
        translate_args = []
        if self.build_cfg.do_clean():
            translate_args.append('clean')
        translate_args.append('install')
        translate_args.append('com.sap.ldi:fortify-plugin:{}:translate'.format(self._fortify_plugin_version))
        translate_args.extend(base_maven_args)
        self._mvn(translate_args)

        # fortify scan
        scan_args = []
        scan_args.append('com.sap.ldi:fortify-plugin:{}:scan'.format(self._fortify_plugin_version))
        scan_args.extend(base_maven_args)
        self._mvn(scan_args)

    def _fortifyDeploy(self):
        '''
            Deploy fortify result in corporate fortify server
        '''

        log.info('fortify upload')

        # Read option values from os environment
        serverurl = os.getenv('FORTIFY_F360_URL')  # https://fortify1.wdf.sap.corp/ssc
        token = os.getenv('FORTIFY_F360_AUTH_TOKEN')

        logErrors = []
        if serverurl is None:
            logErrors.append('fortify server url not set. Please set env FORTIFY_F360_URL')
        elif not serverurl.startswith('http://') and not serverurl.startswith('https://'):
            logErrors.append('bad fortify server url waiting for http/https url: {}'.format(serverurl))

        if token is None:
            logErrors.append('fortify token not set. Please set env FORTIFY_F360_AUTH_TOKEN')

        if len(logErrors) > 0:
            for error in logErrors:
                log.error(error, log.INFRA)
            raise XmakeException('fortify results upload fails')

        # fortify deploy
        maven_args = []
        maven_args.append('com.sap.ldi:fortify-plugin:{}:upload'.format(self._fortify_plugin_version))
        maven_args.append('-Dldi.fortify.f360.url={}'.format(serverurl))
        maven_args.append('-Dldi.fortify.f360.authToken={}'.format(token))
        maven_args.append('-Dldi.fortify.f360.projectVersion={}'.format(self.build_cfg.base_version().split('.')[0]))
        maven_args.extend(shlex.split(' '.join(self._maven_user_options)))
        self._mvn(maven_args)

    ###############################################################################
    #  Analyze and store build dependencies
    ###############################################################################

    def _store_build_dependencies(self):
        '''
            Store build dependencies in this format [group:artifact:version:type::classifier]
            ie: log4j-1.2.12-debug.jar --> log4j:log4j:1.2.12:jar::debug
            The file will be saved in [component_dir]/gen/tmp/dependencies
        '''
        artifacts = Artifact.gather_artifacts(self._maven_repository_dir)
        lines = []
        for key in artifacts:
            values = artifacts[key]
            for artifact in values:

                str_key = ':'.join([key, artifact.extension])
                if artifact.classifier:
                    str_key = '::'.join([str_key, artifact.classifier])
                lines.append(str_key)

        with open(self._maven_build_dependencies_file, 'w') as f:
            f.writelines(['%s\n' % line for line in lines])

        self.build_cfg.add_metadata_file(self._maven_build_dependencies_file)
        log.info('found ' + str(len(lines)) + ' dependencies')

    ###############################################################################
    #  Analyze build for deployment
    ###############################################################################
    def _generate_ads_file(self):
        '''
            Create the artifact deployer script file
        '''

        # Retrieve artifacts from local deployment repo
        artifacts = Artifact.gather_artifacts(self._localDeploymentPath)

        group_section_list = []
        for key in artifacts:
            values = artifacts[key]
            gav = key.split(':')
            group = gav[0]
            aid = gav[1]
            version = gav[2]
            strippedVersion = version
            strippedVersion = re.sub(r'\-(?i)(SNAPSHOT|RELEASE|MILESTONE)$', '', version)
            # Rollback this change as it causes a regression concatenating version twice 1.42.2-1.42.2
            # project_version = self.build_cfg.version()
            # if project_version is not None:
            #     strippedVersion = strippedVersion + '-' + project_version
            group_section_list.append('artifact "%s", group:"%s", version:"%s" , { ' % (aid, group, strippedVersion))
            for artifactObj in values:
                log.info('artifact to deploy ' + artifactObj.path)
                fileLine = '\t\t file "%s"' % artifactObj.path.replace('\\', '/')
                if not artifactObj.classifier == '':
                    fileLine = fileLine + ', classifier:"%s"' % (artifactObj.classifier)
                if not artifactObj.extension == '':
                    fileLine = fileLine + ', extension:"%s"' % (artifactObj.extension)
                group_section_list.append(fileLine)

                # Removed this restriction according to the new wanted behaviour see BESTL-8564
                # # Check that all submodules POMs have the same version as the main (Reactor) POM
                # project_version = self.build_cfg.version()
                # strippedVersion = re.sub(r'\-(?i)(SNAPSHOT|RELEASE|MILESTONE)$', '', artifactObj.version)
                # if strippedVersion != project_version:
                #     errorMessage = 'the following sub module POM %s:%s:%s has different version from the main POM  %s' % (artifactObj.gid, artifactObj.aid,artifactObj.version,project_version)
                #     errorMessage= errorMessage + ' All sub modules POM must have the same version as the main POM '
                #     raise XmakeException( errorMessage)

            group_section_list.append('\n\t}')

        export_ads_template_file = join(inst.get_installation_dir(), 'xmake', 'template', 'maven', 'export.ads')
        with open(export_ads_template_file, 'r') as f:
            export_ads = f.read()
        export_ads = Template(export_ads).substitute(groupList='\n\t'.join(group_section_list))

        with open(self._ads, 'w') as f:
            f.write(export_ads)

    def _copy_src_dir_to(self, todir):
        '''
            Copy source files in another directory to avoid modifications in original source files.
        '''

        if os.path.exists(todir):
            log.info('removing existing folder', todir)
            targetDirectory = os.path.join(todir, 'target')
            if os.path.exists(targetDirectory):
                log.debug('target directory was generated, so we keep it as it is in directory {}'.format(targetDirectory))
                tmpDir = os.path.join(tempfile.mkdtemp(), 'target')
                shutil.copytree(targetDirectory, tmpDir)
                OS_Utils.rm_dir(todir)
                os.mkdir(todir)
                shutil.copytree(tmpDir, targetDirectory)
                shutil.rmtree(tmpDir)
            else:
                OS_Utils.rm_dir(todir)
                os.mkdir(todir)
        else:
            os.mkdir(todir)

        log.info('copying files from', self.build_cfg.component_dir(), 'to', todir)

        for directory in os.listdir(self.build_cfg.component_dir()):
            if directory not in ['.xmake.cfg', 'gen', 'import', 'cfg', '.git', '.gitignore', 'target']:
                pathToCopy = os.path.join(self.build_cfg.component_dir(), directory)
                if os.path.isdir(pathToCopy):
                    shutil.copytree(pathToCopy, os.path.join(todir, directory))
                else:
                    shutil.copyfile(pathToCopy, os.path.join(todir, directory))

    def _hide_password_in_maven_args_for_log(self, maven_args):
        '''
            Hide password in logs
        '''

        argsToHide = ['-Dcodesign.sap.ssl.keystore.pass=',
                      '-Dcodesign.sap.ssl.truststore.pass=',
                      '-Dldi.fortify.f360.authToken=']

        maven_args_to_log = []
        # loop on maven args
        for arg in maven_args:
            if arg:
                found = False
                # loop on args to hide
                for argToHide in argsToHide:
                    if arg.startswith(argToHide):
                        found = True
                        maven_args_to_log.append(arg.split('=')[0] + '=*******')
                        break

                if not found:
                    maven_args_to_log.append(arg)

        return maven_args_to_log

    def _check_project_version_compliance(self):

            status = (True, '')
            if self.build_cfg.is_release() == 'direct-shipment':
                if not re.search(r'^[1-9]\d*\.\d+\.\d+$', self.build_cfg.base_version()):
                    err_message = 'ERR: project version %s does not respect the format for the direct shipment release. Version must have 3 digits and major greater than 0   ' % self.build_cfg.base_version()
                    status = (False, err_message)

            #############################
            # Three digit version format#
            #############################
            if self.build_cfg.is_release() == 'indirect-shipment':
                if not re.search(r'^\d+', self.build_cfg.base_version()):
                    err_message = 'ERR: project version %s does not respect the format for the indirect shipment release.' % self.build_cfg.base_version()
                    status = (False, err_message)

                is_compliant = False
                result = re.search(r'^(\d+\.\d+\.\d+)$', self.build_cfg.base_version())
                if result:
                    is_compliant = True

                else:
                    result = re.search(r'^(\d+\.\d+\.\d+)-(\d+)$', self.build_cfg.base_version())
                    if result:
                        version_digits = result.group(1)
                        self.build_cfg.set_base_version(version_digits)
                        is_compliant = True

#                     else:
#                         result = re.search(r'^(\d+\.\d+\.\d+)\.(\d+)$', self.build_cfg.base_version())
#                         if result:
#                             version_digits = result.group(1)
#                             self.build_cfg.set_base_version(version_digits)
#                             is_compliant = True
                    else:
                        result = re.search(r'^(\d+\.\d+\.\d+[-\.+])', self.build_cfg.base_version())
                        if result:
                            is_compliant = True
                            #############################
                            # Two digit version format  #
                            #############################
                        else:
                            result = re.search(r'^(\d+\.\d+)$', self.build_cfg.base_version())
                            if result:
                                self.build_cfg.set_base_version('{}.0'.format(self.build_cfg.base_version()))
                                is_compliant = True

                            else:
                                result = re.search(r'^(\d+\.\d+)[\.,-]([a-zA-Z]+[-\.]?\d*)$', self.build_cfg.base_version())
                                if result:
                                    version_digits = result.group(1)
                                    version_alphanumeric = result.group(2)
                                    self.build_cfg.set_base_version('{}.0-{}'.format(version_digits, version_alphanumeric))
                                    is_compliant = True

                                else:
                                    result = re.search(r'^(\d+\.\d+)-(\d+)$', self.build_cfg.base_version())
                                    if result:
                                        version_digits = result.group(1)
                                        self.build_cfg.set_base_version('{}.0'.format(version_digits))
                                        is_compliant = True
                                    else:
                                        result = re.search(r'^(\d+\.\d+)\.(0\d+)$', self.build_cfg.base_version())
                                        if result:
                                            version_digits = result.group(1)
                                            self.build_cfg.set_base_version('{}.0'.format(version_digits))
                                            is_compliant = True

                                            #############################
                                            # One digit version format  #
                                            #############################
                                        else:
                                            result = re.search(r'^([1-9]\d*)$', self.build_cfg.base_version())
                                            if result:
                                                self.build_cfg.set_base_version('{}.0.0'.format(self.build_cfg.base_version()))
                                                is_compliant = True
                                            else:
                                                result = re.search(r'^([1-9]\d*)[\.,-]([a-zA-Z]+[-\.]?\d*)$', self.build_cfg.base_version())
                                                if result:
                                                    version_digits = result.group(1)
                                                    version_alphanumeric = result.group(2)
                                                    self.build_cfg.set_base_version('{}.0.0-{}'.format(version_digits, version_alphanumeric))
                                                    is_compliant = True
                                                else:
                                                    result = re.search(r'^([1-9]\d*)\.(0\d+)$', self.build_cfg.base_version())
                                                    if result:
                                                        version_digits = result.group(1)
                                                        self.build_cfg.set_base_version('{}.0.0'.format(version_digits))
                                                        is_compliant = True
                                                    else:
                                                        result = re.search(r'^([1-9]\d*)-(\d+)$', self.build_cfg.base_version())
                                                        if result:
                                                            version_digits = result.group(1)
                                                            self.build_cfg.set_base_version('{}.0.0'.format(version_digits))
                                                            is_compliant = True

                if not is_compliant:
                    err_message = 'ERR: project version %s does not respect the format for the indirect shipment release.' % self.build_cfg.base_version()
                    status = (False, err_message)

            return status

    def _remove_leading_zero(self, given_version):

        result = given_version.split('-')

        version_digits = result[0]
        version_suffix = result[1:]
        log.debug('version_suffix = {}'.format(version_suffix))

        version_tab = version_digits.split('.')
        stripped_version_tab = []
        for elem in version_tab:
            if elem.isdigit():
                elem = str(int(elem))
            stripped_version_tab.append(elem)

        stripped_version = '.'.join(stripped_version_tab)
        if len(version_suffix) > 0:
            stripped_version = stripped_version + '-' + '-'.join(version_suffix)

        return stripped_version
