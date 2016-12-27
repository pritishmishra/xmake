import log

import docker
import buildplugins.node
import buildplugins.dockerrun

from xmake_exceptions import XmakeException

DEFREG = 'http://10.97.24.230:8081/nexus/content/groups/build.npm/'


class build(buildplugins.node.build):
    def __init__(self, build_cfg):
        buildplugins.node.build.__init__(self, build_cfg)

        self.image_name = None
        self.image_file = None
        self.aid = None
        self.gid = None
        self.version = None
        self.mode = 'docker'
        self.keepuser = True
        self.keepcontainer = False

        self._scripts = []
        self._importdir = '/imports'
        self._gendir = '/gen'
        self._srcdir = '/src'

    def set_option(self, o, v):
        if o == 'scripts':
            self._scripts = v.split(',')
            return
        if not buildplugins.dockerrun._set_stdrun_option(self, o, v):
            buildplugins.node.build.set_option(self, o, v)

    def plugin_imports(self):
        return buildplugins.dockerrun._plugin_imports(self)

    def _setup(self):
        buildplugins.node.build._setup(self)
        buildplugins.dockerrun._setup_image(self)

    def docker(self, args, reg=None, handler=None):
        docker.docker(args, handler, self.build_cfg.gen_dir())

    def handle_build(self):
        buildplugins.dockerrun._check(self)
        if self.image_name is None:
            raise XmakeException('ERR: please specify docker image id to use in buildplugin option "image"')

        log.info('executing docker node build...')

        opt = ['-v', self.module_dir + ':' + self._srcdir]
        opt.extend(['-v', self.build_cfg.import_dir()+':'+self._importdir+':ro'])
        opt.extend(['-v', self.build_cfg.gen_dir()+':'+self._gendir])
        opt.extend(['-v', self._nodehome+':/tools/nodejs:ro'])
        opt.extend(['-e', 'XMAKE_NPM_REGISTRY='+str(self.registry)])
        opt.extend(['-e', 'XMAKE_NODE_HOME=/tools/nodejs'])
        opt.extend(['-e', 'XMAKE_NODE_CMD='+self._node_cmd('/tools/nodejs')])
        opt.extend(['-e', 'XMAKE_NPM_CMD='+' '.join(self._npm_cmd('/tools/nodejs'))])
        opt.extend(['-e', 'XMAKE_NPM_SCRIPTS='+' '.join(self._scripts)])

        buildplugins.dockerrun._execute_build(self, opt)
