#!/usr/bin/env sage
"""
Export the canonical dataset consumed by both interactive pages: site/data.json.

Single source of truth:
  - stateless pool  : read from utils/all_size_capped_candidates.csv
                      (regenerate first if needed:
                       sage slhdsa-2to40.sage --max-size 7856 &&
                       mv candidates.csv utils/all_size_capped_candidates.csv)
  - stateful grid, UXMSS variants, SLH baseline
                    : computed by loading stateful.sage / costs.sage —
                      the exact same code paths as the CLI tools.

The pages load data.json at startup and fall back to in-browser computation
only if the file is unavailable; they also self-check the loaded numbers
against their local formulas and log any divergence to the console.

Usage:  sage export_site_data.sage
Verify: python3 tests/test_regression.py
"""
import os
import sys
import csv as _csvmod
import json
import subprocess
import datetime

_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['STATEFUL_SAGE_NO_MAIN'] = '1'
os.environ['COSTS_SAGE_NO_MAIN'] = '1'
_saved_argv = sys.argv
sys.argv = ['export_site_data.sage']
load(os.path.join(_dir, "stateful.sage"))   # also loads costs.sage
sys.argv = _saved_argv

# Canonical stateless grid (report Sec. 2; must match slhdsa-2to40.sage
# defaults and the explorer's fallback sweep).
GRID = {'h': [40, 50], 'd': [2, 25], 'k': [6, 24], 'a': [8, 20],
        'w': [16, 32, 256], 'q_s_log2': 40, 'max_size': 7856}


def _sweep_count():
    pairs = 0
    for h in range(GRID['h'][0], GRID['h'][1] + 1):
        for d in range(GRID['d'][0], GRID['d'][1] + 1):
            if h % d == 0:
                pairs += 1
    return pairs * len(GRID['w']) \
        * (GRID['k'][1] - GRID['k'][0] + 1) * (GRID['a'][1] - GRID['a'][0] + 1)


# ---------------------------------------------------------------------------
# Stateless pool: straight from the canonical sweep CSV
# ---------------------------------------------------------------------------
csv_path = os.path.join(_dir, 'utils', 'all_size_capped_candidates.csv')
pool_rows, baseline = [], None
with open(csv_path) as f:
    for r in _csvmod.DictReader(f):
        rec = [int(r['h']), int(r['d']), int(r['k']), int(r['a']), int(r['w']),
               int(r['size']), int(float(r['keygen_C'])), int(float(r['sign_C'])),
               int(float(r['verify_C'])), int(float(r['verify_worst_C']))]
        if r['label'] == 'STANDARD':
            baseline = {'params': {'h': 63, 'd': 7, 'k': 14, 'a': 12, 'w': 16},
                        'size': rec[5], 'kg': rec[6], 'sg': rec[7],
                        'sv': rec[8], 'sv_worst': rec[9]}
        else:
            pool_rows.append(rec)
assert baseline is not None, "STANDARD row missing from %s" % csv_path

# ---------------------------------------------------------------------------
# Stateful: XMSS/XMSS-MT grid + UXMSS variants (same functions as the CLI)
# ---------------------------------------------------------------------------
_SWN = {16: 240, 32: 403, 256: 2040}
UXMSS_REF = 5712   # Report Candidate 2 — reference bound for max stateful size

xmssmt_rows = []
for ots_label, ots_type in (('TW', OTS_TW), ('WC', OTS_WC)):
    for w in (16, 32, 256):
        swn = _SWN[w] if ots_type == OTS_WC else 0
        for h in range(10, 41):
            for d in range(1, 11):
                if h % d != 0:
                    continue
                xmssmt_rows.append([
                    ots_label, h, d, w,
                    int(xmssmt_size_h(h, d, w, ots_type)),
                    int(xmssmt_keygen_C_h(h, d, w, ots_type)),
                    int(xmssmt_sign_bds_C_h(h, d, w, swn, ots_type)),
                    int(xmssmt_verify_C_h(h, d, w, swn, ots_type, worst_case=False)),
                    int(xmssmt_verify_C_h(h, d, w, swn, ots_type, worst_case=True)),
                ])

uxmss_rows = []
for ots_label, ots_type in (('TW', OTS_TW), ('WC', OTS_WC)):
    for w in (16, 32, 256):
        swn = _SWN[w] if ots_type == OTS_WC else 0
        hsf = find_max_hsf(w, ots_type, UXMSS_REF)
        uxmss_rows.append([
            ots_label, w, int(hsf),
            int(uxmss_size(1, hsf, w, ots_type)),
            int(uxmss_size(hsf, hsf, w, ots_type)),
            int(uxmss_keygen_C(hsf, w, ots_type)),
            int(uxmss_sign_C(1, hsf, w, swn, ots_type)),
            int(uxmss_verify_C(hsf, hsf, w, swn, ots_type, worst_case=False)),
            int(uxmss_verify_C(hsf, hsf, w, swn, ots_type, worst_case=True)),
        ])


def _commit():
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=_dir, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return 'unknown'


data = {
    'meta': {
        'generator': 'export_site_data.sage',
        'generated': datetime.date.today().isoformat(),
        'commit': _commit(),
        'grid': GRID,
        'sweep_count': _sweep_count(),
        'pool_count': len(pool_rows),
        'uxmss_ref_size': UXMSS_REF,
    },
    'baseline': baseline,
    'stateless_pool': {
        'fields': ['h', 'd', 'k', 'a', 'w', 'size', 'kg', 'sg', 'sv', 'sv_worst'],
        'rows': pool_rows,
    },
    'stateful': {
        'slh': {'size': baseline['size'], 'kg': baseline['kg'],
                'sg': baseline['sg'], 'sv': baseline['sv'],
                'sv_worst': baseline['sv_worst'], 'qs_log2': 64},
        'xmssmt': {
            'fields': ['ots', 'h', 'd', 'w', 'size', 'kg', 'sg', 'sv', 'sv_worst'],
            'rows': xmssmt_rows,
        },
        'uxmss': {
            'fields': ['ots', 'w', 'hsf', 'sz_q1', 'sz_max', 'kg', 'sg',
                       'sv_max', 'sv_max_worst'],
            'rows': uxmss_rows,
        },
    },
}

out_path = os.path.join(_dir, 'site', 'data.json')
with open(out_path, 'w') as f:
    # default=int: the sage preparser turns integer literals into sage
    # Integers, which the json module cannot serialize directly.
    json.dump(data, f, separators=(',', ':'), default=int)
print("Wrote {} — {} pool rows, {} stateful grid rows, commit {}".format(
    out_path, len(pool_rows), len(xmssmt_rows), data['meta']['commit']))
