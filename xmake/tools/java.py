from ExternalTools import OS_Utils
from os.path import join,isdir
from spi import ArchiveBasedTool
from os import listdir
import utils

class tool(ArchiveBasedTool):
    def _import(self):
        return utils.runtime_ga("com.oracle.download.java:jdk:tar.gz", "classifier", "linux-x64" if OS_Utils.is_UNIX() else "windows-x64")
    def _map_installation(self,d,version):
        # if root directory only containn 1 subdir, then the jdk java_home is this subdir otherwise the jdk_javahome is the install dir d
        installationDirectoryContent=listdir(d)
        if(len(installationDirectoryContent)!=1): return d
        javaHomeToBeReturned=join(d,installationDirectoryContent[0]);
        if(isdir(javaHomeToBeReturned)): return javaHomeToBeReturned
        return d;
    