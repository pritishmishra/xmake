import log
import os, re
import docker
import shutil

from distutils.version import LooseVersion
from shutil import copytree, ignore_patterns
from os.path import join
from utils import is_existing_file, is_existing_directory, get_first_line
from xmake_exceptions import XmakeException
from ExternalTools import OS_Utils
from spi import BuildPlugin
from config import DOCKERREPO
from phases.deploy import resolve_deployment_credentials


class build(BuildPlugin):
    def __init__(self, build_cfg):
        BuildPlugin.__init__(self, build_cfg)

        if not build_cfg.runtime().startswith('linux'):
            raise XmakeException('docker build available only on linux runtime')

        repos = self.build_cfg.import_repos('DOCKER')
        if repos is None or len(repos) == 0:
            log.warning('no docker repository specified')
            self.registry = None
        else:
            if len(repos) > 1:
                log.warning('multiple DOCKER import repositories found -> ignore all but the first one')
            self.registry = repos[0]
            log.info('using DOCKER import repository '+self.registry)
        f = join(self.build_cfg.src_dir(), 'Dockerfile')
        if not is_existing_file(f):
            raise XmakeException('Docker file required in projects root folder')
        if 'IS_NEW_DOCKER' in os.environ and os.environ['IS_NEW_DOCKER'] == 'true':
            with open('Dockerfile') as infile, open('Dockerfile_tmp', 'w') as outfile:
                for line in infile:
                    line = re.sub('^\s*FROM\s*[^:]+:\d+/', 'FROM ', line)
                    if self.registry is not None:
                        line = re.sub('^\s*FROM\s*', 'FROM '+self.registry+'/', line)
                    outfile.write(line)
            shutil.copyfile('Dockerfile_tmp', 'Dockerfile')
        
        self.context_dir = join(self.build_cfg.gen_dir(), 'context')
        self.import_dir = join(self.context_dir, 'imports')
        self.image_file = join(build_cfg.gen_dir(), 'image.tar.gz')
        self.delta_file = join(build_cfg.gen_dir(), 'delta.tar.gz')
        self.image_name_file = join(build_cfg.gen_dir(), 'imagename')

        self.aid = None
        self.gid = 'com.sap.docker'
        self.load = None
        self.delta = False
        self.common = False
        self.echo = False

        self.image = None
        self.src_image = None
        self.src_imagename = None
        self.docker_force_enabled=False
        
        output=[]
        def catch_output(line):
            if not len(output):
                log.info(line.rstrip())
            output.append(line)        
        docker.docker(["-v"],handler=catch_output)
        m = re.match(r".*?\s+(?P<Version>\d+\.[\w\.\-]+).*", ''.join(output))        
        if m and m.group('Version'):
            log.info("Checking --force flag for version: "+m.group('Version'))
            if LooseVersion(m.group('Version'))<LooseVersion('1.10'): # starting from 1.10 forcing option is deprecated
                self.docker_force_enabled=True

    def set_options(self, opts):
        pass

    def set_option(self, o, v):
        if o == 'aid':
            self.aid = v
        if o == 'gid':
            self.gid = v
        if o == 'load':
            self.load = v.split(',')
        if o == 'common':
            self.common = v.lower() == 'true'
        if o == 'delta':
            self.delta = v.lower() == 'true'
        if o == 'echo':
            self.echo = v.lower() == 'true'

    def required_tool_versions(self):
        return {}

    def variant_cosy_gav(self):
        return None

    def _setup(self):
        if self.aid is None:
            raise XmakeException('build plugin option aid must be specified (repository name)')
        if self.gid is None:
            raise XmakeException('build plugin option aid must be specified (repository name)')

    def run(self):
        self._clean_if_requested()
        self._setup()

        self.prepare_sources()
        self.install_dependencies()
        self.execute_scripts()

    def docker(self, args, reg=None, handler=None):
        docker.docker(args, handler, self.context_dir)

    def prepare_export(self):
        if not self.common:
            return
        ads = join(self.build_cfg.temp_dir(), 'export.ads')
        mapping_script = '''
artifacts builderVersion:"1.1", {
   group "'''+self.gid+'''", {
         artifact "'''+self.aid+'''", {
        }
    }
}
'''
        with open(ads, 'w') as f:
            f.write(mapping_script)
            self.build_cfg.set_export_script(ads)

    def is_plain(self):
        return self.build_cfg.src_dir() == self.build_cfg.component_dir()

    def prepare_sources(self):
        log.info('copying context sources...')
        if os.path.exists(self.context_dir):
            OS_Utils.rm_dir(self.context_dir)
        ign = ignore_patterns('gen*', 'import', 'cfg', '.git', 'node_modules') if self.is_plain() else None
        copytree(self.build_cfg.src_dir(), self.context_dir, ignore=ign)

    def install_dependencies(self):
        # npm install
        log.info('installing dependencies...')
        os.mkdir(self.import_dir)

        if not is_existing_directory(self.build_cfg.import_dir()):
            return

        if OS_Utils.is_UNIX():
            names = os.listdir(self.build_cfg.import_dir())
            if names is not None:
                for name in names:
                    os.link(join(self.build_cfg.import_dir(), name), join(self.import_dir, name))
        else:
            copytree(self.build_cfg.import_dir(), self.import_dir)

        if self.load is not None:
            log.info('preloading images...')
            for image in self.load:
                ifile = join(self.build_cfg.import_dir(), image)
                if is_existing_file(ifile):
                    log.info('  loading '+image)
                    self.docker(['load', '-i', ifile])
                else:
                    log.warning('image '+image+' not imported')

    def match(self, line, key, old=None):
        if line.startswith(key):
            return line[len(key)+1:].strip()
        return old

    def execute_scripts(self):
        log.info('executing docker build...')
        self.image = None

        def handler(line):
            if self.src_image is None:
                self.src_imagename = self.match(line, 'Step 0 : FROM', self.src_imagename)
                if not self.src_imagename:
                    self.src_imagename = self.match(line, 'Step 1 : FROM', self.src_imagename)
                self.src_image = self.match(line, ' --->', self.src_image)
            self.image = self.match(line, 'Successfully built', self.src_image)
            return line
        try:
            self.docker(["build",self.context_dir],handler=handler)
        except XmakeException:
            log.error("docker image '%s' not found.\nPlease check the docker registry '%s'" % (self.src_imagename, self.registry))
            raise XmakeException("ERR: docker image '%s' not found.\nPlease check the docker registry '%s'" % (self.src_imagename, self.registry))
        if self.image is None:
            raise XmakeException('ERR: no image found')
        log.info('generated docker image '+self.image)
        addfile = os.path.join(self.build_cfg.src_dir(), 'DockerCommands')
        if is_existing_file(addfile):
            log.info('executing additional commands...')
            succeeded = False
            try:
                self.image = self.handle_script(self.image, addfile)
                log.info('generated docker image '+self.image)
                succeeded = True
            finally:
                if self.image is not None and not succeeded:
                    self.cleanup_image(self.image)
        log.info('root image '+self.src_imagename+' ('+self.src_image+')')
        with open(self.image_name_file, 'w') as f:
            f.write(self.image+'\n')

    def prepare_deployment(self):
        log.info('packaging...')
        self.docker(['save', '-o', self.image_file, self.image])
        log.info('stripping '+self.src_imagename+'...')
        docker.strip_image(self.image_file, self.src_image, self.delta_file)
        if self.build_cfg.is_release() or self.build_cfg.is_milestone():
            self.tag_image(True)
        else:
            if not self.build_cfg.do_deploy():
                self.cleanup_image(self.image)

    def repo_host(self):
        return docker.repo_host(self.build_cfg)

    def tag_name(self, tmp=False):
        return docker.tag_name(self.build_cfg, self.gid, self.aid, tmp)

    def tag_image(self, tmp=False):
        tag = self.tag_name(tmp)
        docker.tag_image(self.image, tag, self.docker_force_enabled and not ((self.build_cfg.is_release() or self.build_cfg.is_milestone()) and not tmp))

    def publish(self):
        if self.image is None:
            self.image = get_first_line(self.image_name_file, 'cannot read image id from last build')
            log.info('reading image name from last build: '+self.image)
            if is_existing_file(self.delta_file):
                log.info('reloading image to daemon cache...')
                docker.docker(['load', '-i', self.delta_file])
        repo = self.repo_host()
        if repo is None:
            raise XmakeException('no DOCKER deployment repository configured')
        self.tag_image()
        log.info('publishing to DOCKER repository '+repo+'...')
        resolve_deployment_credentials(self.build_cfg, DOCKERREPO)
        user = self.build_cfg.deploy_user(DOCKERREPO)
        password = self.build_cfg.deploy_password(DOCKERREPO)
        dir = '.'
        if user is not None and password is not None:
            log.info('  using user '+user)
            dir = docker.prepare_dockercfg(user, password, repo)
        success = False
        try:
            tag = self.tag_name()
            log.info('publishing image to '+repo+' ('+tag+')')
            docker.docker(['push', tag], None, dir=dir, home=dir)
            log.info('docker logout '+repo)
            docker.docker(['logout', repo], None, dir=dir, home=dir)
            success = True
        finally:
            if dir is not '.':
                log.info('cleanup login info '+dir)
                shutil.rmtree(dir)
            if success:
                self.cleanup_image(tag)

    def after_PRELUDE(self, build_cfg):
        log.info("artifact id is "+self.aid)
        log.info("group id is    "+self.gid)
        if not is_existing_file(self.build_cfg.export_script()):
            self.prepare_export()
    
    def after_DEPLOY(self, build_cfg):
            if build_cfg.do_deploy():
                repo = build_cfg.export_repo(DOCKERREPO)
                log.info('docker deployment repo is '+str(repo))
                self.publish()

    def build_step(self, img, cmd, priv=False):
        cidfile = os.path.join(self.build_cfg.gen_dir(), 'cid')
        if is_existing_file(cidfile):
            os.remove(cidfile)
        args = ['run', '--cidfile='+cidfile]
        args.extend(['-v', self.context_dir+':/xmake/context:ro'])
        if priv:
            args.extend(['--privileged=true'])
        args.extend([img, 'bash', '-c', cmd])

        def gap(line): return '      '+line
        docker.docker(args, gap, echo=self.echo)
        cid = get_first_line(cidfile, 'cannot read container id')
        # log.info('execution container is '+cid)

        last = [None]

        def gather(line):
            last[0] = line.strip()
        if self._cmd is not None:
            cmd = ['commit', '--change', 'CMD '+self._cmd, cid]
        else:
            cmd = ['commit', cid]
        docker.docker(cmd, gather, echo=True)
        log.info(' ---> '+last[0][:12])
        log.info('Removing intermediate container '+cid[:12])
        self.cleanup_container(cid)
        return last[0]

    def cleanup_image(self, img):
        self._cleanup('rmi', img)

    def cleanup_container(self, cid):
        def ignore(line): return line if self.echo else None
        try:
            log.info('docker rm -f -v '+cid+': echo '+str(self.echo))
            docker.docker(['rm', '-f', '-v', cid], ignore, echo=self.echo)
        except XmakeException:
            pass

    def _stop(self, cmd, cid):
        def ignore(line): return line if self.echo else None
        try:
            log.info('docker '+cmd+' '+cid+': echo '+str(self.echo))
            docker.docker([cmd, cid], ignore, echo=self.echo)
        except XmakeException:
            pass

    def _cleanup(self, cmd, eid):
        def ignore(line): return line if self.echo else None
        try:
            log.info('docker '+cmd+' '+eid+': echo '+str(self.echo))
            docker.docker([cmd, eid], ignore, echo=self.echo)
        except XmakeException:
            pass

    def handle_script(self, img, ifile):
        succeeded = False
        try:
            with open(ifile, 'r') as f:
                no = step = 0

                def handler(line):
                    self._cmd = line
                    return None
                # docker.docker(['inspect', '-f', '{{.Config.Cmd}}', img],handler=handler)
                self._cmd = docker.get_command(img)
                if self._cmd is None:
                    log.info('no command set in docker file')
                else:
                    log.info('found command: '+self._cmd)
                for line in f:
                    no += 1
                    line = line.strip()
                    if not line.startswith('#') and len(line) != 0:
                        ix = line.find(' ')
                        if ix < 0:
                            raise XmakeException('invalid syntax in line '+str(no)+': '+str(line))
                        key = line[:ix]
                        cmd = line[ix:].strip()
                        priv = False
                        step += 1
                        if key == 'RUNPRIVILEGED':
                            priv = True
                        if priv or key == 'RUN':
                            log.info('Step '+str(step)+' : '+line)
                            img = self.build_step(img, cmd, priv)
                        else:
                            raise XmakeException('unknown command '+key+' in line '+str(no)+': '+str(line))
            succeeded = True
        finally:
            if img is not None and not succeeded:
                self.cleanup_image(img)
        return img
