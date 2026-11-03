"""Validate reviewed metadata; never execute profile commands."""
import argparse
import json
import re
from pathlib import Path

PROJECT = 'GoToGtymPrime'
TOOLING = '03900cf91f81ccb001fffaefa079ebd13e50ad18'
COMMANDS = {'semgrep': ['semgrep', 'scan', '--config', 'auto', '--exclude', 'QAF-Cyber', '--exclude', '1_FaseAnalisis', '--json', '--output', '{report}', '.'], 'osv-scanner': ['osv-scanner', 'scan', 'source', '-r', '.', '--format', 'json', '--output', '{report}'], 'gitleaks': ['gitleaks', 'dir', '.', '--redact', '--report-format', 'json', '--report-path', '{report}', '--exit-code', '0'], 'trivy': ['trivy', 'fs', '--scanners', 'vuln,misconfig', '--skip-dirs', 'QAF-Cyber,1_FaseAnalisis', '--format', 'json', '--output', '{report}', '.'], 'syft': ['syft', 'dir:.', '-o', 'cyclonedx-json={report}']}
ROOT = Path(__file__).resolve().parents[2]

def validate(profile, operational=False):
    if profile.get('project_id') != PROJECT or profile.get('repository') != 'gotogymsaas/' + PROJECT:
        raise ValueError('Cross-project profile rejected')
    if profile.get('mode') != 'SHADOW' or profile.get('authority') != 'READ_ONLY':
        raise ValueError('Read-only shadow authority required')
    if profile.get('tooling_ref') != TOOLING or not re.fullmatch(r'[0-9a-f]{40}', TOOLING):
        raise ValueError('Reviewed tooling SHA required')
    if set(profile.get('tools', {})) != set(COMMANDS):
        raise ValueError('Exactly five scanners required')
    for tool, expected in COMMANDS.items():
        config = profile['tools'][tool]
        if config.get('allowed_command') != expected:
            raise ValueError('Arbitrary commands rejected')
        if config.get('configuration') != {'source': 'central qaf_cyber.scanners.COMMANDS', 'tooling_ref': TOOLING}:
            raise ValueError('Configuration differs from reviewed tooling')
        if config.get('output_format') != ('cyclonedx-json' if tool == 'syft' else 'json'):
            raise ValueError('Unsupported output')
        version, digest, feed = (config.get(k) for k in ('version', 'version_stdout_sha256', 'feed_reference'))
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise ValueError('Invalid scanner version SHA-256')
        if operational and (not all(isinstance(v, str) and v.strip() for v in (version, digest, feed))
                            or any(re.search(r'(?i)(pending|placeholder|latest|<|>)', v) for v in (version, digest, feed))):
            raise ValueError('Runner version/hash/feed attestation required')
    if operational and profile.get('status') != 'OPERATOR_REVIEWED':
        raise ValueError('Operational review required')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--operational', action='store_true')
    args = parser.parse_args()
    validate(json.loads((ROOT / '.github/qaf/scanner-profile.json').read_text()), args.operational)
    print('Profile validation passed')
