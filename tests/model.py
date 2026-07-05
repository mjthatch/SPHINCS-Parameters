"""Independent reference model for the regression tests.

Ports the cost formulas of costs.sage (SPX branch) and stateful.sage using
only the Python standard library. Written during the 2026-07-05 audit and
verified against the sage scripts, both site pages, and the published CSVs.

Deliberately does NOT import or reuse any project code: its value is being
a second, independent implementation that the real code is diffed against.
"""
from math import ceil, floor, log2, comb

N = 16                       # hashbytes (128-bit security level)
C_SIZE = 4                   # WOTS+C grinding counter (bytes)
R_SIZE = 16                  # message randomness = n bytes

C_TH1 = 1; C_TH1C = 1; C_TH2 = 2; C_HMSG = 2; C_PRFMSG = 2; C_PRF = 1

SWN = {16: 240, 32: 403, 256: 2040}   # WOTS+C target chain sums S_{w,n}


def compute_th(x):
    """Compressions for a tweakable hash over x hash-sized values (SHA-256)."""
    return ceil((128 + 96 + 128 * x + 65) / 512)


def wots_len1(w):
    return ceil(8 * N / log2(w))


def wots_len(w, wc=False):
    """Chain count: l1 + l2 for WOTS-TW/classic, l1 for WOTS+C (FIPS 205 form)."""
    l1 = wots_len1(w)
    if wc:
        return l1
    l2 = floor(log2(l1 * (w - 1)) / log2(w)) + 1
    return l1 + l2


def wots_worst_steps(w):
    """Worst-case WOTS-TW verification chain steps (all message digits 0)."""
    l1 = wots_len1(w)
    l2 = floor(log2(l1 * (w - 1)) / log2(w)) + 1
    c = l1 * (w - 1)
    ds, rem = 0, c
    while rem:
        ds += rem % w
        rem //= w
    return l1 * (w - 1) + l2 * (w - 1) - ds


# ---------------------------------------------------------------------------
# Stateless: SLH-DSA / SPX (plain WOTS-TW + FORS), matches costs.sage
# ---------------------------------------------------------------------------

def spx_metrics(h, d, k, a, w):
    assert h % d == 0
    hp = h // d
    l = wots_len(w)
    thl = compute_th(l)
    thk = compute_th(k)

    size = N * (1 + k * (a + 1) + h + d * l)

    c_merkle = 2**hp * (l * C_PRF + l * (w - 1) * C_TH1 + thl) + (2**hp - 1) * C_TH2
    kg = c_merkle

    c_fors = (k * 2**a * C_PRF + k * 2**a * C_TH1
              + k * (2**a - 1) * C_TH2 + thk)
    sg = c_fors + (C_HMSG + C_PRFMSG) + d * c_merkle

    c_fts = k * C_TH1 + k * a * C_TH2 + thk
    c_wots_avg = (w - 1) * l // 2 * C_TH1 + thl
    c_wots_worst = wots_worst_steps(w) * C_TH1 + thl
    sv = C_HMSG + c_fts + d * c_wots_avg + h * C_TH2
    sv_worst = C_HMSG + c_fts + d * c_wots_worst + h * C_TH2

    return {
        'size': size, 'kg': kg, 'sg': sg, 'sv': sv, 'sv_worst': sv_worst,
        'cpb': sv / size, 'cpb_worst': sv_worst / size,
    }


# ---------------------------------------------------------------------------
# Stateful: XMSS / XMSS-MT / UXMSS, matches stateful.sage (R = n = 16 B)
# ---------------------------------------------------------------------------

def _wc(ots):
    return ots == 'WC'


def wots_pk_c(w, ots):
    l = wots_len(w, _wc(ots))
    return l * C_PRF + l * (w - 1) * C_TH1 + compute_th(l)


def _nu(l, swn, w):
    """Number of valid WOTS+C encodings with digit sum exactly swn."""
    nu = 0
    for j in range(l + 1):
        n_val = (swn + l) - j * w - 1
        b2 = comb(n_val, l - 1) if n_val >= l - 1 else 0
        nu += (-1)**j * comb(l, j) * b2
    return nu if nu > 0 else 1


def wots_sign_c(w, ots):
    l = wots_len(w, _wc(ots))
    if _wc(ots):
        swn = SWN[w]
        nu = _nu(l, swn, w)
        search = -(-(w**l) // nu)          # ceil division, exact integers
        return search * C_TH1C + l * C_PRF + swn * C_TH1 + compute_th(l)
    return l * C_PRF + l * (w - 1) // 2 * C_TH1


def wots_verify_c(w, ots, worst=False):
    l = wots_len(w, _wc(ots))
    thl = compute_th(l)
    if _wc(ots):
        return ((w - 1) * l - SWN[w]) * C_TH1 + C_TH1C + thl
    if worst:
        return wots_worst_steps(w) * C_TH1 + thl
    return l * (w - 1) // 2 * C_TH1 + thl


def idx_bytes(h):
    return max(1, ceil(h / 8))


def xmssmt_metrics(ots, h, d, w):
    assert h % d == 0
    hp = h // d
    l = wots_len(w, _wc(ots))
    ctr = C_SIZE if _wc(ots) else 0
    size = R_SIZE + d * (hp * N + l * N + ctr) + idx_bytes(h)
    pk = wots_pk_c(w, ots)
    kg = 2**hp * pk + (2**hp - 1) * C_TH2
    sg = C_HMSG + C_PRFMSG + wots_sign_c(w, ots) + d * (hp * pk + hp * C_TH2)
    sv = C_HMSG + d * (wots_verify_c(w, ots, False) + hp * C_TH2)
    sv_worst = C_HMSG + d * (wots_verify_c(w, ots, True) + hp * C_TH2)
    return {'size': size, 'kg': kg, 'sg': sg, 'sv': sv, 'sv_worst': sv_worst}


def uxmss_idx_bytes(hsf):
    if hsf <= 0:
        return 1
    return max(1, ceil(log2(hsf + 1) / 8))


def uxmss_find_hsf(w, ots, target_size):
    l = wots_len(w, _wc(ots))
    ctr = C_SIZE if _wc(ots) else 0
    hsf = 0
    for _ in range(64):
        avail = target_size - 1 - R_SIZE - ctr - l * N - uxmss_idx_bytes(hsf)
        new = max(0, avail // N)
        if new == hsf:
            return hsf
        hsf = new
    return hsf


def uxmss_metrics(ots, w, target_size=5712):
    hsf = uxmss_find_hsf(w, ots, target_size)
    l = wots_len(w, _wc(ots))
    ctr = C_SIZE if _wc(ots) else 0

    def size(q):
        return R_SIZE + ctr + l * N + min(q, hsf) * N + uxmss_idx_bytes(hsf)

    return {
        'hsf': hsf,
        'sz_q1': size(1),
        'sz_max': size(hsf),
        'kg': (hsf + 1) * wots_pk_c(w, ots) + hsf * C_TH2,
        'sg': C_HMSG + C_PRFMSG + wots_sign_c(w, ots),
        'sv_max': C_HMSG + wots_verify_c(w, ots, False) + hsf * C_TH2,
        'sv_max_worst': C_HMSG + wots_verify_c(w, ots, True) + hsf * C_TH2,
    }
