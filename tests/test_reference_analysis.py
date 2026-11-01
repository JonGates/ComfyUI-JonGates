import importlib.util
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('reference_analysis',Path(__file__).parents[1]/'nodes/reference_analysis.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReferenceAnalysisTests(unittest.TestCase):
    def test_required_fields_and_exclusion_of_unrequested_content(self):
        data={k:'  描述  ' for k in module.FIELDS}
        data['watermark']='DO NOT PASS THIS TO THE GENERATOR'
        normalized=json.loads(module.validate_analysis(json.dumps(data)))
        self.assertEqual(set(normalized),set(module.FIELDS))
        self.assertTrue(all(v=='描述' for v in normalized.values()))

    def test_partial_wrong_type_or_empty_fields_fail_loudly(self):
        for value in ['',None,[],3]:
            data={k:'描述' for k in module.FIELDS}
            data['source_items']=value
            with self.assertRaises(ValueError):module.validate_analysis(json.dumps(data))
        with self.assertRaises(ValueError):module.validate_analysis('{}')
        with self.assertRaises(ValueError):module.validate_analysis('not JSON')


if __name__=='__main__':unittest.main()
