#!/usr/bin/env python3
"""Regression tests for the SPHINCS-Parameters tool chain.

Diffs three independent implementations against frozen golden fixtures:
  1. tests/model.py       — stdlib-only reference model (audit port)
  2. utils/*.csv          — the published sweep data (sage output)
  3. site/*.html          — the interactive pages' JS (executed under node)
  4. costs.sage           — exercised directly when `sage` is on PATH

Run:  python3 tests/test_regression.py        (also works under pytest)

Requires node for the site tests and sage for the sage test; both are
skipped with a notice when unavailable.

These tests would have caught both critical audit findings:
  C1 (w=32 chain-count floor bug)  -> test_wots_chain_counts, test_csv_*
  C2 (randomness-size divergence)  -> test_stateful_model, test_site_stateful
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import model as M  # noqa: E402

FIX = json.load(open(os.path.join(HERE, 'fixtures.json')))


def _tuple_of(key):
    return tuple(int(x) for x in key.split(','))


# ---------------------------------------------------------------------------
# 1. Reference model vs frozen fixtures
# ---------------------------------------------------------------------------

def test_wots_chain_counts():
    """FIPS 205 chain counts — catches the C1 class of bug (w=32 -> 28, not 27)."""
    for w, l in FIX['wots_len'].items():
        assert M.wots_len(int(w)) == l, (w, M.wots_len(int(w)), l)
    for w, l in FIX['wots_len_wc'].items():
        assert M.wots_len(int(w), wc=True) == l
    for w, s in FIX['swn'].items():
        assert M.SWN[int(w)] == s


def test_baseline_metrics():
    b = FIX['baseline']
    m = M.spx_metrics(63, 7, 14, 12, 16)
    for k in ('size', 'kg', 'sg', 'sv', 'sv_worst'):
        assert m[k] == b[k], (k, m[k], b[k])
    assert abs(m['cpb'] - 0.3038441955193482) < 1e-12
    assert abs(m['cpb_worst'] - 0.5248217922606925) < 1e-12


def test_stateless_fixtures():
    for key, f in FIX['stateless'].items():
        m = M.spx_metrics(*_tuple_of(key))
        for k in ('size', 'kg', 'sg', 'sv', 'sv_worst'):
            assert m[k] == f[k], (key, k, m[k], f[k])


def test_stateful_model():
    """UXMSS + XMSS-MT fixtures — catches the C2 class of bug (R_SIZE drift)."""
    for key, f in FIX['stateful']['uxmss'].items():
        ots, w = key.split(',')
        m = M.uxmss_metrics(ots, int(w))
        assert m == f, (key, m, f)
    for key, f in FIX['stateful']['xmssmt'].items():
        parts = key.split(',')
        m = M.xmssmt_metrics(parts[0], int(parts[1]), int(parts[2]), int(parts[3]))
        assert m == f, (key, m, f)


# ---------------------------------------------------------------------------
# 2. Published CSVs vs reference model
# ---------------------------------------------------------------------------

def _csv_rows(name):
    with open(os.path.join(ROOT, 'utils', name)) as fh:
        return list(csv.DictReader(fh))


def test_csv_row_counts():
    for name, expected in FIX['csv_rows'].items():
        assert len(_csv_rows(name)) == expected, name


def test_csv_full_consistency():
    """Every row of both sweep CSVs must match the reference model exactly."""
    for name in FIX['csv_rows']:
        for r in _csv_rows(name):
            t = tuple(int(r[x]) for x in 'hdkaw')
            m = M.spx_metrics(*t)
            got = (int(r['size']), int(float(r['keygen_C'])),
                   int(float(r['sign_C'])), int(float(r['verify_C'])),
                   int(float(r['verify_worst_C'])), int(r['l']))
            want = (m['size'], m['kg'], m['sg'], m['sv'], m['sv_worst'],
                    M.wots_len(t[4]))
            assert got == want, (name, t, got, want)
            assert abs(float(r['c_per_byte']) - m['cpb']) < 1e-9
            assert abs(float(r['c_per_byte_worst']) - m['cpb_worst']) < 1e-9


def test_csv_standard_row():
    std = [r for r in _csv_rows('all_size_capped_candidates.csv')
           if r['label'] == 'STANDARD']
    assert len(std) == 1
    assert int(std[0]['size']) == FIX['baseline']['size']


# ---------------------------------------------------------------------------
# 3. Site pages (node)
# ---------------------------------------------------------------------------

def _extract_js(page, end_marker):
    html = open(os.path.join(ROOT, 'site', page)).read()
    m = re.search(r"'use strict';(.*?)" + re.escape(end_marker), html, re.S)
    assert m, f'extraction markers not found in {page} — update the test'
    return m.group(1)


def _run_node(js):
    if not shutil.which('node'):
        print('  [skip] node not available')
        return None
    p = subprocess.run(['node', '-e', js], capture_output=True, text=True,
                       cwd=ROOT, timeout=300)
    assert p.returncode == 0, p.stderr[:2000]
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_site_index():
    js = _extract_js('index.html', '// ---------- State ----------')
    tuples = [list(_tuple_of(k)) for k in FIX['stateless']]
    js += f"""
const _tuples = {json.dumps(tuples)};
const out = {{ pool: sweep().filter(passesInitial).length, metrics: {{}} }};
for (const t of _tuples) {{
  const m = metrics({{h:t[0], d:t[1], k:t[2], a:t[3], w:t[4]}});
  out.metrics[t.join(',')] = [m.size, m.kg, m.sg, m.sv, m.sv_worst];
}}
console.log(JSON.stringify(out));
"""
    out = _run_node(js)
    if out is None:
        return
    assert out['pool'] == FIX['site_pool_count'], out['pool']
    for key, f in FIX['stateless'].items():
        got = out['metrics'][key]
        want = [f['size'], f['kg'], f['sg'], f['sv'], f['sv_worst']]
        assert got == want, (key, got, want)


def test_site_stateful():
    js = _extract_js('stateful.html', '// Shared slider/number-input renderer')
    js += """
const out = { slh: null, uxmss: {}, xmssmt: {} };
const s = buildSLH().metrics;
out.slh = [s.size, s.keygen, s.siggen, s.sigver, s.sigverWorst];
for (const ots of ['TW','WC']) for (const w of [16,32,256]) {
  const c = buildUxmss(ots, w), m = c.metrics;
  out.uxmss[`${ots},${w}`] = [c.hsf, m.sizeQ1, m.size, m.keygen, m.siggen, m.sigver, m.sigverWorst];
}
""" + "".join(
        f"""{{ const m = buildXmssMt('{k.split(',')[0]}', {k.split(',')[1]}, {k.split(',')[2]}, {k.split(',')[3]}).metrics;
out.xmssmt['{k}'] = [m.size, m.keygen, m.siggen, m.sigver, m.sigverWorst]; }}
""" for k in FIX['stateful']['xmssmt']) + """
console.log(JSON.stringify(out));
"""
    out = _run_node(js)
    if out is None:
        return
    b = FIX['baseline']
    assert out['slh'] == [b['size'], b['kg'], b['sg'], b['sv'], b['sv_worst']], out['slh']
    for key, f in FIX['stateful']['uxmss'].items():
        want = [f['hsf'], f['sz_q1'], f['sz_max'], f['kg'], f['sg'],
                f['sv_max'], f['sv_max_worst']]
        assert out['uxmss'][key] == want, (key, out['uxmss'][key], want)
    for key, f in FIX['stateful']['xmssmt'].items():
        want = [f['size'], f['kg'], f['sg'], f['sv'], f['sv_worst']]
        assert out['xmssmt'][key] == want, (key, out['xmssmt'][key], want)


# ---------------------------------------------------------------------------
# 4. Sage (optional)
# ---------------------------------------------------------------------------

def test_sage_costs():
    if not shutil.which('sage'):
        print('  [skip] sage not available')
        return
    p = subprocess.run(
        ['sage', 'costs.sage', '--params', 'SPX', '64', '14', '12', '63', '7', '16', '0'],
        capture_output=True, text=True, cwd=ROOT, timeout=600)
    assert p.returncode == 0, p.stderr[:2000]
    out = p.stdout
    b = FIX['baseline']
    assert f"Size:       {b['size']} bytes" in out, out
    assert 'Security:   128.0 bits' in out, out
    assert 'C/byte:     0.30  (worst: 0.52)' in out, out


# ---------------------------------------------------------------------------
# Plain runner (no pytest required)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith('test_') and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f'PASS  {name}')
        except AssertionError as e:
            failed += 1
            print(f'FAIL  {name}: {e}')
    print(f'\n{len(tests) - failed}/{len(tests)} passed')
    sys.exit(1 if failed else 0)
