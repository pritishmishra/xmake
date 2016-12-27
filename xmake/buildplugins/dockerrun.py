import log
import docker
import os, re

from utils import is_existing_file, is_existing_directory
from xmake_exceptions import XmakeException
from spi import VariantBuildPlugin


class build(VariantBuildPlugin):
    def __init__(self, build_cfg):
        VariantBuildPlugin.__init__(self, build_cfg)

        if not build_cfg.runtime().startswith('linux'):
            raise XmakeException('docker build available only on linux runtime')
        if not is_existing_directory(self.build_cfg.src_dir()):
                self.build_cfg.set_src_dir(self.build_cfg.component_dir())
                log.info('using flat source dir: '+self.build_cfg.src_dir())
        repos = self.build_cfg.import_repos('DOCKER')
        if repos is None or len(repos) == 0:
            log.warning('no docker repository specified')
            self.registry = None
        else:
            if len(repos)>1:
                log.warning("multiple DOCKER import repositories found -> ignore all but the first one")
            self.registry=repos[0]
            log.info("using DOCKER import repository "+self.registry)
        self.image_file = None
        self.image_name = None
        self.aid = None
        self.gid = None
        self.version = None
        self.mode = 'tool'
        self.keepuser = True
        self.keepcontainer = False
        self._srcdir = '/src'
        self._gendir = '/gen'
        self._importdir = '/imports'

    def set_options(self, opts):
        pass

    def set_option(self, o, v):
        if o == 'srcdir':
            self._srcdir = v
            return
        if o == 'gendir':
            self._gendir = v
            return
        if o == 'importdir':
            self._importdir = v
            return
        if o == 'cosy':
            if len(v.split(':')) == 2:
                log.info('  using coordinate system '+v)
                self._variant_cosy_gav = v
            else:
                raise XmakeException('ERR: invalid coordinate system specification '+str(v)+': expected <name>:<version>')
            return
        if not _set_stdrun_option(self, o, v):
            VariantBuildPlugin.set_option(self, o, v)

    def after_PRELUDE(self, build_cfg):
        log.info('checking docker settings...')
        _check(self)
        self.declare_tools()

    def declare_tools(self):
        if self.mode == 'tool':
            if not self.build_cfg.tools().is_declared_tool('dockerimage'):
                self.build_cfg.tools().declare_tool('dockerimage', ':'.join([self.gid, self.aid, 'tar.gz']), archive=False)

    def required_tool_versions(self):
        if self.mode != 'tool':
            return {}

        return {'dockerimage': self.version}

    def plugin_imports(self):
        _plugin_imports(self)

    def _setup(self):
        _setup_image(self)

    def run(self):
        self._clean_if_requested()
        self._setup()
        self.execute_scripts()

    def docker(self, args, reg=None, handler=None):
        docker.docker(args, handler, self.build_cfg.gen_dir())

    def is_plain(self):
        return self.build_cfg.src_dir() == self.build_cfg.component_dir()

    def handle_dict(self, cmd, d, prefix):
            cmd.extend(['-e', prefix+'S='+','.join(d.keys())])
            for c, v in d.items():
                cmd.extend(['-e', prefix+'_'+c+'='+v])

    def execute_scripts(self):

        log.info('executing docker build...')
        opt = ['-v', self.build_cfg.src_dir()+':'+self._srcdir+':ro']
        opt.extend(['-v', self.build_cfg.import_dir()+':'+self._importdir+':ro'])
        opt.extend(['-v', self.build_cfg.gen_dir()+':'+self._gendir])
        opt.extend(['-v', self.build_cfg.tools().artifact_deployer()+':/xmake/tools/artifactdeployer:ro'])
        opt.extend(['-v', self.build_cfg.component_dir()+':/project:ro'])

        if not self.build_cfg.suppress_variant_handling():
            self.handle_dict(opt, self.build_cfg.variant_coords(), 'XMAKE_VARIANT_COORD')
            self.handle_dict(opt, self.build_cfg.variant_info(), 'XMAKE_VARIANT_INFO')

        _execute_build(self, opt)
        df = os.path.join(self.build_cfg.gen_dir(), 'export.df')
        if is_existing_file(df):
            log.info('deploy file already created by build')
            if is_existing_file(self.build_cfg.export_file()):
                os.remove(self.build_cfg.export_file())
            os.symlink(df, self.build_cfg.export_file())


############################################
# Utilities
############################################

def _plugin_imports(build):
        _check(build)
        return {'default': [':'.join([build.gid, build.aid, 'tar.gz', build.version])]} if build.mode == 'import' else {}


def _set_stdrun_option(build, o, v):
        if o == 'image':
            build.image_name = v
            build.mode = 'docker'
            return True
        if o == 'aid':
            build.aid = v
            return True
        if o == 'gid':
            build.gid = v
            return True
        if o == 'version':
            build.version = v
            return True
        if o == 'mode':
            if not v.lower() in ['import', 'docker', 'tool']:
                raise XmakeException('invalid image mode '+v+', please use Import, Docker or Tool')
            build.mode = v
            return True
        if o == 'keepuser':
            build.keepuser = v.lower() == 'true'
            return True
        if o == 'keepcontainer':
            build.keepcontainer = v.lower() == 'true'
            return True
        return False


def _check(build):
        if build.image_name is not None:
            if build.mode != 'docker':
                raise XmakeException('using docker image name requires mode "docker"')
            return
        if build.mode is None:
            if build.version is None or build.gid is None:
                build.mode = 'docker'
        if build.aid is None:
            raise XmakeException('docker image name or artifact id required: specify property aid for build plugin')
        if build.gid is None:
            if build.mode != 'docker':
                raise XmakeException('group id for docker image required: specify property gid for build plugin')
        elif 'IS_NEW_DOCKER' in os.environ and os.environ['IS_NEW_DOCKER'] == 'true':
             build.gid = re.sub('^[^:]+:\d+/', '', build.gid)
             build.gid = build.registry + '/' + build.gid
        if build.version is None:
            if build.mode != 'docker':
                raise XmakeException('version of docker image required: specify property version for build plugin')
        else:
            if build.mode is 'tool':
                if build.version.endwith('-SNAPSHOT'):
                    raise XmakeException('snapshot versions not supported for tool dependencies')


def _setup_image(build):
        if build.mode == 'docker':
            if build.image_name is None:
                build.image_name = docker.normalize_tag(build.aid)
                if build.gid is not None:
                    build.image_name = build.gid+'/'+build.image_name
                if build.version is not None:
                    build.image_name = build.image_name+':'+build.version
            log.info('using docker to resolve docker image '+build.image_name)
            try:
                build.docker(['pull',build.image_name])
            except XmakeException:
                log.error("docker image '%s' not found.\nPlease check the docker registry '%s'" % (build.image_name, build.registry))
                raise XmakeException("ERR: docker image '%s' not found.\nPlease check the docker registry '%s'" % (build.image_name, build.registry))
        else:
            if build.mode == 'tool':
                build.image_file = os.path.join(build.build_cfg.tools()['dockerimage'][build.version], 'artifact.tar.gz')
                build.image_name = docker.get_image_id(build.image_file)
                log.info('using image '+build.image_name+' from tool like image file '+build.image_file)
            if build.mode == 'import':
                build.image_file = os.path.join(build.build_cfg.import_dir(), build.aid+'-'+build.version+'.tar.gz')
                build.image_name = docker.get_image_id(build.image_file)
                log.info('using image '+build.image_name+' from imported image file'+build.image_file)

            if build.image_file is not None:
                build.docker(['load', '-i', build.image_file])


def _execute_build(build, opt):
    cmd = ['run']
    if opt is not None:
        cmd.extend(opt)
    cmd.extend(['-e', 'XMAKE_SRCDIR='+build._srcdir])
    cmd.extend(['-e', 'XMAKE_GENDIR='+build._gendir])
    cmd.extend(['-e', 'XMAKE_IMPORTDIR='+build._importdir])
    cmd.extend(['-e', 'XMAKE_PROJECTDIR=/project'])
    cmd.extend(['-e', 'XMAKE_PROJECT_VERSION='+build.build_cfg.version()])
    cmd.extend(['-e', 'XMAKE_PROJECT_BASE_VERSION='+build.build_cfg.base_version()])
    cmd.extend(['-e', 'XMAKE_PROJECT_VERSION_SUFFIX=' +
                (build.build_cfg.version_suffix() if build.build_cfg.version_suffix() is not None else '')])
    cmd.extend(['-e', 'XMAKE_RELEASE_BUILD='+str(build.build_cfg.is_release() or build.build_cfg.is_milestone())])
    cmd.extend(['-e', 'XMAKE_SKIP_TESTS='+str(build.build_cfg.skip_test())])
    if not build.keepcontainer or build.build_cfg.productive():
            cmd.extend(['--rm=true'])
    if not build.keepuser:
        cmd.extend(['-u', str(os.getuid())])
    cmd.extend([build.image_name])
    try:
        build.docker(cmd)
    finally:
        if build.keepuser:
            build.docker(['run', '--rm', '-v', build.build_cfg.gen_dir()+':'+build._gendir, build.gid+'/'+build.aid+':'+(build.version if build.version else "latest"), 'chown', '-R', str(os.getuid()), build._gendir])
