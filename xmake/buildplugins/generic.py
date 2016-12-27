import shutil
import string
import os
import re
import xmake_exceptions
import inst
import log


class build:
    def _expandVariables(self, variable):
        dico = dict((k, v) for k, v in dict(self.build_cfg.__dict__, **self._tempDico).items() if v is not None)
        variable = os.path.expandvars(variable)
        while True:
            variable = string.Template(variable).substitute(dico)
            isExpandableRE = re.search(r'\${.+}', variable)
            if not isExpandableRE:
                break
        return variable

    def _readConfig(self):
        for buildConfig in self._options['configs'].values():
            with open(buildConfig, 'r') as f:
                lines = [l for l in (line.strip() for line in f) if l and not l.startswith('#')]
            for i in range(0, len(lines)):
                sectionRE = re.search(r'^\s*\[(.+?)\]', lines[i])
                if not sectionRE:
                    continue
                section = sectionRE.group(1)
                for j in range(i+1, len(lines)):
                    sectionRE = re.search(r'^\s*\[(.+?)\]', lines[j])
                    if sectionRE:
                        i = j - 1
                        break
                    if section == 'import_tools':
                        (platform, tool, destination) = [x.strip() for x in lines[j].split('|')]
                        if not (platform == 'all' or platform == self.build_cfg.runtime() or platform == self.build_cfg._family):
                            continue
                        (name, GAV) = [x.strip() for x in tool.split('=')]
                        self._options['tools'][name] = (GAV, destination)
                    elif section == 'import':
                        (platform, component, destination) = [x.strip() for x in lines[j].split('|')]
                        if not (platform == 'all' or platform == self.build_cfg.runtime() or platform == self.build_cfg._family):
                            continue
                        (name, GAV) = [x.strip() for x in component.split('=')]
                        self._options['components'][name] = (GAV, destination)
                    elif section == 'build':
                        (platform, command) = [x.strip() for x in lines[j].split('|', 1)]
                        if not (platform == 'all' or platform == self.build_cfg.runtime() or platform == self.build_cfg._family):
                            continue
                        self._options['commands'].append(command)
                    elif section == 'export':
                        pass
                    elif section == 'environment':
                        (platform, environment) = [x.strip() for x in lines[j].split('|')]
                        if not (platform == 'all' or platform == self.build_cfg.runtime() or platform == self.build_cfg._family):
                            continue
                        (key, value) = [x.strip() for x in environment.split('=')]
                        self._options['environments'][key] = value
                    else:
                        raise xmake_exceptions.XmakeException('ERR: section [%s] is unknow in %s' % (section, self._options['parameters']['config']))

    def _writeConfig(self):
        if 'flavor' in self._options['parameters']:
            for flavor in [f.strip() for f in self._options['parameters']['flavor'].split(',')]:
                templateFile = os.path.join(inst.get_installation_dir(), 'xmake', 'template', '%s.cfg' % flavor)
                configFile = os.path.join(self.build_cfg.cfg_dir(), '%s.cfg' % flavor)
                if not os.path.isfile(configFile) and os.path.isfile(templateFile):
                    shutil.copy(templateFile, configFile)
                if os.path.isfile(configFile):
                    self._options['configs'][flavor] = configFile
        elif 'config' in self._options['parameters']:
            self._options['configs']['user'] = self._expandVariables(self._options['parameters']['config'])
        else:
            for f in os.listdir(self.build_cfg.cfg_dir()):
                if f.endswith('.cfg'):
                    self._options['configs'][f[:-4]] = os.path.join(self.build_cfg.cfg_dir(), f)
            if 'du' not in self._options['configs'] and os.path.isfile(os.path.join(self.build_cfg.src_dir(), 'du.xs')):
                shutil.copy(os.path.join(inst.get_installation_dir(), 'xmake', 'template', 'du.cfg'), os.path.join(self.build_cfg.cfg_dir(), 'du.cfg'))
                self._options['configs']['du'] = os.path.join(self.build_cfg.cfg_dir(), 'du.cfg')
        if not self._options['configs']:
            raise xmake_exceptions.XmakeException('No flavor defined and no config file found. Add argument -- flavor=<your_flavor> where <your_flavor> has one of these values "node", "ant", "cmake", "du"')

    def __init__(self, build_cfg):
        self.build_cfg = build_cfg
        self._options = {}
        (self._options['tools'], self._options['components'], self._options['configs'], self._options['environments'], self._options['required_tools'], self._options['parameters'], self._options['commands']) = ({}, {}, {}, {}, {}, {}, [])
        if self.build_cfg.build_args():
            for arg in self.build_cfg.build_args():
                (key, value) = arg.split('=')
                self._options['parameters'][key] = value
        self._tempDico = {}
        self._tempDico['xmake_component_dir'] = self.build_cfg.component_dir()
        self._tempDico['xmake_src_dir'] = self.build_cfg.src_dir()
        self._tempDico['xmake_gen_dir'] = self.build_cfg.gen_dir()
        self._tempDico['xmake_import_dir'] = self.build_cfg.import_dir()
        self._tempDico['xmake_runtime'] = self.build_cfg.runtime()
        for key, value in self.build_cfg.variant_info().iteritems():
            self._tempDico[key] = value
        self._writeConfig()
        if 'du' in self._options['configs']:
            duFile = os.path.join(self.build_cfg.src_dir(), 'du.xs')
            with open(duFile, 'r') as f:
                for line in f:
                    if not line.strip() or line.startswith('#'):
                        continue
                    (key, value) = [x.strip() for x in line.split('=')]
                    self._tempDico[key] = value
        self._readConfig()
        if len(self._options['tools']):
            for name in self._options['tools']:
                (GAV, destination) = (self._expandVariables(self._options['tools'][name][0]), self._expandVariables(self._options['tools'][name][1]))
                gav = GAV.split(':')
                (group, artifact, version) = gav[:3]
                type = gav[3] if len(gav) > 3 and gav[3] else 'tar.gz'
                classifier = gav[4] if len(gav) > 4 else ''
                self._options['required_tools'][name] = version
                if classifier:
                    self.build_cfg.tools().declare_tool(name, '%s:%s:%s:%s' % (group, artifact, type, classifier), destination)
                else:
                    self.build_cfg.tools().declare_tool(name, '%s:%s:%s' % (group, artifact, type), destination)

    def set_options(self, opts):
        for option in opts:
            if option.find(':') >= 0:
                (key, value) = option.split(':')
                self._options['parameters'][key] = value

    def required_tool_versions(self): return self._options['required_tools']

    def run(self):
        self._clean_if_requested()

        for tool, version in self._options['required_tools'].iteritems():
            self._tempDico['xmake_%s_dir' % tool] = self.build_cfg.tools()[tool][version]

        def add_tool(tid, d): self._tempDico['xmake_%s_dir' % tid] = d
        self._handle_configured_tools(add_tool)
        for key, value in self._options['environments'].iteritems():
            (key, value) = (self._expandVariables(key), self._expandVariables(value))
            self._tempDico[key] = os.environ[key] = value

        for command in self._options['commands']:
            command = self._expandVariables(command)
            log.info('########################## ')
            log.info('# Generic plugin, running: %s' % command)
            log.info('########################## ')
            rc = log.log_execute_shell(command)
            if rc > 0:
                raise xmake_exceptions.XmakeException('ERR: command "%s" returned %s' % (command, str(rc)))
        return 0
