import os

if __name__ == '__main__':
    import sys
    dirname = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dirname + '/../')
    sys.path.append(dirname + '/../../externals')

import unittest
from config import BuildConfig
import bootstrap
from mock import patch, Mock, MagicMock, call


class Test(unittest.TestCase):

    @patch('bootstrap.log')
    def test_prepare_args(self, log_mock):
        return_args = bootstrap.prepare_args(BuildConfig(), '', [])
        assert len(return_args) == 0

        return_args = bootstrap.prepare_args(BuildConfig(), '', ['--xmake-version', '1.0.0'])
        assert len(return_args) == 2
        assert '--xmake-version' in return_args
        assert '1.0.0' in return_args

        build_cfg = BuildConfig()
        build_cfg._xmake_version = '1.0.0'
        return_args = bootstrap.prepare_args(build_cfg, '', [])
        assert len(return_args) == 2
        assert '--xmake-version' in return_args
        assert '1.0.0' in return_args

        build_cfg = BuildConfig()
        build_cfg._xmake_version = '1.0.0'
        input_args = ['-arg1', 'val1', '-arg2', 'val2', '--', 'postdash']
        indexOfDashDash = input_args.index('--')
        indexOfPostDash = input_args.index('postdash')
        return_args = bootstrap.prepare_args(build_cfg, '', input_args)
        assert len(return_args) == 8  # 6 + 2 (--xmake-version 1.0.0)
        assert '--xmake-version' in return_args
        assert '1.0.0' in return_args
        assert indexOfDashDash == return_args.index('--xmake-version')
        assert indexOfDashDash + 1 == return_args.index('1.0.0')
        assert indexOfDashDash + 2 == return_args.index('--')
        assert indexOfPostDash + 2 == return_args.index('postdash')

if __name__ == '__main__':
    unittest.main()
