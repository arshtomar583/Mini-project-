"""Analyze a local reference snapshot; never execute its source or fetch updates."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from app.analyzer import analyze_project, text_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT / 'temp/AltF4')
    args = parser.parse_args()
    repo = args.repo.resolve()
    baseline = json.loads((ROOT / 'tests/reference/altf4.json').read_text(encoding='utf-8'))
    if not repo.is_dir():
        parser.error('Reference copy not found. See docs/REVIEW-AND-REFERENCE.md for the clone command.')
    try:
        commit = subprocess.run(
            ['git', '-C', str(repo), 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True, timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        parser.error('Could not read the reference repository revision.')

    started = time.perf_counter()
    report = analyze_project(repo)
    elapsed = time.perf_counter() - started
    canonical = json.dumps(report, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    passed = (
        commit == baseline['commit']
        and digest == baseline['report_sha256']
        and report['summary'] == baseline['summary']
    )
    output = ROOT / 'output/reference'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'AltF4-analysis.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    selected = 'src/engine.py' if 'src/engine.py' in report['impact'] else None
    readable = f"Reference: {baseline['repository']}\nSnapshot: {commit}\n\n" + text_report(report, selected)
    (output / 'AltF4-analysis.txt').write_text(readable, encoding='utf-8')
    check = {
        'repository': baseline['repository'], 'snapshot': commit,
        'baseline_snapshot': baseline['commit'], 'schema_version': report['schema_version'],
        'report_sha256': digest, 'baseline_matches': passed,
        'analysis_seconds': round(elapsed, 4), 'summary': report['summary'],
    }
    (output / 'AltF4-check.json').write_text(json.dumps(check, indent=2), encoding='utf-8')
    print(f"AltF4 reference snapshot: {commit}")
    print(f"Files: {report['summary']['files_analyzed']} | Functions: {report['summary']['functions']} | Classes: {report['summary']['classes']}")
    print(f"Local connections: {report['summary']['local_dependencies']} | Source errors: {report['summary']['errors']}")
    print(f"Unresolved imported names: {report['summary']['unresolved_imports']} (includes library imports)")
    print(f"Circular groups: {report['summary']['circular_dependency_groups']}")
    if selected:
        impact = report['impact'][selected]
        print(f"Potential impact of {selected}: {len(impact['direct_dependents'])} direct, {len(impact['indirect_dependents'])} indirect")
    print(f'\nAnalysis time on this run: {elapsed:.3f} seconds')
    print('Reference comparison: ' + ('PASS' if passed else 'CHANGED - review the snapshot or analyzer before updating the baseline'))
    print('Reports saved to output/reference/')
    # A baseline comparison detects changed output; it is not a proof that every
    # relationship in this real project has been independently verified.
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
