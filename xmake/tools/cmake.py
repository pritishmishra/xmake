import os.path, utils, spi

class tool(spi.ArchiveBasedTool):
    def _import(self):
        return utils.runtime_ga("com.sap.external.org.cmake.%s:cmake:tar.gz" % utils.runtime(), "classifier")

    def _map_installation(self, d, version):
        return os.path.join(d, "cmake-"+version+"-"+utils.runtime())
