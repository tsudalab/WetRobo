"""Extract only the authorized trial's usage evidence; never execute logged code."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = Path('/home/admin/.codex/sessions/2026/09/08/rollout-2026-09-08T21-10-07-01a080ec-f2af-7ee2-a641-57e02e0aeaeb.jsonl')
FILES = ['src/labb_right_cap_control.py', 'src/detect_culture_bottle_cap.py',
         'src/sample_record3d_depth.py', 'src/estimate_frame_motion.py',
         'src/log_right_pressure.py', 'rollout/verify_right_home_level.py',
         'src/orient_record3d_frame.sh', 'tests/test_piper_native_gripper.py']


def main():
    events = {p: {'path': p, 'physical_lines': len((ROOT/p).read_text().splitlines())} for p in FILES}
    tokens, skipped = [], []
    for part in re.split(r'(?m)(?=^\{"timestamp":)', LOG.read_text()):
        if not part.strip():
            continue
        # The file contains two malformed records. Preserve their identity,
        # then resume at the next top-level timestamp, not arbitrary text.
        if part[:40] > '{"timestamp":"2026-09-08T13:00:00':
            break
        try:
            row = json.loads(part, strict=False)
        except ValueError:
            skipped.append(part[:100])
            continue
        ts = row['timestamp']
        if ts > '2026-09-08T13:00:00':
            break
        p = row.get('payload', {})
        if p.get('type') == 'token_count' and p.get('info'):
            tokens.append({'utc': ts, **p['info']['total_token_usage']})
        if row['type'] != 'response_item' or p.get('type') not in ('function_call', 'custom_tool_call'):
            continue
        call = p.get('arguments', p.get('input', ''))
        if '*** Begin Patch' in call:
            continue
        for match in re.finditer(r'"cmd"\s*:\s*("(?:[^"\\]|\\.)*")', call):
            cmd = json.loads(match[1])
            for command in re.split(r'\n|&&', cmd):
                for path, event in events.items():
                    if path not in command:
                        continue
                    if re.match(r'\s*(?:nohup\s+)?(?:python|bash|pytest)\b', command):
                        event.setdefault('first_execution', {'utc': ts, 'command': command.strip()})
                    elif re.match(r'\s*(?:sed|cat|head)\b', command):
                        event.setdefault('first_review', {'utc': ts, 'command': command.strip()})
    assert tokens and all(b['total_tokens'] >= a['total_tokens'] for a,b in zip(tokens,tokens[1:]))
    out = {'source': str(LOG), 'files': list(events.values()), 'tokens': tokens,
           'skipped_malformed_records': skipped,
           'token_definition': 'Session cumulative input plus output, including cached input; reasoning is included in output, not added again.'}
    (ROOT/'artifacts/labB/session_usage_metrics.json').write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps({'files': out['files'], 'last_tokens': tokens[-1], 'skipped': len(skipped)}, indent=2))


if __name__ == '__main__':
    main()
