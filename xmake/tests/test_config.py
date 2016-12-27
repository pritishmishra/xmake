import os

if __name__ == '__main__':
    import sys
    dirname = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dirname + '/../')
    sys.path.append(dirname + '/../../externals')

import unittest
from config import BuildConfig
from config import COMMONREPO, DOCKERREPO, NPMREPO
from xmake_exceptions import XmakeException

class Test(unittest.TestCase):

    def test_import_repos(self):
        nx_repos = ['http://nexus1', 'http://nexus2', 'http://nexus3']
        docker_repos = ['http://docker1', 'http://docker2', 'http://docker3']
        npm_repos = ['http://npm1', 'http://npm2', 'http://npm3']


        # no repos
        cfg = BuildConfig()
        cfg._import_repos = {
            COMMONREPO: None,
            DOCKERREPO: None,
            NPMREPO: None
        }
        assert cfg.import_repos() == None
        assert cfg.import_repos(t=DOCKERREPO) == None
        assert cfg.import_repos(t=NPMREPO) == None

        # no repos productive build
        cfg._productive = True
        assert cfg.import_repos() == None
        assert cfg.import_repos(t=DOCKERREPO) == None
        assert cfg.import_repos(t=NPMREPO) == None

        # no repos
        cfg = BuildConfig()
        cfg._import_repos = {
            COMMONREPO: [],
            DOCKERREPO: [],
            NPMREPO: []
        }
        assert cfg.import_repos() == []
        assert cfg.import_repos(t=DOCKERREPO) == []
        assert cfg.import_repos(t=NPMREPO) == []

        # no repos productive build
        cfg._productive = True
        assert cfg.import_repos() == []
        assert cfg.import_repos(t=DOCKERREPO) == []
        assert cfg.import_repos(t=NPMREPO) == []

        cfg = BuildConfig()
        cfg._import_repos = {
            COMMONREPO: nx_repos,
            DOCKERREPO: docker_repos,
            NPMREPO: npm_repos
        }
        # non productive / non release build
        assert cfg.import_repos() == nx_repos
        assert cfg.import_repos(t=DOCKERREPO) == docker_repos
        assert cfg.import_repos(t=NPMREPO) == npm_repos

        # productive build
        cfg._productive = True
        assert cfg.import_repos() == [nx_repos[0]]
        assert cfg.import_repos(t=DOCKERREPO) == [docker_repos[0]]
        assert cfg.import_repos(t=NPMREPO) == [npm_repos[0]]

        # xmake-ldi release build
        cfg._productive = False
        cfg._release = 'release'
        assert cfg.import_repos() == [nx_repos[0]]
        assert cfg.import_repos(t=DOCKERREPO) == [docker_repos[0]]
        assert cfg.import_repos(t=NPMREPO) == [npm_repos[0]]

        # xmake-dev release build
        cfg._productive = True
        cfg._release = None
        cfg._version_suffix = None
        assert cfg.import_repos() == [nx_repos[0]]
        assert cfg.import_repos(t=DOCKERREPO) == [docker_repos[0]]
        assert cfg.import_repos(t=NPMREPO) == [npm_repos[0]]

    def test_add_import_repo(self):
        nx_repos = ['http://nexus1', 'http://nexus2']
        docker_repos = ['http://docker1', 'http://docker2']

        cfg = BuildConfig()

        # non productive / non release build
        cfg._import_repos = {}
        cfg.add_import_repo(nx_repos[0])
        cfg.add_import_repo(nx_repos[1])
        cfg.add_import_repo(docker_repos[0], DOCKERREPO)
        cfg.add_import_repo(docker_repos[1], DOCKERREPO)
        assert cfg._import_repos[COMMONREPO] == nx_repos
        assert cfg._import_repos[DOCKERREPO] == docker_repos

        # productive build
        cfg._import_repos = {}
        cfg._productive = True
        cfg.add_import_repo(nx_repos[0])
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.add_import_repo(nx_repos[1])
        cfg.add_import_repo(docker_repos[0], DOCKERREPO)
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.add_import_repo(docker_repos[1], DOCKERREPO)

        assert cfg._import_repos[COMMONREPO] == [nx_repos[0]]
        assert cfg._import_repos[DOCKERREPO] == [docker_repos[0]]

        # xmake-ldi release build
        cfg._import_repos = {}
        cfg._productive = False
        cfg._release = 'release'
        cfg.add_import_repo(nx_repos[0])
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.add_import_repo(nx_repos[1])
        cfg.add_import_repo(docker_repos[0], DOCKERREPO)
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.add_import_repo(docker_repos[1], DOCKERREPO)
        assert cfg._import_repos[COMMONREPO] == [nx_repos[0]]
        assert cfg._import_repos[DOCKERREPO] == [docker_repos[0]]

        # xmake-dev release build
        cfg._import_repos = {}
        cfg._productive = True
        cfg._release = None
        cfg._version_suffix = None
        cfg.add_import_repo(nx_repos[0])
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.add_import_repo(nx_repos[1])
        cfg.add_import_repo(docker_repos[0], DOCKERREPO)
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.add_import_repo(docker_repos[1], DOCKERREPO)
        assert cfg._import_repos[COMMONREPO] == [nx_repos[0]]
        assert cfg._import_repos[DOCKERREPO] == [docker_repos[0]]

    def test_set_import_repos(self):
        nx_repos = ['http://nexus1', 'http://nexus2']
        docker_repos = ['http://docker1', 'http://docker2']

        cfg = BuildConfig()

        # non productive / non release build
        cfg._import_repos = {}
        cfg.set_import_repos(nx_repos)
        cfg.set_import_repos(docker_repos, DOCKERREPO)
        assert cfg._import_repos[COMMONREPO] == nx_repos
        assert cfg._import_repos[DOCKERREPO] == docker_repos

        # productive build
        cfg._import_repos = {}
        cfg._productive = True
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.set_import_repos(nx_repos)
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.set_import_repos(docker_repos, DOCKERREPO)

        # xmake-ldi release build
        cfg._import_repos = {}
        cfg._productive = False
        cfg._release = 'release'
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.set_import_repos(nx_repos)
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.set_import_repos(docker_repos, DOCKERREPO)

        # xmake-dev release build
        cfg._import_repos = {}
        cfg._productive = True
        cfg._release = None
        cfg._version_suffix = None
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.set_import_repos(nx_repos)
        with self.assertRaisesRegexp(XmakeException, 'only one repository url is authorized'):
            cfg.set_import_repos(docker_repos, DOCKERREPO)

if __name__ == '__main__':
    unittest.main()
