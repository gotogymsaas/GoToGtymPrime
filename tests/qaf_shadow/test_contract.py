import copy
import importlib.util
import json
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('qaf_validate', ROOT / '.github/qaf/validate.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.p = json.loads((ROOT / '.github/qaf/scanner-profile.json').read_text())
        self.w = yaml.load((ROOT / '.github/workflows/qaf-shadow.yml').read_text(), Loader=yaml.BaseLoader)
    def test_profile(self):
        v.validate(self.p)
    def test_cross_project_denied(self):
        for project in ('appdesplegada', 'GoToGtymPrime', 'gotogymdevelopers'):
            if project != v.PROJECT:
                p = copy.deepcopy(self.p)
                p.update(project_id=project, repository='gotogymsaas/' + project)
                with self.assertRaises(ValueError): v.validate(p)
    def test_pending_is_not_operational(self):
        if self.p['status'] != 'OPERATOR_REVIEWED':
            with self.assertRaises(ValueError): v.validate(self.p, True)
    def test_operational_requires_all_versions(self):
        p = copy.deepcopy(self.p)
        p['status'] = 'OPERATOR_REVIEWED'
        p['tools']['gitleaks']['version_stdout_sha256'] = None
        with self.assertRaises(ValueError): v.validate(p, True)
    def test_shell_injection_denied(self):
        for tool in v.COMMANDS:
            p = copy.deepcopy(self.p)
            p['tools'][tool]['allowed_command'] = ['bash', '-c', 'arbitrary']
            with self.assertRaises(ValueError): v.validate(p)
    def test_mutable_tooling_denied(self):
        self.p['tooling_ref'] = 'main'
        with self.assertRaises(ValueError): v.validate(self.p)
    def test_workflow_ref_and_scope(self):
        self.assertEqual(set(self.w['on']), {'workflow_dispatch'})
        emit = self.w['jobs']['emit']
        self.assertEqual(emit['uses'], 'gotogymsaas/cybersecurity/.github/workflows/qaf-emitter.yml@' + v.TOOLING)
        self.assertEqual(emit['with']['tooling_ref'], v.TOOLING)
        self.assertEqual(emit['with']['project_id'], v.PROJECT)
        self.assertEqual(emit['needs'], 'preflight')
        for job in self.w['jobs'].values():
            self.assertIn('refs/heads/main', job['if'])
            self.assertIn('gotogymsaas/' + v.PROJECT, job['if'])
    def test_least_privilege_and_no_raw_artifacts(self):
        self.assertEqual(self.w['permissions'], {'contents': 'read'})
        self.assertEqual(self.w['jobs']['emit']['permissions'], {'contents':'read', 'id-token':'write'})
        self.assertEqual(set(self.w['jobs']['emit']['secrets']), {'QAF_TOOLING_READ_TOKEN'})
        raw = (ROOT / '.github/workflows/qaf-shadow.yml').read_text()
        for forbidden in ('upload-artifact', 'secrets: inherit', 'pull_request_target', 'contents: write'):
            self.assertNotIn(forbidden, raw)
    def test_preflight_binds_checkout_to_event(self):
        steps = self.w['jobs']['preflight']['steps']
        self.assertEqual(steps[0]['with']['ref'], '${{ github.sha }}')
        self.assertEqual(steps[0]['with']['persist-credentials'], 'false')
        self.assertIn('--operational', steps[1]['run'])
    def test_no_credential_literals_in_new_integration(self):
        import re
        patterns = (r'gh[pousr]_[A-Za-z0-9]{30,}', r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', r'AccountKey=[A-Za-z0-9+/=]{20,}')
        for path in (ROOT / '.github/qaf').rglob('*'):
            if path.is_file() and path.suffix in ('.py', '.json'):
                for pattern in patterns:
                    self.assertIsNone(re.search(pattern, path.read_text()))

if __name__ == '__main__': unittest.main()
