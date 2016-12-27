import os
import re


class Artifact:
    def __init__(self, gid, aid, version, classifier, extension, path):
        self.gid = gid
        self.aid = aid
        self.version = version
        self.classifier = classifier
        self.extension = extension
        self.path = path

    def __getitem__(self, index):
        return self.__dict__[index]

    @staticmethod
    def parse_path(path, prefix):

        timestampRE = re.compile(r"\d{8}\.\d{6}-\d+")
        stripped_path = timestampRE.sub("SNAPSHOT", path)
        result = re.search('(.*)/([^/]*)/([^/]*)/\\2-\\3-?([^/.]*)\.([^/.]*)$', stripped_path.replace("\\","/"))
        
        if result:
            gid = result.group(1).replace('/', '.')
            aid = result.group(2)
            version = result.group(3)
            classifier = result.group(4)
            extension = result.group(5)
            #log.info("%s %s %s %s %s" % (gid, aid, version, classifier, extension))

            return Artifact(gid, aid, version, classifier, extension, os.path.join(prefix, path))

        result = re.search('(.*)/([^/]*)/([^/]*)/\\2-\\3-?([^/]*)\.([^/.]*)\.([^/.]*)$', stripped_path.replace("\\","/"))
        if result:
            lastextension = result.group(6)
            if lastextension != 'sha1' and lastextension != 'md5':
                gid = result.group(1).replace('/', '.')
                aid = result.group(2)
                version = result.group(3)
                classifier = result.group(4)
                extension =   result.group(5) + '.'  + lastextension
                #log.info("%s %s %s %s %s" % (gid, aid, version, classifier, extension))

                return Artifact(gid, aid, version, classifier, extension, os.path.join(prefix, path))
            
        return None

    @staticmethod
    def gather_artifacts(repository_path):
        artifacts=dict()

        for dirname, _, filenames in os.walk(repository_path):

            # gather information about artifacts in M2 directory
            for filename in filenames:
                repopath = os.path.join(dirname, filename)[len(repository_path)+1:]

                artifact = Artifact.parse_path(repopath, repository_path)
                if artifact:
                    key = "%s:%s:%s" % (artifact.gid, artifact.aid, artifact.version)
                    if key not in artifacts:
                        artifacts[key] = list()
                    artifacts[key].append(artifact)
        return artifacts