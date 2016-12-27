import log
import os
import json
import tarfile
import base64
import shlex
from distutils.version import LooseVersion


from shutil import copytree, copyfile, move
from os.path import join
from utils import is_existing_file, is_existing_directory
from xmake_exceptions import XmakeException
from ExternalTools import OS_Utils
from pyjavaproperties import Properties
from spi import BuildPlugin
from config import NPMREPO
from phases.deploy import resolve_deployment_credentials

DEFREG = 'http://10.97.24.230:8081/nexus/content/groups/build.npm/'


class build(BuildPlugin):

    def __init__(self, build_cfg):
        BuildPlugin.__init__(self, build_cfg)
        self._detected_npm_version = None
        self._node_version = '0.12.0'
        self._npm_user_options = []
        self._bundle = False
        self._run_shrinkwrap = True
        self._after_install = []
        self._before_publish = []
        self._node_executable = None
        self._npmcmd = None
        self._env = None
        self._path = None
        self._rel_path = 'bin'
        self._rel_npm = 'lib/node_modules/npm/bin/npm-cli.js'
        self._root = self.build_cfg.src_dir()
        self._pkgfile = join(self._root, 'package.json')
        self._npm_prefix_dir = join(self.build_cfg.temp_dir(), '.npm-global')


        self.build_cfg.tools().declare_runtime_tool('nodejs', 'com.sap.prd.distributions.org.nodejs:nodejs:tar.gz')
        repos = self.build_cfg.import_repos(NPMREPO)
        if repos is None or len(repos) == 0:
            raise XmakeException('npm repository required')
        if len(repos) > 1:
            log.warning('multiple NPM import repositories found -> ignore all but the first one')
        self.registry = repos[0]
        log.info('using NPM import repository ' + self.registry)

        if self._is_plain():
            log.info('using plain mode for build')
        if not is_existing_file(self._pkgfile):
            raise XmakeException('package.json required in projects root or src folder')
        with open(self._pkgfile, 'r') as d:
            self.pkg = json.load(d)
        if 'name' not in self.pkg:
            raise XmakeException('package.json must contain a name field')
        self.module_name = self.pkg['name']
        if 'dependencies' not in self.pkg:
            self._run_shrinkwrap = False
        else:
            dependencies = self.pkg['dependencies']
            if dependencies is not None and bool(dependencies) is False:
                self._run_shrinkwrap = False

        self.deps = join(self.build_cfg.temp_dir(), 'dependencies')
        self.build_cfg.add_metadata_file(self.deps)

        # Take in account arguments after the --
        # All these arguments will be passed to the npm command
        if self.build_cfg.build_args():
            for arg in self.build_cfg.build_args():
                log.info('  using custom option ' + arg)
                self._npm_user_options.append(arg)

    def set_options(self, opts):
        for o in opts:
            log.info('  using node version ' + o)
            self._node_version = o

    def set_option(self, o, v):
        if o == 'node-version':
            log.info('  using node version ' + v)
            self._node_version = v
            return
        if o == 'bundle':
            self._bundle = (v == 'true')
            return
        if o == 'after_install':
            self._after_install = v.split(',')
            return
        if o == 'before_publish':
            self._before_publish = v.split(',')
            return
        if o == 'options':
            values = v.split(',')
            for value in values:
                log.info('  using custom option ' + value)
                self._npm_user_options.append(value)
            return

        BuildPlugin.set_option(self, o, v)

    def required_tool_versions(self):
        return {'nodejs': self._node_version}

    def variant_cosy_gav(self):
        return None

    def _node_cmd(self, nodehome=None):
        if nodehome is None:
            nodehome = self._nodehome
        return os.path.join(nodehome, self._rel_path, self.build_cfg.tools().executable('node', 'exe'))

    def _npm_script(self, nodehome=None):
        if nodehome is None:
            nodehome = self._nodehome
        return os.path.join(nodehome, self._rel_npm)

    def _npm_cmd(self, nodehome=None):
        if nodehome is None:
            nodehome = self._nodehome
        return [self._node_cmd(nodehome), '-i', self._npm_script(nodehome)]

    def _setup(self):
        if self._npmcmd is None:
            self._nodehome = self.build_cfg.tools()['nodejs'][self._node_version]
            dirs = os.listdir(self._nodehome)
            if len(dirs) != 1:
                raise XmakeException('ERR: invalid nodejs distribution %s' % str(self._nodehome))
            self._nodehome = join(self._nodehome, dirs[0])
            log.info('found node: ' + self._nodehome)

            self._path = os.path.realpath(os.path.join(self._nodehome, self._rel_path))
            self._node_executable = os.path.realpath(self._node_cmd())
            self._npmrc_file = os.path.join(self.build_cfg.temp_dir(), '.npmrc')
            self._npmcmd = [self._node_executable, '-i', os.path.realpath(self._npm_script()), '--userconfig', self._npmrc_file]

            self.module_dir = join(self.build_cfg.gen_dir(), 'module')
            self.shrinkwrap = join(self.build_cfg.temp_dir(), 'npm-shrinkwrap.json')
            self.build_cfg.add_metadata_file(self.shrinkwrap)
            self.setup_env()

    def setup_env(self):
        if self._env is None:
            self._env = log.ExecEnv()

            env = dict(os.environ)
            prop = 'PATH'
            if prop not in env:
                prop = 'path'

            p=self._path+os.pathsep+os.path.join(self._npm_prefix_dir, 'bin')

            env[prop] = p+(os.pathsep+env[prop] if prop in env else "")
            log.info('adding '+p+' to '+prop)
            env['XMAKE_IMPORT_DIR'] = self.build_cfg.import_dir()
            log.info('adding '+self._npm_prefix_dir+' to NPM_CONFIG_PREFIX')
            env['NPM_CONFIG_PREFIX'] = self._npm_prefix_dir

            def add_tool(n, d):
                prop = self._tool_property(n)
                log.info('  adding env property '+prop)
                env[prop] = d
            self._handle_configured_tools(add_tool)

            self._env.env = env
            self._env.cwd = self.module_dir

    def _tool_property(self, key):
        return 'TOOL_' + key + '_DIR'

    def handle_build(self):
        self.prepare_npmrc()
        self.install_dependencies()
        # DTXMAKE-1310 node buildplugin - Enabling back shrinkwrap when depependencies detected or npm >= 3.0.0
        # do the shrinkwrao only if there are some dependencies or if version is >= to 3.0.0 otherwise all versions below will crash! 
        detected_npm_loose_version=LooseVersion(self._detected_npm_version) if self._detected_npm_version else None 
        if self._run_shrinkwrap or (detected_npm_loose_version and detected_npm_loose_version>=LooseVersion("3.0.0")):
            log.info("dependencies detected, calling gather_dependencies step" if self._run_shrinkwrap else "npm version >= 3.0.0, calling gather_dependencies step")
            self.gather_dependencies()
        else:
            log.warning('Skip "gather_dependencies" step as this project has no dependencies in packages.json or npm version must be >= 3.0.0')
        self.execute_commands(self._after_install)
        self.execute_scripts()
        self.execute_commands(self._before_publish)

    def run(self):
        self._clean_if_requested()
        self._setup()

        self.prepare_sources()
        self.handle_build()
        self.prepare_deployment()

    def npm(self, args, reg=None):
        tmp = [x for x in self._npmcmd]
        if reg is None:
            reg = self.registry
        #tmp.append('--verbose')
        tmp.extend(['--reg', reg])
        tmp.extend(args)
        log.info('node args: ', ','.join(tmp))
        rc = self._env.log_execute(tmp)
        if rc > 0:
            raise XmakeException('ERR: npm returned %s' % str(rc))

    def prepare_export(self):
        ads = join(self.build_cfg.temp_dir(), 'export.ads')
        mapping_script = '''
artifacts builderVersion:"1.1", {
   group "com.sap.npm", {
         artifact "'''+self.module_name+'''", {
            file "${gendir}/module.tar.gz", extension:"tar.gz"
'''
        if self._bundle:
            mapping_script += '''
            file "${gendir}/bundle.tar.gz", extension:"tar.gz", classifier:"bundle"
'''
        mapping_script += '''
         }
   }
}
'''
        with open(ads, 'w') as f:
            f.write(mapping_script)
            self.build_cfg.set_export_script(ads)

    def get_version(self, md, mp):
        f = join(md, 'package.json')
        if not is_existing_file(f):
            log.warning('missing package.json in dependency' + mp)
            return None
        with open(f, 'r') as d:
            pkg = json.load(d)
        if 'version' not in pkg:
            raise XmakeException('package.json in dependency '+mp+' must contain a version field')
        return pkg['version']

    def list_deps(self, d, p):
        r = []
        d = join(d, 'node_modules')
        if is_existing_directory(d):
            for m in os.listdir(d):
                md = join(d, m)
                if m != '.bin' and is_existing_directory(md):
                    mp = p+'/'+m
                    v = self.get_version(md, mp)
                    if v is not None:
                        r.append((mp, str(v)))
                    r.extend(self.list_deps(md, mp))
        return r

    def prepare_sources(self):
        log.info('copying module sources...')
        if os.path.exists(self.module_dir):
            OS_Utils.rm_dir(self.module_dir)
        os.mkdir(self.module_dir)
        
        for directory in os.listdir(self._root):
            if directory not in ['.xmake.cfg', '.xmake', 'gen', 'import', 'cfg', '.git', 'node_modules']:
                pathToCopy = os.path.join(self._root, directory)
                if os.path.isdir(pathToCopy):
                    copytree(pathToCopy, os.path.join(self.module_dir, directory))
                else:
                    copyfile(pathToCopy, os.path.join(self.module_dir, directory))
        os.mkdir(join(self.module_dir, 'node_modules'))
        self.check_tool([])

    def install_dependencies(self):
        # npm install
        log.info('installing dependencies...')
        npm_args = ['--strict-ssl', 'false', 'install']
        if self._npm_user_options:
            npm_args.extend(shlex.split(' '.join(self._npm_user_options)))
        self.npm(npm_args)

    def check_tool(self, args):
        tool = self.build_cfg.tools().packaged_tools_dir('checkpackage')
        log.info('using check tool '+tool)
        checkcmd = [self._node_executable, '-i', join(tool, 'check'), '-v', 'error',
                    '-f', join(self._root, 'package.json'),
                    '-d', 'version', '-d', 'range']
        if not self.build_cfg.is_release() and not self.build_cfg.is_milestone():
            checkcmd.extend(['-d', 'others'])
        else:
            if self.build_cfg.version_suffix() is not None:
                checkcmd.extend(['-s', '-'+self.build_cfg.version_suffix()])
            checkcmd.extend(['-t', '-o', join(self.module_dir, 'package.json')])
        log.info('executing check '+str(checkcmd))
        rc = self._env.log_execute(checkcmd)
        if rc > 0:
            raise XmakeException('ERR: package.json check returned %s' % str(rc))

    def execute_scripts(self):
        scripts = {}
        if 'scripts' in self.pkg:
            scripts = self.pkg['scripts']
        log.info('calling scripts...')
        if 'lint' in scripts:
            self.npm(['run', 'lint'])
        if 'test' in scripts:
            if not self.build_cfg.skip_test():
                self.npm(['test'])

    def execute_commands(self, cmds):
        for cmd in cmds:
            cmd = cmd.strip()
            log.info('executing script '+cmd)
            self.npm(['run', cmd])

    def _clean_shrinkwrap(self, shrinkwrappart, keypath=(), listofkeytoremove=[]):
        for key in shrinkwrappart:
            value = shrinkwrappart[key]
            if type(value) is dict:
                self._clean_shrinkwrap(value, tuple(list(keypath)+[key]), listofkeytoremove)
            elif key == 'from' or key == 'resolved':
                listofkeytoremove.append(tuple(list(keypath)+[key]))

    def gather_dependencies(self):
        log.info('gathering dependencies...')
        self.npm(['shrinkwrap'])
        shrinkwrapFile = join(self.module_dir, 'npm-shrinkwrap.json')
        if is_existing_file(shrinkwrapFile):
            move(shrinkwrapFile, self.shrinkwrap)

        # clean shrinkwrap file see spec on https://wiki.wdf.sap.corp/wiki/display/xs2/Filtering+SAP-internal+metadata+before+release
        cleanedShrinwrap = {}
        with open(self.shrinkwrap, 'r') as f:
            cleanedShrinwrap = json.load(f)

        keystoremove = []
        self._clean_shrinkwrap(cleanedShrinwrap, listofkeytoremove=keystoremove)
        for keys in keystoremove:
            shrinkwrappart = cleanedShrinwrap
            for key in keys[:-1]:
                shrinkwrappart = shrinkwrappart[key]
            shrinkwrappart.pop(keys[-1], None)

        with open(self.shrinkwrap, 'w') as jsonfile:
            json.dump(cleanedShrinwrap, jsonfile, indent=2)

        dep = self.module_dir
        p = Properties()
        for (m, v) in self.list_deps(join(dep), ''):
            p.setProperty(m, v)
        with open(self.deps, 'w') as f:
            p.store(f)
        copyfile(self.deps, join(dep, 'dependencies'))

    def prepare_deployment(self):
        log.info('packaging...')
        omit = set([self.module_dir+os.sep+'node_modules'])

        def imports(n):
            return n in omit

        with tarfile.open(join(self.build_cfg.gen_dir(), 'module.tar.gz'), 'w:gz') as tar:
            tar.add(self.module_dir, arcname=os.curdir, exclude=imports)
        if self._bundle:
            with tarfile.open(join(self.build_cfg.gen_dir(), 'bundle.tar.gz'), 'w:gz') as tar:
                tar.add(self.module_dir, arcname=os.curdir)

    def prepare_npmrc(self, user=None, password=None):
        with open(self._npmrc_file, 'w') as f:
            if user and password:
                auth = base64.b64encode(user+':'+password)
                f.write('email=xmake@sap.com\n')
                f.write('_auth='+auth+'\n')
            f.write('prefix='+self._npm_prefix_dir+'\n')

    def publish(self):
        repo = self.build_cfg.export_repo(NPMREPO)
        if repo is None:
            raise XmakeException('no NPM deployment repository configured')
        log.info('publishing to NPM repository '+repo+'...')
        resolve_deployment_credentials(self.build_cfg, NPMREPO)
        user = self.build_cfg.deploy_user(NPMREPO)
        password = self.build_cfg.deploy_password(NPMREPO)
        if user is None:
            raise XmakeException('no user found for NPM deployment')
        if password is None:
            raise XmakeException('no password found for NPM deployment')
        log.info('  using user '+user)

        try:
            self.prepare_npmrc(user, password)
            self.npm(['publish'], repo)
        finally:
            if self._npmrc_file is not None:
                os.remove(self._npmrc_file)

    def after_PRELUDE(self, build_cfg):
        if not is_existing_file(self.build_cfg.export_script()):
            self.prepare_export()

    def after_DEPLOY(self, build_cfg):
        if not build_cfg.do_deploy():
            return
        self._setup()
        repo = build_cfg.export_repo(NPMREPO)
        log.info('npm deployment repo is '+str(repo))
        if build_cfg.is_release() or build_cfg.is_milestone():
            self.publish()
        else:
            log.info('no npm deployment for non-release build')

    def after_IMPORT(self, build_cfg):
    	self._setup()
        cmd = list(self._npmcmd)
        cmd.append('--version')
        previous_cwd=self._env.cwd # As source not necessary copied into the module dir which is the cwd after _setup
        self._env.cwd=self._root # use the _root src dir
        def handler(string):
            self._detected_npm_version=string.strip()
        rc = self._env.log_execute(cmd, handler=handler)
        self._env.cwd=previous_cwd # set back the value set previously
        if rc > 0:
            raise XmakeException('ERR: npm returned %s' % str(rc))
