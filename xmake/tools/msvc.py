'''
Created on 21.07.2014

@author: D051236
'''

import pickle
import re
import os
import subprocess
import sys

from spi import Tool
from xmake_exceptions import XmakeException
from utils import is_existing_directory

import log

'''
Usage example:
  request installation: 
          build_cfg.tools()['msvc']['100']
  request modified environment:
          msvc=self.build_cfg.tools()['msvc']
          log.info( 'found msvc: '+msvc['100'])
          env=msvc.impl.extract_msvc_env(msvc['100'],'amd64')

'''

class tool(Tool):
    def __init__(self, tools, toolid):
        Tool.__init__(self, tools, toolid)
        self.printenv=False
        self.versions = { 100: "VS100COMNTOOLS",
                          '100': "VS100COMNTOOLS",
                          '2010': "VS100COMNTOOLS",

                          110: "VS110COMNTOOLS",
                          '110': "VS110COMNTOOLS",
                          '2012': "VS110COMNTOOLS",

                          120: "VS120COMNTOOLS",
                          '120': "VS120COMNTOOLS",
                          '2013': "VS120COMNTOOLS"
                        }

        self.archs    = [ "amd64", "x86" ]

    def tool(self, version):
        self._tools._fail_if_not_windows('msvc')
        try:
            environment_variable = self.versions[version]
        except KeyError:
            log.error("visual studio version '%s' is not supported" % (version))
            raise XmakeException("unsupported visual studio version: %s" % version)
        
        if os.environ.has_key(environment_variable):
            visual_studio_inst_dir = os.environ[environment_variable]
            if not is_existing_directory(visual_studio_inst_dir):
                log.error("visual studio '%s' not found in '%s=%s'. Either unset environment variable '%s' or change it" % (version, environment_variable, visual_studio_inst_dir, environment_variable))
                raise XmakeException("visual studio '%s' not found in '%s=%s'" % (version, environment_variable, visual_studio_inst_dir))
            visual_studio_inst_dir = os.path.abspath(os.path.join(visual_studio_inst_dir, '..', '..'))
        else:
            visual_studio_inst_dir = r"C:\Program Files (x86)\Microsoft Visual Studio "+environment_variable[2:4]+"."+environment_variable[4:5]
            if not is_existing_directory(visual_studio_inst_dir):
                log.error("visual studio version '%s' not found in the default folder '%s'. Set environment variable '%s' or install visual studio in the default folder" % (version, visual_studio_inst_dir, environment_variable))
                raise XmakeException("visual studio '%s' not found in the default folder '%s'" % (version, visual_studio_inst_dir))
        return visual_studio_inst_dir

    def extract_msvc_env(self, vs_inst_path, arch):
        """ extracts the msvc environment variables out of the local installation
            and returns them as a dict
        """

        if arch not in self.archs:
            log.error("invalid architecture provided: %s" % arch)
            raise XmakeException("invalid architecture provided: %s" % arch)
        log.info("looking up env for "+vs_inst_path)
        vc_vars_all = os.path.normpath(os.path.join(vs_inst_path, "VC", "vcvarsall.bat"))
        if not os.path.exists(vc_vars_all):
            log.error("vcvarsall.bat not found")
            raise XmakeException("vcvarsall.bat not found")

        cmd = subprocess.Popen(args=["cmd.exe"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        cmd.stdin.write('"%s" %s\n' % (vc_vars_all, arch))
        cmd.stdin.write('''"%s" -c "import pickle, os; print '---{1}---\\n{0}\\n---{1}---'.format(pickle.dumps(dict(os.environ), -1).encode('base64'), 'ENV')"\n''' % sys.executable)
        cmd.stdin.close()
        output = cmd.stdout.read()
        rc = cmd.wait()

        if rc != 0:
            log.error("could not determine msvc environment")
            raise XmakeException("could not determine msvc environment")

        match = re.search("---ENV---(.*)---ENV---", output, re.DOTALL)

        if match is None:
            log.error("getting environment failed")
            raise XmakeException("getting environment failed")

        environ_data = match.group(1)
        environ = pickle.loads(environ_data.strip().decode("base64"))
        
        if self.printenv:
            log.info("environment modifications: ")
            for v in environ.keys():
                n=environ[v]
                if os.environ.has_key(v):
                    if os.environ[v]!=n:
                        log.info("  modified: "+v+"="+os.environ[v]+" -> "+n)
                else:
                    log.info("  new     : "+v+"="+n)
                
        return environ
