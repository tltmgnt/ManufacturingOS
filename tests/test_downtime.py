from copy import deepcopy
import json
from pathlib import Path
import unittest

from manufacturing_os.bundle import build_bundle,verify_bundle
from manufacturing_os.compare import compare_studies
from manufacturing_os.review import render_review
from manufacturing_os.simulation import simulate_batch
from manufacturing_os.study import run_study

ROOT=Path(__file__).resolve().parents[1]


def window(begin,end,unit='h'):
    return {'start':{'value':begin,'unit':unit},'end':{'value':end,'unit':unit}}


class DowntimeTests(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/finite-batch.json').read_text())
        self.spec['batch_size']=3
        self.spec['scenario']['horizon']={'value':5,'unit':'h'}
        self.spec['scenario']['target_good_units']=3
        for index,op in enumerate(self.spec['scenario']['operations']):
            op.update(cycle_time={'value':index+1,'unit':'h'},setup_time={'value':0,'unit':'h'},availability=1,yield_fraction=1,machines=1)
        self.spec['downtime']=[{'operation_id':'finish','machine_id':0,'windows':[window(2,4)]}]

    def test_hand_schedule_defers_whole_processing_cycle(self):
        report=simulate_batch(self.spec)
        self.assertEqual([row['finish_hours'] for row in report['operations'][1]['timeline']],[6,8,10])
        self.assertEqual(report['good_by_horizon'],0)
        self.assertEqual(report['wip_at_horizon'],3)
        self.assertEqual(report['operations'][1]['occupied_fraction_by_machine'][0]['value'],.2)
        self.assertEqual(report['batch_completion_time']['value'],10)

    def test_half_open_boundaries_allow_finish_at_start_and_start_at_end(self):
        self.spec['downtime'][0]['windows']=[window(3,4)]
        report=simulate_batch(self.spec)
        rows=report['operations'][1]['timeline']
        self.assertEqual([row['finish_hours'] for row in rows],[3,6,8])
        self.assertEqual(rows[1]['start_hours'],4)
        self.assertEqual(report['good_by_horizon'],1)

    def test_parallel_machine_uses_earliest_feasible_slot(self):
        self.spec['scenario']['operations'][1]['machines']=2
        self.spec['downtime'][0]['windows']=[window(0,10)]
        rows=simulate_batch(self.spec)['operations'][1]['timeline']
        self.assertEqual([row['machine_id'] for row in rows],[1,1,1])
        self.assertEqual([row['finish_hours'] for row in rows],[3,5,7])

    def test_setup_fits_outside_downtime_and_is_not_counted_during_window(self):
        self.spec['scenario']['operations'][1]['setup_time']={'value':1,'unit':'h'}
        self.spec['downtime'][0]['windows']=[window(0,2)]
        report=simulate_batch(self.spec)
        op=report['operations'][1]
        self.assertEqual(op['setup_intervals'],[{'machine_id':0,'start_hours':2.0,'finish_hours':3.0}])
        self.assertEqual(op['timeline'][0]['finish_hours'],5)
        self.assertEqual(op['occupied_fraction_by_machine'][0]['value'],.6)

    def test_multiple_windows_and_unit_conversion(self):
        self.spec['downtime'][0]['windows']=[window(6,7),window(2,4)]
        report=simulate_batch(self.spec)
        self.assertEqual([row['finish_hours'] for row in report['operations'][1]['timeline']],[6,9,11])
        other=deepcopy(self.spec)
        other['downtime'][0]['windows']=[window(360,420,'min'),window(120,240,'min')]
        self.assertEqual(report['operations'],simulate_batch(other)['operations'])
        self.assertEqual(report['normalized_downtime'],simulate_batch(other)['normalized_downtime'])

    def test_overlapping_zero_negative_windows_rejected(self):
        for windows in [[window(1,3),window(2,4)],[window(1,1)],[window(2,1)],[window(-1,1)]]:
            self.spec['downtime'][0]['windows']=windows
            with self.subTest(windows=windows),self.assertRaises(ValueError):
                simulate_batch(self.spec)

    def test_duplicate_unknown_machine_and_availability_rejected(self):
        cases=[]
        for key,value in [('operation_id','missing'),('machine_id',True),('machine_id',1),('windows',[])]:
            spec=deepcopy(self.spec)
            spec['downtime'][0][key]=value
            cases.append(spec)
        duplicate=deepcopy(self.spec)
        duplicate['downtime']*=2
        cases.append(duplicate)
        reduced=deepcopy(self.spec)
        reduced['scenario']['operations'][1]['availability']=.9
        cases.append(reduced)
        for spec in cases:
            with self.assertRaises(ValueError):
                simulate_batch(spec)

    def test_calendar_work_budget(self):
        self.spec['batch_size']=10000
        for op in self.spec['scenario']['operations']:
            op['machines']=51
        with self.assertRaisesRegex(ValueError,'work units'):
            simulate_batch(self.spec)

    def test_every_processing_and_setup_interval_avoids_windows(self):
        report=simulate_batch(self.spec)
        for op in report['operations']:
            windows=[(row['start']['value'],row['end']['value']) for row in report['normalized_downtime'] if row['operation_id']==op['operation_id']]
            for row in op['timeline']+op['setup_intervals']:
                if row['finish_hours']==row['start_hours']:
                    continue
                for begin,end in windows:
                    self.assertTrue(row['finish_hours']<=begin or row['start_hours']>=end)
        self.assertEqual(report['good_by_horizon']+report['scrapped_by_horizon']+report['wip_at_horizon'],3)

    def test_empty_calendar_does_not_change_scheduled_results(self):
        self.spec['downtime']=[]
        report=simulate_batch(self.spec)
        without=deepcopy(self.spec)
        del without['downtime']
        old=simulate_batch(without)
        self.assertEqual(report['jobs'],old['jobs'])
        self.assertEqual(report['batch_completion_time'],old['batch_completion_time'])
        self.assertNotIn('normalized_downtime',old)

    def test_study_html_comparison_and_bundle_integration(self):
        spec=json.loads((ROOT/'examples/downtime-study.json').read_text())
        spec['uncertainty']['samples']=2
        report=run_study(spec)
        self.assertEqual(report['review_state'],'REVISION_REQUIRED')
        self.assertIn('Scheduled downtime (half-open intervals)',render_review(report))
        self.assertEqual(verify_bundle(build_bundle(spec))['review_state'],'REVISION_REQUIRED')
        before=deepcopy(spec)
        del before['simulation']['downtime']
        comparison=compare_studies(run_study(before),report)
        self.assertIn('SIMULATION_CONFIG_CHANGED',[row['code'] for row in comparison['context_changes']])

    def test_deterministic_and_input_not_mutated(self):
        original=deepcopy(self.spec)
        first=simulate_batch(self.spec)
        self.assertEqual(first,simulate_batch(self.spec))
        self.assertEqual(original,self.spec)
