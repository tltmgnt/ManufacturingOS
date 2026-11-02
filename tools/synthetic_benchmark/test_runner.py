import json
from pathlib import Path
import sys
import unittest
import runner

class RunnerTests(unittest.TestCase):
    def execute(self,code,**kwargs):
        return runner.run([sys.executable,'-c',code],{'case_id':'D01'},**kwargs)
    def test_valid_stdin_and_workdir(self):
        r=self.execute('import json,sys,os; x=json.load(sys.stdin); x["files"]=os.listdir(); print(json.dumps(x))')
        self.assertEqual(r['status'],'OK');self.assertEqual(r['submission']['case_id'],'D01')
        self.assertNotIn('oracle',r['submission']['files']);self.assertGreater(r['cpu_seconds'],0)
    def test_wall_timeout(self):
        self.assertEqual(self.execute('import time;time.sleep(10)',wall=.05)['status'],'WALL_TIMEOUT')
    def test_cpu_limit(self):
        r=self.execute('while True: pass',cpu=1,wall=4)
        self.assertEqual(r['status'],'PROCESS_FAILURE');self.assertLess(r['wall_seconds'],4)
    def test_output_limit(self):
        self.assertNotEqual(self.execute('print("x"*1000000)')['status'],'OK')
    def test_nonzero_exit(self):
        self.assertEqual(self.execute('raise SystemExit(3)')['returncode'],3)
    def test_invalid_json(self):
        for text in ('[]','NaN','{"a":1,"a":2}','invalid'):
            with self.subTest(text=text):
                self.assertEqual(self.execute('print('+repr(text)+')')['status'],'INVALID_OUTPUT')
    def test_memory_limit(self):
        r=self.execute('x=bytearray(200*1024**2)',memory=64*1024**2)
        self.assertEqual(r['status'],'PROCESS_FAILURE')

if __name__=='__main__':unittest.main()
