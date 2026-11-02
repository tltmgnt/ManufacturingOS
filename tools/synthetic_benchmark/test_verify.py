import hashlib
import json
from pathlib import Path
import statistics
import tempfile
import unittest
import benchmark as m
from verify import verify

class VerificationTests(unittest.TestCase):
    def fixture(self,root):
        rows=[]
        for t in m.generate(2):
            o=m.oracle(t)
            for k in m.LAYERS:
                s=m.participant(t,k)
                rows.append({'block':t['block'],'kind':t['kind'],'condition':k,
                    'candidate_evaluations':s['evaluations'],'execution_status':'OK',
                    'cpu_seconds':.01,'wall_seconds':.02,'submission':s,**m.score(t,o,s)})
        summary={'blocks':2,'source_sha256':hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),
                 'scores':{k:statistics.mean(r['justified'] for r in rows if r['condition']==k) for k in m.LAYERS}}
        (root/'records.json').write_text(json.dumps(rows))
        (root/'summary.json').write_text(json.dumps(summary))
        return rows
    def test_recomputes_and_rejects_edited_score(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rows=self.fixture(root)
            self.assertEqual(verify(root)['executions'],112)
            rows[0]['justified']=1-rows[0]['justified']
            (root/'records.json').write_text(json.dumps(rows))
            with self.assertRaisesRegex(ValueError,'recorded score'):verify(root)
    def test_rejects_missing_record(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rows=self.fixture(root)
            (root/'records.json').write_text(json.dumps(rows[:-1]))
            with self.assertRaisesRegex(ValueError,'incomplete'):verify(root)
    def test_rejects_wrong_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            s=json.loads((root/'summary.json').read_text());s['source_sha256']='0'*64
            (root/'summary.json').write_text(json.dumps(s))
            with self.assertRaisesRegex(ValueError,'source digest'):verify(root)

if __name__=='__main__':unittest.main()
