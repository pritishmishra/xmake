'''
@author: I072332
'''
import os.path, utils, spi

class tool(spi.ArchiveBasedTool):
    def _import(self):
        return "com.sap.prd.sapmake:sapmake:tar.gz"

    def _map_installation(self, d, version):
        return os.path.join(d, "sapmake-"+version)
