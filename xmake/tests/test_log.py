import sys
import os

if __name__ == '__main__':
    import os
    dirname = os.path.dirname(os.path.realpath(__file__))
    sys.path.append(dirname + '/../')
    sys.path.append(dirname + '/../../externals')

import unittest
import time
from threading import Event
from mock import patch, Mock, MagicMock, call
import log
from log import Tail
from config import BuildConfig

# mock logging module
INFO = MagicMock()
ERROR = MagicMock()
WARNING = MagicMock()
log.logger = MagicMock()

class Test(unittest.TestCase):
    @patch('log.logging')
    def test_logGuessLevel(self, logging_mock):
        logging_mock.INFO = INFO
        logging_mock.ERROR = ERROR
        logging_mock.WARNING = WARNING

        trueTestSet = (
            {'text': 'INFORMATION: blabla', 'level': INFO},
            {'text': 'information: blabla', 'level': INFO},
            {'text': 'inFo: blabla', 'level': INFO},
            {'text': '(INFORMATION) blabla', 'level': INFO},
            {'text': '(information) blabla', 'level': INFO},
            {'text': '(inFo) blabla', 'level': INFO},
            {'text': '[INFORMATION] blabla', 'level': INFO},
            {'text': '[information] blabla', 'level': INFO},
            {'text': '[inFo] blabla', 'level': INFO},
            {'text': 'WARNING: blabla', 'level': WARNING},
            {'text': 'warning: blabla', 'level': WARNING},
            {'text': 'warN: blabla', 'level': WARNING},
            {'text': '(WARNING) blabla', 'level': WARNING},
            {'text': '(warning) blabla', 'level': WARNING},
            {'text': '(warN) blabla', 'level': WARNING},
            {'text': '[WARNING] blabla', 'level': WARNING},
            {'text': '[warning] blabla', 'level': WARNING},
            {'text': '[warN] blabla', 'level': WARNING},
            {'text': 'ERROR: blabla', 'level': ERROR},
            {'text': 'error: blabla', 'level': ERROR},
            {'text': 'Err: blabla', 'level': ERROR},
            {'text': '(ERROR) blabla', 'level': ERROR},
            {'text': '(error) blabla', 'level': ERROR},
            {'text': '(Err) blabla', 'level': ERROR},
            {'text': '[ERROR] blabla', 'level': ERROR},
            {'text': '[error] blabla', 'level': ERROR},
            {'text': '[Err] blabla', 'level': ERROR}
        )
        falseTestSet = (
            '  error',
            'file warn'
        )

        old_logger_log = log.logger.log
        old_log_message = log._message
        for test in trueTestSet:
            log.logger.log = MagicMock()
            log._message = MagicMock()
            log._logGuessLevel(test['text'])
            log._message.assert_called_once_with(None, 'blabla')
            log.logger.log.assert_called_once_with(test['level'], log._message())

        for text in falseTestSet:
            log.logger.log = MagicMock()
            log._message = MagicMock()
            log._logGuessLevel(text)
            log._message.assert_called_once_with(None, text)
            log.logger.log.assert_called_once_with(INFO, log._message())

        # undo monkey patches to not affect other test cases
        log.logger.log = old_logger_log
        log._message = old_log_message


    @patch('log.logging')
    @patch('log.open')
    @patch('log.os')
    def test_osenviron_expand_variables(self, os_mock, open_mock, logging_mock):
        os_mock.environ = {
            'XMAKE_ENV_FILE':'somefile',
            'PATH': 'TATA'
        }
        open_mock.return_value = MagicMock(spec=file)
        file_mock = open_mock.return_value.__enter__.return_value
        file_mock.readlines.return_value = [
            'PATH=$PATH:TOTO:TITI:TUTU'
        ]

        env = log.expand_variables(None)
        assert(env['XMAKE_ENV_FILE'] == 'somefile')
        assert(env['PATH'] == 'TATA:TOTO:TITI:TUTU')

        os_mock.environ = {
            'XMAKE_ENV_FILE':'somefile',
            'PATH': 'TATA'
        }
        file_mock.readlines.return_value = [
            'BABA=$PATH',
            'PATH=$PATH:TOTO:TITI:TUTU:$BABA'
        ]
        env = log.expand_variables(None)
        assert(env['XMAKE_ENV_FILE'] == 'somefile')
        assert(env['BABA'] == 'TATA')
        assert(env['PATH'] == 'TATA:TOTO:TITI:TUTU:TATA')

        os_mock.environ = {
            'XMAKE_ENV_FILE':'somefile',
            'PATH': 'TATA'
        }
        file_mock.readlines.return_value = [
            'RIRI=$COCO',
            'BABA=$PATH',
            'PATH=$PATH:TOTO:TITI:TUTU:$BABA'
        ]
        env = log.expand_variables(None)
        assert(env['XMAKE_ENV_FILE'] == 'somefile')
        assert(env['BABA'] == 'TATA')
        assert(env['PATH'] == 'TATA:TOTO:TITI:TUTU:TATA')
        assert(not hasattr(env, 'RIRI'))    # $COCO does not exist

        os_mock.environ = {
            'XMAKE_ENV_FILE':'somefile',
            'PATH': '#'
        }
        file_mock.readlines.return_value = [
            'La9=$Lb8$Lb7$Lb6$Lc5$Ld4$Le3$Lf2$Lg1',
            'La8=$Lb7$Lb6$Lc5$Ld4$Le3$Lf2$Lg1',
            'La7=$Lb6$Lc5$Ld4$Le3$Lf2$Lg1',
            'Lb6=$Lc5$Ld4$Le3$Lf2$Lg1',
            'Lc5=$Ld4$Le3$Lf2$Lg1',
            'Ld4=$Le3$Lf2$Lg1',
            'Le3=$Lf2$Lg1',
            'Lf2=$Lg1',
            'Lg1=$PATH'
        ]
        env = log.expand_variables(None)
        assert(env['XMAKE_ENV_FILE'] == 'somefile')
        assert(not hasattr(env, 'La8')) #too deeper to be managed
        assert(not hasattr(env, 'La9')) #too deeper to be managed

        os_mock.environ = {
            'XMAKE_ENV_FILE':'somefile',
            'PATH': '#'
        }
        file_mock.readlines.return_value = [
            'L2=$L1',
            'L1=$L2'
        ]
        env = log.expand_variables(None)
        assert(env['XMAKE_ENV_FILE'] == 'somefile')
        assert(not hasattr(env, 'L2')) #circular ref
        assert(not hasattr(env, 'L1')) #circular ref

        # check os.environ not corrupter after two calls of expand_variables
        os_mock.environ = {
            'XMAKE_ENV_FILE':'somefile',
            'PATH': '/home/caissani'
        }
        file_mock.readlines.return_value = [
            'PATH=$PATH:/home/jmaqueda'
        ]
        env = log.expand_variables(None)
        assert(env['PATH'] == '/home/caissani:/home/jmaqueda')
        file_mock.readlines.return_value = [
            'PATH=$PATH:/home/fskhiri'
        ]
        env = log.expand_variables(None)
        assert(env['PATH'] == '/home/caissani:/home/fskhiri')

        file_mock.readlines.return_value = [
            'MAVEN_OPTS=-Xmx512m -XX:MaxPermSize=350m'
        ]
        env = log.expand_variables(None)
        assert(env['MAVEN_OPTS'] == '-Xmx512m -XX:MaxPermSize=350m')

    @patch('log.logging')
    @patch('log.open')
    def test_expand_variables(self, open_mock, logging_mock):
        open_mock.return_value = MagicMock(spec=file)
        file_mock = open_mock.return_value.__enter__.return_value
        file_mock.readlines.return_value = [
            'PATH=$TATA:TOTO:TITI:TUTU'
        ]

        env = log.expand_variables({'XMAKE_ENV_FILE':'somefile', 'TATA':'TATA'})
        assert(env['PATH'] == 'TATA:TOTO:TITI:TUTU')

    @patch('log._logGuessLevel')
    @patch('log._TailThread.tail_F')
    def test_tailer_stop(self, tail_F_mock, logGuessLevel_mock ):
        # The goal of this test is to disable tailing from the Tail class in multithreaded and ensure that the stop method tails/flushs well 
        # when the thread created by the start() method had not time for reading the tailed file if the stop() was called to quickly 
        
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'samples', 'sample.to_be_tailed')
        testResult={'position':0, 'isEqual':True}
        with open(filename) as fileInput:
            def mocked__logGuessLevel(msg, prefix=None):
                if fileInput.readline()!=msg: testResult['isEqual']=False
                testResult['position']=fileInput.tell()
            
            logGuessLevel_mock.side_effect=mocked__logGuessLevel
            
            tail_F_mock.side_effect=None            
            tailed_file=Tail(None,filename)
            tailed_file.start(True)
            assert(logGuessLevel_mock.called==0)
            tailed_file.stop()
        assert(testResult['isEqual'])
        assert(os.path.getsize(filename)==testResult['position'])
        assert(logGuessLevel_mock.called)

    @patch('log._logGuessLevel')
    @patch('log.open')
    def test_tailer(self,  open_mock, logGuessLevel_mock):
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'samples', 'sample.to_be_tailed')
        testResult={'position':0, 'isEqual':True}
        with open(filename) as fileInput:
            def mocked__logGuessLevel(msg, prefix=None):
                if fileInput.readline()!=msg: testResult['isEqual']=False
                testResult['position']=fileInput.tell()                            
            logGuessLevel_mock.side_effect=mocked__logGuessLevel
            
            tailed_file=Tail(None,filename)
            
            tailer_param={'tailer':tailed_file}
            def mocked_open(file, access_mode="r", buffering=0):
                tailed_file.reader.stopTailingOpenLoop.set()
                return open(file, access_mode, buffering)
            open_mock.side_effect=mocked_open

            tailed_file.start(True)
            # Ensure that everything was read by thte thread and that not data remains to be read
            tailed_file.reader.stopTailingReadingLoop.set()
            #tailed_file.reader.stop(False)
            if tailed_file.reader.is_alive(): tailed_file.reader.join()

            assert(testResult['isEqual'])
            assert(os.path.getsize(filename)==testResult['position'])
            assert(logGuessLevel_mock.called)
            
            # file was reazd, nothing should be read anymore
            logGuessLevel_mock.reset_mock()
            tailed_file.stop()
            assert(logGuessLevel_mock.called==0)        

    @patch('log._logGuessLevel')
    @patch('log.open')
    def test_tailer_empty(self,  open_mock, logGuessLevel_mock):
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'samples', 'empty.to_be_tailed')
        testResult={'position':0, 'isEqual':True}
        with open(filename) as fileInput:
            def mocked__logGuessLevel(msg, prefix=None):
                if fileInput.readline()!=msg: testResult['isEqual']=False
                testResult['position']=fileInput.tell()                            
            logGuessLevel_mock.side_effect=mocked__logGuessLevel
            
            tailed_file=Tail(None,filename)
            
            tailer_param={'tailer':tailed_file}
            def mocked_open(file, access_mode="r", buffering=0):
                tailed_file.reader.stopTailingOpenLoop.set()
                return open(file, access_mode, buffering)
            open_mock.side_effect=mocked_open

            tailed_file.start(True)
            # Ensure that everything was read by thte thread and that not data remains to be read
            tailed_file.reader.stopTailingReadingLoop.set()
            #tailed_file.reader.stop(False)
            if tailed_file.reader.is_alive(): tailed_file.reader.join()

            assert(testResult['isEqual'])
            assert(os.path.getsize(filename)==testResult['position'])
            assert(logGuessLevel_mock.called==0)
            
            # file was reazd, nothing should be read anymore
            logGuessLevel_mock.reset_mock()
            tailed_file.stop()
            assert(logGuessLevel_mock.called==0)

    @patch('log._logGuessLevel')
    @patch('log.os.path.walk')
    def test_monitoring(self,  walk_mock, logGuessLevel_mock):
        wait=0.01
        build_cfg = BuildConfig()
        build_cfg.cfg_dir = MagicMock(return_value=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples'))
        build_cfg.component_dir = MagicMock(return_value=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'samples'))

        testResult={'detected':False, 'notify_caller':Event()}

        def mocked_walk(path, visit, arg):
            arg[1]['change']=True
        walk_mock.side_effect=mocked_walk
        def mocked__logGuessLevel(msg, prefix=None):
            if msg==log._MonitoringWorker.MESSAGE_ALIVE.format(wait): 
                testResult['detected']=True
                testResult['notify_caller'].set()
        logGuessLevel_mock.side_effect=mocked__logGuessLevel

        log.logging_monitoring_enable(build_cfg, wait)
        
        testResult['notify_caller'].wait(60) # should not wait so much... maximum value and in this case, should fail in the assert below
        
        log._logging_monitoring=None
        
        assert(testResult['detected'])

        
if __name__ == '__main__':

    unittest.main()
