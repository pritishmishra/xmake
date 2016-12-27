import log
import os
from xmake_exceptions import XmakeException

from spi import BuildPlugin


class build(BuildPlugin):
    def __init__(self, build_cfg):
        BuildPlugin.__init__(self, build_cfg)
        self._node_version = '0.10.33-SNAPSHOT'
        self.build_cfg.tools().declare_tool('nodejs', 'com.sap.prd.distributions.org.nodejs:nodejs:tar.gz')

    def required_tool_versions(self):
        return {'nodejs': self._node_version}

    def variant_cosy_gav(self):
        return None

    def run(self):
        self._clean_if_requested()

        self._nodehome = self.build_cfg.tools()['nodejs'][self._node_version]
        log.info('found node: ' + self._nodehome)

        node_executable = os.path.join(self._nodehome, 'bin', 'node')
        npm_executable = os.path.join(self._nodehome, 'bin', 'npm')
        grunt_executable = os.path.join('.', 'node_modules', '.bin', 'grunt')

        std = [node_executable, '-i', npm_executable, '--reg', 'http://10.97.24.230:8081/nexus/content/groups/build.npm/']
        # npm install grunt-cli
        args = [x for x in std]
        args.extend(['install', 'grunt-cli'])

        log.info('invoking npm: ' + ' '.join(args))

        rc = log.log_execute(args)
        if rc > 0:
            raise XmakeException('ERR: npm returned %s' % str(rc))

        # npm install
        args = [x for x in std]
        args.extend(['install'])

        log.info('invoking npm: ' + ' '.join(args))

        rc = log.log_execute(args)
        if rc > 0:
            raise XmakeException('ERR: npm returned %s' % str(rc))

        # grunt build
        args = [node_executable, '-i', grunt_executable, 'build']

        log.info('invoking grunt: ' + ' '.join(args))

        rc = log.log_execute(args)
        if rc > 0:
            raise XmakeException('ERR: grunt returned %s' % str(rc))
