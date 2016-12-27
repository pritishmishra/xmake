# i072332
import ExternalTools
import xmake_exceptions
import os.path
import log
import os
import tarfile


class build():
    def __init__(self, build_cfg):
        self.build_cfg = build_cfg
        self._options = {}
        self._cfg = {}
        self._options['sapmake'] = '0.0.1-ms-1'
        self._options['msvc'] = '120'

    def required_tool_versions(self):
        return {'sapmake': self._options['sapmake']}

    def set_options_from_conf(self):
        command = ''
        cfg_name = os.path.join(self.build_cfg.src_dir(), 'props.cfg')
        with open(cfg_name, 'r') as f:
            for line in f:
                command += ' ' + line.strip()

                # Check if property is for project name and saves project name in local conf
                arr0 = line.split(' ')
                if arr0[0] == '-p':
                    arr = arr0[1].split('/')
                    self._cfg['project_name'] = arr[-1].strip()

        return command

    def set_options(self, opts):
        for option in opts:
            if option.find(':') >= 0:
                (key, value) = option.split(':')
                self._options[key] = value
            else:
                self._options['sapmake'] = option

    def run(self):
        log.info('invoking sapmake....')

        perl_opts = self.set_options_from_conf()
        sapmake_home = os.path.join(self.build_cfg.tools()['sapmake'][self._options['sapmake']], 'src')
        sapmake_pl_home = os.path.join(self.build_cfg.src_dir(), 'sapmake', 'sapmk.pl')

        os.chdir(self.build_cfg.component_dir())
        if ExternalTools.OS_Utils.is_UNIX():
            script_name = os.path.join(self.build_cfg.component_dir(), 'run.sh')

            with open(script_name, 'wb+') as f:
                f.write('perl -S %s -src %s -dst %s %s' % (sapmake_pl_home, self.build_cfg.src_dir(), self.build_cfg.gen_dir(), perl_opts))

            rc = log.log_execute(['sh', script_name])
            rc = 0
        else:
            script_name = os.path.join(self.build_cfg.component_dir(), 'run.bat')
            os.environ['PATH'] = sapmake_home + ';' + os.environ['PATH']
            msvc_home = self.build_cfg.tools()['msvc'][self._options['msvc']]
            with open(script_name, 'w') as f:
                f.write('CALL "%s\\VC\\vcvarsall.bat" x86_amd64\n' % msvc_home)
                f.write('perl -S %s -src %s -dst %s %s' % (sapmake_pl_home, self.build_cfg.src_dir(), self.build_cfg.gen_dir(), perl_opts))
            rc = log.log_execute([script_name])

        if rc > 0:
            raise xmake_exceptions.XmakeException('ERR: sapmake returned %s' % str(rc))
        else:
            source_dir = self.build_cfg.gen_dir()
            output_script_name = os.path.join(self.build_cfg.gen_dir(), self._cfg['project_name']) + '.tar.gz'

            with tarfile.open(output_script_name, 'w:gz') as tar:
                tar.add(source_dir, arcname=os.path.basename(source_dir))

        return 0
