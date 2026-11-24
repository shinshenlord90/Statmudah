"""StatMudah - fungsi statistik tulen (tiada kebergantungan luar)."""
import math, statistics as st

def _betacf(a, b, x):
    qab, qap, qam, c, d = a + b, a + 1, a - 1, 1.0, 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) > 1e-30 else 1e-30); h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30)
            c = 1 + aa / c; c = c if abs(c) > 1e-30 else 1e-30
            h *= d * c
        if abs(d * c - 1) < 3e-14: break
    return h

def betainc(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    return bt * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - bt * _betacf(b, a, 1 - x) / b

def p_t(t, df): return betainc(df / 2, 0.5, df / (df + t * t))          # dua hujung
def p_f(f, d1, d2): return betainc(d2 / 2, d1 / 2, d2 / (d2 + d1 * f)) if f > 0 else 1.0
def p_chi2(x, k):  # hujung atas, siri gamma tak lengkap
    if x <= 0: return 1.0
    a, s, term = k / 2, 0.0, 1.0 / (k / 2)
    if x / 2 < a + 1:
        s = term
        for n in range(1, 500): term *= (x / 2) / (a + n); s += term
        return 1 - s * math.exp(-x / 2 + a * math.log(x / 2) - math.lgamma(a))
    # pecahan berterusan untuk x besar
    b, c, d = x / 2 + 1 - a, 1e300, 1 / (x / 2 + 1 - a); h = d
    for i in range(1, 500):
        an = -i * (i - a); b += 2
        d = an * d + b; d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = b + an / c; c = c if abs(c) > 1e-300 else 1e-300
        h *= d * c
    return math.exp(-x / 2 + a * math.log(x / 2) - math.lgamma(a)) * h

def inverse(m):
    """Songsang matriks (Gauss-Jordan); None jika singular."""
    n = len(m); a = [row[:] + [float(i == j) for j in range(n)] for i, row in enumerate(m)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(a[r][c]))
        if abs(a[piv][c]) < 1e-12: return None
        a[c], a[piv] = a[piv], a[c]; d = a[c][c]; a[c] = [v / d for v in a[c]]
        for r in range(n):
            if r != c and a[r][c]: f = a[r][c]; a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return [row[n:] for row in a]

def ols(y, xs):
    """Regresi linear OLS. xs: senarai baris peramal. Pulangkan dict atau None jika kolinear/data kurang."""
    n, k = len(y), len(xs[0]) if xs else 0
    if n - k - 1 < 1: return None
    X = [[1.0] + list(r) for r in xs]
    inv = inverse([[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k + 1)] for a in range(k + 1)])
    if inv is None: return None
    xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(k + 1)]
    b = [sum(inv[a][c] * xty[c] for c in range(k + 1)) for a in range(k + 1)]
    my = sum(y) / n; sst = sum((v - my) ** 2 for v in y)
    yhat = [sum(b[a] * X[i][a] for a in range(k + 1)) for i in range(n)]; e = [y[i] - yhat[i] for i in range(n)]
    sse = sum(v * v for v in e)
    if sst == 0: return None
    ssr, dfe = sst - sse, n - k - 1; mse = sse / dfe
    se = [math.sqrt(max(0.0, mse * inv[a][a])) for a in range(k + 1)]
    sy = math.sqrt(sst / (n - 1)); sx = [st.stdev([r[a] for r in xs]) for a in range(k)]
    return dict(n=n, k=k, b=b, se=se, beta=[None] + [b[a + 1] * sx[a] / sy for a in range(k)],
                t=[b[a] / se[a] if se[a] else math.inf for a in range(k + 1)], r2=ssr / sst,
                adj=1 - (sse / dfe) / (sst / (n - 1)), see=math.sqrt(mse), ssr=ssr, sse=sse, sst=sst, dfe=dfe,
                f=(ssr / k) / mse if mse else math.inf, yhat=yhat, e=e, cov=[[mse * v for v in r] for r in inv])

def vif(xs):
    """VIF setiap peramal: 1/(1-R²) bila diregres atas peramal lain."""
    k = len(xs[0])
    if k == 1: return [1.0]
    out = []
    for j in range(k):
        m = ols([r[j] for r in xs], [[v for c, v in enumerate(r) if c != j] for r in xs])
        out.append(None if m is None else (math.inf if m["r2"] >= 1 else 1 / (1 - m["r2"])))
    return out

def shapiro(x):
    """Shapiro-Wilk W dan p (algoritma Royston 1992, 3 <= n <= 5000); None jika tak boleh dikira."""
    x = sorted(x); n = len(x); N = st.NormalDist()
    mean = sum(x) / n if n else 0; ss = sum((v - mean) ** 2 for v in x)
    if n < 3 or n > 5000 or ss == 0: return None
    if n == 3: a = [-math.sqrt(.5), 0, math.sqrt(.5)]
    else:
        m = [N.inv_cdf((i - .375) / (n + .25)) for i in range(1, n + 1)]; mm = sum(v * v for v in m); u = 1 / math.sqrt(n)
        an = -2.706056*u**5 + 4.434685*u**4 - 2.07119*u**3 - .147981*u**2 + .221157*u + m[-1] / math.sqrt(mm)
        if n > 5:
            an1 = -3.582633*u**5 + 5.682633*u**4 - 1.752461*u**3 - .293762*u**2 + .042981*u + m[-2] / math.sqrt(mm)
            phi = (mm - 2 * m[-1]**2 - 2 * m[-2]**2) / (1 - 2 * an**2 - 2 * an1**2)
            a = [v / math.sqrt(phi) for v in m]; a[0], a[1], a[-2], a[-1] = -an, -an1, an1, an
        else:
            phi = (mm - 2 * m[-1]**2) / (1 - 2 * an**2)
            a = [v / math.sqrt(phi) for v in m]; a[0], a[-1] = -an, an
    w = min(sum(ai * xi for ai, xi in zip(a, x)) ** 2 / ss, 1 - 1e-12)
    if n == 3: return w, max(0.0, 6 / math.pi * (math.asin(math.sqrt(w)) - math.asin(math.sqrt(.75))))
    if n <= 11:
        g = -2.273 + .459 * n
        mu = .544 - .39978 * n + .025054 * n**2 - .0006714 * n**3
        sig = math.exp(1.3822 - .77857 * n + .062767 * n**2 - .0020322 * n**3)
        if g - math.log(1 - w) <= 0: return w, 0.0
        z = (-math.log(g - math.log(1 - w)) - mu) / sig
    else:
        ln = math.log(n)
        mu = .0038915 * ln**3 - .083751 * ln**2 - .31082 * ln - 1.5861
        sig = math.exp(.0030302 * ln**2 - .082676 * ln - .4803)
        z = (math.log(1 - w) - mu) / sig
    return w, 1 - N.cdf(z)

def breusch_pagan(e, xs):
    """Ujian Breusch-Pagan (versi Koenker): LM = n·R² regresi e² atas X, dk = k."""
    m = ols([v * v for v in e], xs)
    return None if m is None else (len(e) * m["r2"], len(xs[0]))

def durbin_watson(e): return sum((e[i] - e[i - 1]) ** 2 for i in range(1, len(e))) / sum(v * v for v in e)

def logit(y, xs, iters=50):
    """Regresi logistik binari (Newton-Raphson). y: 0/1. None jika tak menumpu (cth. pemisahan sempurna) atau kolinear."""
    n, k = len(y), len(xs[0]); X = [[1.0] + list(r) for r in xs]; b = [0.0] * (k + 1)
    prob = lambda b: [1 / (1 + math.exp(-max(-700, min(700, sum(c * v for c, v in zip(b, row)))))) for row in X]
    for _ in range(iters):
        p = prob(b)
        g = [sum((y[i] - p[i]) * X[i][a] for i in range(n)) for a in range(k + 1)]
        inv = inverse([[sum(p[i] * (1 - p[i]) * X[i][a] * X[i][c] for i in range(n)) for c in range(k + 1)] for a in range(k + 1)])
        if inv is None: return None
        step = [sum(inv[a][c] * g[c] for c in range(k + 1)) for a in range(k + 1)]
        b = [c + s for c, s in zip(b, step)]
        if max(map(abs, step)) < 1e-8: break
    else: return None
    p = prob(b)
    inv = inverse([[sum(p[i] * (1 - p[i]) * X[i][a] * X[i][c] for i in range(n)) for c in range(k + 1)] for a in range(k + 1)])
    if inv is None: return None
    cl = lambda v: min(max(v, 1e-15), 1 - 1e-15)
    ll = sum(math.log(cl(p[i])) if y[i] else math.log(1 - cl(p[i])) for i in range(n))
    p0 = sum(y) / n; ll0 = n * (p0 * math.log(p0) + (1 - p0) * math.log(1 - p0))
    se = [math.sqrt(max(0.0, inv[a][a])) for a in range(k + 1)]
    cs = 1 - math.exp(2 * (ll0 - ll) / n)
    return dict(n=n, k=k, b=b, se=se, p=p, ll=ll, chi2=2 * (ll - ll0), cs=cs, nk=cs / (1 - math.exp(2 * ll0 / n)),
                wald=[(b[a] / se[a]) ** 2 if se[a] else math.inf for a in range(k + 1)])

def anova1(groups):
    """ANOVA sehala atas senarai kumpulan. Pulangkan (F, dk1, dk2, JKA, JKD) atau None."""
    allv = [v for g in groups for v in g]; k, n = len(groups), len(allv)
    if k < 2 or n - k < 1: return None
    gm, means = sum(allv) / n, [sum(g) / len(g) for g in groups]
    ssb = sum(len(g) * (m - gm) ** 2 for g, m in zip(groups, means))
    ssw = sum((v - m) ** 2 for g, m in zip(groups, means) for v in g)
    if ssw == 0: return None
    return (ssb / (k - 1)) / (ssw / (n - k)), k - 1, n - k, ssb, ssw

def levene(groups):
    """Ujian Levene (berasaskan min, seperti SPSS/PSPP): ANOVA atas |x - min kumpulan|."""
    return anova1([[abs(v - sum(g) / len(g)) for v in g] for g in groups])

def ranks(v):
    """Pangkat dengan purata untuk nilai seri."""
    o = sorted(range(len(v)), key=v.__getitem__); r = [0.0] * len(v); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]: j += 1
        for q in range(i, j + 1): r[o[q]] = (i + j) / 2 + 1
        i = j + 1
    return r

def _simpson(f, a, b, m):
    h = (b - a) / m
    return (f(a) + f(b) + sum((4 if i % 2 else 2) * f(a + i * h) for i in range(1, m))) * h / 3

def ptukey(q, k, df):
    """P(Q <= q) bagi taburan julat student (k min, dk df), dengan kamiran berangka."""
    if q <= 0: return 0.0
    r2, rpi = math.sqrt(2), math.sqrt(2 * math.pi)
    Phi = lambda z: .5 * math.erfc(-z / r2)
    prange = lambda w: k * _simpson(lambda z: math.exp(-z * z / 2) / rpi * (Phi(z) - Phi(z - w)) ** (k - 1), -8, 8, 120)
    if df > 20000: return min(1.0, prange(q))
    c = df / 2 * math.log(df) - math.lgamma(df / 2) - (df / 2 - 1) * math.log(2)
    sd = 1 / math.sqrt(2 * df)
    dens = lambda s: math.exp(c + (df - 1) * math.log(s) - df * s * s / 2) if s > 0 else 0.0
    return min(1.0, _simpson(lambda s: dens(s) * prange(q * s), max(0.0, 1 - 10 * sd), 1 + 12 * sd, 100))

def qtukey(p, k, df):
    """Songsang ptukey (pembahagian dua)."""
    lo, hi = 0.0, 100.0
    for _ in range(30):
        mid = (lo + hi) / 2
        if ptukey(mid, k, df) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def tukey(groups):
    """Tukey HSD (Tukey-Kramer bagi n tak sama). Pulangkan senarai (i, j, beza, ralat piawai, p, SK95 bawah, atas)."""
    k, n = len(groups), sum(map(len, groups)); df = n - k
    means = [sum(g) / len(g) for g in groups]
    msw = sum((v - m) ** 2 for g, m in zip(groups, means) for v in g) / df
    qc = qtukey(.95, k, df); out = []
    for i in range(k):
        for j in range(k):
            if i == j: continue
            se = math.sqrt(msw / 2 * (1 / len(groups[i]) + 1 / len(groups[j]))); d = means[i] - means[j]
            out.append((i, j, d, se * math.sqrt(2), 1 - ptukey(abs(d) / se, k, df), d - qc * se, d + qc * se))
    return out

def anova2(y, a, b):
    """ANOVA dua hala, JK Jenis III (pengekodan kesan). a, b: label faktor bagi setiap kes.
    Pulangkan dict atau None jika ada sel kosong / data tidak mencukupi."""
    la, lb = sorted(set(a), key=sortkey), sorted(set(b), key=sortkey)
    if len(la) < 2 or len(lb) < 2 or len({(x, z) for x, z in zip(a, b)}) < len(la) * len(lb): return None
    eff = lambda lv, levels: [1.0 if lv == levels[i] else -1.0 if lv == levels[-1] else 0.0 for i in range(len(levels) - 1)]
    A = [eff(v, la) for v in a]; B = [eff(v, lb) for v in b]; AB = [[p * q for p in ra for q in rb] for ra, rb in zip(A, B)]
    full = ols(y, [ra + rb + rab for ra, rb, rab in zip(A, B, AB)])
    if full is None or full["dfe"] < 1: return None
    terms = {}  # JK Jenis III = JK reja model tanpa sebutan itu - JK reja model penuh
    for name, keep, df in (("A", (B, AB), len(A[0])), ("B", (A, AB), len(B[0])), ("AB", (A, B), len(AB[0]))):
        red = ols(y, [r1 + r2 for r1, r2 in zip(*keep)])
        if red is None: return None
        terms[name] = (red["sse"] - full["sse"], df)
    return dict(terms=terms, sse=full["sse"], dfe=full["dfe"], sst=full["sst"], n=full["n"], la=la, lb=lb)

def sortkey(k):
    try: return (0, float(k.replace(",", ".")), k)
    except ValueError: return (1, 0, k)

def fp(p): return "< .001" if p < .001 else f"{p:.3f}"

def _phi2(z): return math.erfc(abs(z) / math.sqrt(2))  # p dua hujung bagi z normal

def skew_kurt(x):
    """Kepencongan G1 dan kurtosis lebihan G2 dengan ralat piawai (formula SPSS). None jika n < 4 atau SP sifar."""
    n = len(x)
    if n < 4: return None
    m = sum(x) / n; m2 = sum((v - m) ** 2 for v in x) / n
    if m2 == 0: return None
    m3 = sum((v - m) ** 3 for v in x) / n; m4 = sum((v - m) ** 4 for v in x) / n
    g1 = m3 / m2 ** 1.5 * math.sqrt(n * (n - 1)) / (n - 2)
    g2 = (n - 1) / ((n - 2) * (n - 3)) * ((n + 1) * (m4 / m2 ** 2) - 3 * (n - 1))
    ses = math.sqrt(6 * n * (n - 1) / ((n - 2) * (n + 1) * (n + 3)))
    sek = 2 * ses * math.sqrt((n * n - 1) / ((n - 3) * (n + 5)))
    return g1, ses, g2, sek

def _tie_sum(r):
    """Jumlah (t³ - t) bagi kumpulan nilai seri (untuk pembetulan seri)."""
    c = {}
    for v in r: c[v] = c.get(v, 0) + 1
    return sum(t ** 3 - t for t in c.values())

def mann_whitney(a, b):
    """Mann-Whitney U (asimptotik, pembetulan seri, tanpa pembetulan kesinambungan seperti SPSS).
    Pulangkan (U, Z, p, r, min pangkat a, min pangkat b) atau None."""
    n1, n2 = len(a), len(b); n = n1 + n2
    if n1 < 1 or n2 < 1: return None
    r = ranks(list(a) + list(b)); r1 = sum(r[:n1])
    u1 = r1 - n1 * (n1 + 1) / 2; u = min(u1, n1 * n2 - u1)
    var = n1 * n2 / 12 * ((n + 1) - _tie_sum(r) / (n * (n - 1)))
    if var <= 0: return None
    z = (u - n1 * n2 / 2) / math.sqrt(var)
    return u, z, _phi2(z), abs(z) / math.sqrt(n), r1 / n1, sum(r[n1:]) / n2

def wilcoxon(x, y):
    """Ujian pangkat bertanda Wilcoxon (beza sifar dibuang, pembetulan seri, asimptotik).
    Pulangkan (W+, W-, Z, p, r, n bukan sifar) atau None."""
    d = [a - b for a, b in zip(x, y) if a != b]; n = len(d)
    if n < 1: return None
    r = ranks([abs(v) for v in d]); wp = sum(rk for rk, v in zip(r, d) if v > 0); wm = n * (n + 1) / 2 - wp
    var = n * (n + 1) * (2 * n + 1) / 24 - _tie_sum(r) / 48
    if var <= 0: return None
    z = (min(wp, wm) - n * (n + 1) / 4) / math.sqrt(var)
    return wp, wm, z, _phi2(z), abs(z) / math.sqrt(n), n

def kruskal(groups):
    """Kruskal-Wallis H (pembetulan seri). Pulangkan (H, dk, p, epsilon², min pangkat setiap kumpulan) atau None."""
    allv = [v for g in groups for v in g]; n, k = len(allv), len(groups)
    if k < 2 or n < 3: return None
    r = ranks(allv); i = 0; h = 0.0; mr = []
    for g in groups:
        s = sum(r[i:i + len(g)]); h += s * s / len(g); mr.append(s / len(g)); i += len(g)
    h = 12 / (n * (n + 1)) * h - 3 * (n + 1); c = 1 - _tie_sum(r) / (n ** 3 - n)
    if c <= 0: return None
    h /= c
    return h, k - 1, p_chi2(h, k - 1), h / (n - 1), mr

def cohen_d(a, b):
    """Cohen's d dengan SP terkumpul."""
    n1, n2 = len(a), len(b)
    sp = math.sqrt(((n1 - 1) * st.variance(a) + (n2 - 1) * st.variance(b)) / (n1 + n2 - 2))
    return (st.mean(a) - st.mean(b)) / sp if sp else math.nan

def read_xlsx(path):
    """Baca helaian pertama fail .xlsx sebagai senarai baris teks (tanpa pustaka luar).
    shortcut: tarikh keluar sebagai nombor siri Excel; tukar dalam Excel jika perlu."""
    import zipfile, re, xml.etree.ElementTree as ET
    M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    with zipfile.ZipFile(path) as z:
        names = z.namelist(); shared = []
        if "xl/sharedStrings.xml" in names:
            shared = ["".join(t.text or "" for t in si.iter(M + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(M + "si")]
        rid = ET.fromstring(z.read("xl/workbook.xml")).find(f"{M}sheets/{M}sheet").get(RID)
        target = next(r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")) if r.get("Id") == rid)
        sheet = ET.fromstring(z.read(target.lstrip("/") if target.startswith("/") else "xl/" + target))
    def col(ref):
        n = 0
        for ch in re.match(r"[A-Z]+", ref).group(): n = n * 26 + ord(ch) - 64
        return n - 1
    rows = []
    for row in sheet.iter(M + "row"):
        cells = {}
        for i, c in enumerate(row.findall(M + "c")):
            t, v = c.get("t"), c.find(M + "v")
            if t == "s": val = shared[int(v.text)]
            elif t == "inlineStr": val = "".join(x.text or "" for x in c.iter(M + "t"))
            elif v is None or v.text is None: val = ""
            elif t in ("str", "b", "e"): val = v.text
            else:
                f = float(v.text); val = str(int(f)) if f.is_integer() and abs(f) < 1e15 else repr(f)
            cells[col(c.get("r")) if c.get("r") else i] = val
        if any(cells.values()): rows.append([cells.get(j, "") for j in range(max(cells) + 1)])
    w = max(map(len, rows), default=0)
    return [r + [""] * (w - len(r)) for r in rows]

# ---------- Fasa 2: kebolehpercayaan, EFA, saringan ----------
def corr_matrix(rows):
    """Matriks korelasi Pearson (baris = kes lengkap)."""
    n, p = len(rows), len(rows[0]); m = [sum(r[j] for r in rows) / n for j in range(p)]
    c = [[sum((r[i] - m[i]) * (r[j] - m[j]) for r in rows) for j in range(p)] for i in range(p)]
    return [[c[i][j] / math.sqrt(c[i][i] * c[j][j]) if c[i][i] and c[j][j] else 0.0 for j in range(p)] for i in range(p)]

def cov_matrix(rows):
    n, p = len(rows), len(rows[0]); m = [sum(r[j] for r in rows) / n for j in range(p)]
    return [[sum((r[i] - m[i]) * (r[j] - m[j]) for r in rows) / (n - 1) for j in range(p)] for i in range(p)], m

def logdet(m):
    """log|det| melalui penghapusan Gauss; None jika singular."""
    a = [r[:] for r in m]; n = len(a); s = 0.0
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(a[r][c]))
        if abs(a[piv][c]) < 1e-14: return None
        a[c], a[piv] = a[piv], a[c]; s += math.log(abs(a[c][c]))
        for r in range(c + 1, n):
            f = a[r][c] / a[c][c]
            if f: a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return s

def jacobi_eig(a, sweeps=100):
    """Nilai eigen (menurun) dan vektor eigen bagi matriks simetri, kaedah Jacobi kitaran."""
    n = len(a); a = [r[:] for r in a]; v = [[float(i == j) for j in range(n)] for i in range(n)]
    for _s in range(sweeps):
        if sum(a[i][j] ** 2 for i in range(n) for j in range(i + 1, n)) < 1e-22: break
        for p in range(n):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-300: continue
                th = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = (1 if th >= 0 else -1) / (abs(th) + math.sqrt(th * th + 1)); c = 1 / math.sqrt(t * t + 1); s = t * c
                for k in range(n):
                    x, y = a[k][p], a[k][q]; a[k][p], a[k][q] = c * x - s * y, s * x + c * y
                for k in range(n):
                    x, y = a[p][k], a[q][k]; a[p][k], a[q][k] = c * x - s * y, s * x + c * y
                for k in range(n):
                    x, y = v[k][p], v[k][q]; v[k][p], v[k][q] = c * x - s * y, s * x + c * y
    order = sorted(range(n), key=lambda i: -a[i][i])
    return [a[i][i] for i in order], [[v[k][i] for k in range(n)] for i in order]

def reliability(rows):
    """Cronbach's alpha dan statistik item (baris = kes lengkap, lajur = item). None jika < 2 item atau < 2 kes."""
    n, k = len(rows), len(rows[0]) if rows else 0
    if k < 2 or n < 2: return None
    var = lambda v: st.variance(v) if len(set(v)) > 1 else 0.0
    alpha = lambda cols: (len(cols) / (len(cols) - 1)) * (1 - sum(var([r[j] for r in rows]) for j in cols) / var([sum(r[j] for j in cols) for r in rows])) \
        if len(cols) > 1 and var([sum(r[j] for j in cols) for r in rows]) > 0 else None
    tot = [sum(r) for r in rows]; R = corr_matrix(rows)
    rbar = sum(R[i][j] for i in range(k) for j in range(k) if i != j) / (k * (k - 1))
    items = []
    for j in range(k):
        rest = [t - r[j] for t, r in zip(tot, rows)]; col = [r[j] for r in rows]
        try: ritc = st.correlation(col, rest)
        except st.StatisticsError: ritc = None
        items.append(dict(mean=st.mean(col), sd=math.sqrt(var(col)), smd=st.mean(rest), svd=var(rest), ritc=ritc,
                          aid=alpha([c for c in range(k) if c != j])))
    return dict(n=n, k=k, alpha=alpha(list(range(k))), std=k * rbar / (1 + (k - 1) * rbar), items=items,
                mean=st.mean(tot), sd=math.sqrt(var(tot)))

def kmo_bartlett(R, n):
    """KMO keseluruhan, MSA setiap item, dan ujian sfera Bartlett (χ², dk, p). None jika R singular."""
    p = len(R); inv = inverse(R); ld = logdet(R)
    if inv is None or ld is None: return None
    pr = [[-inv[i][j] / math.sqrt(inv[i][i] * inv[j][j]) for j in range(p)] for i in range(p)]
    r2 = lambda i: sum(R[i][j] ** 2 for j in range(p) if j != i); q2 = lambda i: sum(pr[i][j] ** 2 for j in range(p) if j != i)
    kmo = sum(map(r2, range(p))) / (sum(map(r2, range(p))) + sum(map(q2, range(p))))
    msa = [r2(i) / (r2(i) + q2(i)) for i in range(p)]
    chi = -(n - 1 - (2 * p + 5) / 6) * ld; df = p * (p - 1) // 2
    return kmo, msa, chi, df, p_chi2(chi, df)

def _loadings(vals, vecs, k):
    L = [[vecs[j][i] * math.sqrt(max(vals[j], 0.0)) for j in range(k)] for i in range(len(vecs[0]))]
    for j in range(k):  # tanda: jumlah muatan positif (tanda vektor eigen adalah sembarangan)
        if sum(r[j] for r in L) < 0:
            for r in L: r[j] = -r[j]
    return L

def extract(R, k, method="paf", maxit=500, tol=1e-6):
    """Pengekstrakan k faktor: 'pca' atau 'paf' (Principal Axis Factoring berulang, komunaliti awal = SMC).
    Pulangkan (muatan, komunaliti awal, komunaliti akhir, lelaran, menumpu?)."""
    p = len(R)
    if method == "pca":
        vals, vecs = jacobi_eig(R); L = _loadings(vals, vecs, k)
        return L, [1.0] * p, [sum(x * x for x in r) for r in L], 0, True
    inv = inverse(R)
    h0 = [1 - 1 / inv[i][i] for i in range(p)] if inv else [max(abs(R[i][j]) for j in range(p) if j != i) for i in range(p)]
    h = h0[:]
    for it in range(1, maxit + 1):
        vals, vecs = jacobi_eig([[h[i] if i == j else R[i][j] for j in range(p)] for i in range(p)])
        L = _loadings(vals, vecs, k); hn = [sum(x * x for x in r) for r in L]
        done = max(abs(a - b) for a, b in zip(h, hn)) < tol; h = hn
        if done: return L, h0, h, it, True
    return L, h0, h, maxit, False

def varimax(L, maxit=1000, tol=1e-10):
    """Putaran Varimax dengan normalisasi Kaiser (kaedah pasangan Kaiser). Pulangkan (muatan, matriks putaran T)."""
    p, k = len(L), len(L[0]); T = [[float(i == j) for j in range(k)] for i in range(k)]
    if k < 2: return [r[:] for r in L], T
    h = [math.sqrt(sum(x * x for x in r)) or 1.0 for r in L]; A = [[x / hi for x in r] for r, hi in zip(L, h)]
    for _it in range(maxit):
        moved = False
        for i in range(k - 1):
            for j in range(i + 1, k):
                u = [r[i] ** 2 - r[j] ** 2 for r in A]; v = [2 * r[i] * r[j] for r in A]
                a, b = sum(u), sum(v); c = sum(x * x - y * y for x, y in zip(u, v)); d = 2 * sum(x * y for x, y in zip(u, v))
                phi = math.atan2(d - 2 * a * b / p, c - (a * a - b * b) / p) / 4
                if abs(phi) < tol: continue
                moved = True; cs, sn = math.cos(phi), math.sin(phi)
                for M in (A, T):
                    for r in M: r[i], r[j] = r[i] * cs + r[j] * sn, -r[i] * sn + r[j] * cs
        if not moved: break
    return [[x * hi for x in r] for r, hi in zip(A, h)], T

def promax(L, power=4):
    """Promax (kappa=4) selepas Varimax, dengan normalisasi Kaiser. Pulangkan (pola, struktur, korelasi faktor)."""
    V, _T = varimax(L); k = len(V[0])
    if k < 2: return V, V, [[1.0]]
    w = [math.sqrt(sum(x * x for x in r)) or 1.0 for r in V]; X = [[x / wi for x in r] for r, wi in zip(V, w)]
    Y = [[x * abs(x) ** (power - 1) for x in r] for r in X]
    mm = lambda A, B: [[sum(A[i][t] * B[t][j] for t in range(len(B))) for j in range(len(B[0]))] for i in range(len(A))]
    tr = lambda A: [list(c) for c in zip(*A)]
    xtx = inverse(mm(tr(X), X))
    if xtx is None: return None
    U = mm(mm(xtx, tr(X)), Y); utu = inverse(mm(tr(U), U))
    if utu is None: return None
    U = [[U[i][j] * math.sqrt(utu[j][j]) for j in range(k)] for i in range(k)]
    P = [[x * wi for x in r] for r, wi in zip(mm(X, U), w)]
    Ui = inverse(U)
    if Ui is None: return None
    phi = mm(Ui, tr(Ui))
    for j in range(k):  # tanda: jumlah muatan positif
        if sum(r[j] for r in P) < 0:
            for r in P: r[j] = -r[j]
            for t in range(k):
                if t != j: phi[j][t] = phi[t][j] = -phi[j][t]
    return P, mm(P, phi), phi

def mahalanobis(rows):
    """Jarak Mahalanobis D² setiap kes dan p (χ², dk = bilangan pemboleh ubah). None jika kovarians singular."""
    S, m = cov_matrix(rows); Si = inverse(S); k = len(m)
    if Si is None: return None
    out = []
    for r in rows:
        d = [x - mu for x, mu in zip(r, m)]; d2 = sum(d[i] * Si[i][j] * d[j] for i in range(k) for j in range(k))
        out.append((d2, p_chi2(d2, k)))
    return out


# ---------- Fasa 3: mediasi, moderasi, regresi hierarki, ANCOVA ----------
def qt(alpha, df):
    """Nilai t kritikal dua hujung: p_t(t, df) = alpha (pembahagian dua)."""
    lo, hi = 0.0, 1000.0
    for _i in range(100):
        mid = (lo + hi) / 2
        if p_t(mid, df) > alpha: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def effect_codes(v, levels):
    """Pengekodan kesan (sum-to-zero): aras terakhir = -1 pada semua lajur."""
    return [1.0 if v == levels[i] else -1.0 if v == levels[-1] else 0.0 for i in range(len(levels) - 1)]

def _beta(y, X):
    """Pekali OLS sahaja (X sudah termasuk pintasan) - laju untuk bootstrap. None jika singular."""
    p = len(X[0]); xtx = [[0.0] * p for _i in range(p)]; xty = [0.0] * p
    for r, yi in zip(X, y):
        for a in range(p):
            ra = r[a]; xty[a] += ra * yi; row = xtx[a]
            for b in range(a, p): row[b] += ra * r[b]
    for a in range(p):
        for b in range(a): xtx[a][b] = xtx[b][a]
    inv = inverse(xtx)
    return None if inv is None else [sum(inv[a][c] * xty[c] for c in range(p)) for a in range(p)]

def _indirect(y, x, ms, cs, idx):
    """Kesan tidak langsung a_i*b_i bagi sampel indeks idx (untuk bootstrap)."""
    k = len(ms[0]); out = []; bs = None
    Xy = [[1.0, x[i]] + ms[i] + cs[i] for i in idx]; bs = _beta([y[i] for i in idx], Xy)
    if bs is None: return None
    for j in range(k):
        ba = _beta([ms[i][j] for i in idx], [[1.0, x[i]] + cs[i] for i in idx])
        if ba is None: return None
        out.append(ba[1] * bs[2 + j])
    return out

def mediation(y, x, ms, cs, boots=5000, seed=12345, progress=None):
    """Mediasi selari (seperti PROCESS Model 4). ms: senarai nilai mediator setiap kes; cs: kovariat setiap kes.
    Pulangkan dict laluan a, b, c, c' (dari ols) dan kesan tidak langsung dengan SK bootstrap persentil 95%."""
    import random
    n, k = len(y), len(ms[0])
    am = [ols([m[j] for m in ms], [[xi] + c for xi, c in zip(x, cs)]) for j in range(k)]
    ym = ols(y, [[xi] + m + c for xi, m, c in zip(x, ms, cs)]); tm = ols(y, [[xi] + c for xi, c in zip(x, cs)])
    if ym is None or tm is None or None in am: return None
    ind = [am[j]["b"][1] * ym["b"][2 + j] for j in range(k)]
    rnd = random.Random(seed); draws = []; tries = 0
    while len(draws) < boots and tries < boots * 2:
        tries += 1; idx = [rnd.randrange(n) for _i in range(n)]; r = _indirect(y, x, ms, cs, idx)
        if r is not None: draws.append(r + [sum(r)])
        if progress and tries % 250 == 0: progress(len(draws), boots)
    if len(draws) < boots * .9: return None
    def ci(j):
        v = sorted(d[j] for d in draws); B = len(v)
        return v[max(0, int(.025 * B))], v[min(B - 1, int(.975 * B))], st.stdev(v)
    return dict(n=n, k=k, a=am, y=ym, total=tm, ind=ind + [sum(ind)], ci=[ci(j) for j in range(k + 1)], boots=len(draws), seed=seed)

def moderation(y, x, w, cs, binary):
    """Moderasi (seperti PROCESS Model 1). X dan W berterusan dipusatkan pada min; W binari (0/1) tidak dipusatkan.
    Pulangkan model penuh, perubahan R² interaksi, dan kesan bersyarat X pada aras W."""
    n = len(y); mx = st.mean(x); mw = 0.0 if binary else st.mean(w)
    xc = [v - mx for v in x]; wc = [v - mw for v in w]
    full = ols(y, [[a, b, a * b] + c for a, b, c in zip(xc, wc, cs)]); red = ols(y, [[a, b] + c for a, b, c in zip(xc, wc, cs)])
    if full is None or red is None: return None
    dr2 = full["r2"] - red["r2"]; fch = dr2 / ((1 - full["r2"]) / full["dfe"]) if full["r2"] < 1 else math.inf
    sdw = st.stdev(w); levels = sorted(set(w)) if binary else [mw - sdw, mw, mw + sdw]
    tc = qt(.05, full["dfe"]); cond = []
    for lv in levels:
        wv = lv - mw; eff = full["b"][1] + full["b"][3] * wv
        se = math.sqrt(max(0.0, full["cov"][1][1] + wv * wv * full["cov"][3][3] + 2 * wv * full["cov"][1][3]))
        t = eff / se if se else math.inf
        cond.append(dict(w=lv, eff=eff, se=se, t=t, p=p_t(t, full["dfe"]) if se else 0.0, lo=eff - tc * se, hi=eff + tc * se))
    return dict(n=n, model=full, dr2=dr2, fch=fch, pch=p_f(fch, 1, full["dfe"]) if math.isfinite(fch) else 0.0,
                cond=cond, mx=mx, mw=mw, sdx=st.stdev(x), centred_w=not binary)

def hier_reg(y, blocks):
    """Regresi hierarki. blocks: senarai blok; setiap blok = senarai lajur nilai (setiap lajur = senarai mengikut kes).
    Pulangkan senarai model dengan R², ΔR², F perubahan."""
    out, cols, prev = [], [], 0.0
    for b in blocks:
        cols = cols + b; m = ols(y, [list(r) for r in zip(*cols)])
        if m is None: return None
        df1 = len(b); dr2 = m["r2"] - prev
        fch = (dr2 / df1) / ((1 - m["r2"]) / m["dfe"]) if m["r2"] < 1 else math.inf
        out.append(dict(m=m, dr2=dr2, df1=df1, df2=m["dfe"], fch=fch, pch=p_f(fch, df1, m["dfe"]) if math.isfinite(fch) else 0.0))
        prev = m["r2"]
    return out

def ancova(y, g, cs):
    """ANCOVA satu faktor dengan kovariat (JK Jenis III, pengekodan kesan), min terlaras, dan ujian kehomogenan kecerunan.
    g: label kumpulan; cs: kovariat setiap kes. None jika tidak boleh dikira."""
    lv = sorted(set(g), key=sortkey); q, nc = len(lv) - 1, len(cs[0])
    if q < 1: return None
    G = [effect_codes(v, lv) for v in g]
    full = ols(y, [a + c for a, c in zip(G, cs)])
    if full is None: return None
    terms = []
    red = ols(y, cs) if nc else None
    sse_red = red["sse"] if red else sum((v - st.mean(y)) ** 2 for v in y)
    terms.append((None, sse_red - full["sse"], q))
    for j in range(nc):
        r = ols(y, [a + [v for t, v in enumerate(c) if t != j] for a, c in zip(G, cs)])
        if r is None: return None
        terms.append((j, r["sse"] - full["sse"], 1))
    # kehomogenan kecerunan: tambah interaksi kumpulan x kovariat
    inter = ols(y, [a + c + [ai * ci for ai in a for ci in c] for a, c in zip(G, cs)])
    hom = None
    if inter is not None and inter["dfe"] > 0:
        dfh = q * nc; fh = ((full["sse"] - inter["sse"]) / dfh) / (inter["sse"] / inter["dfe"]) if inter["sse"] > 0 else math.inf
        hom = (fh, dfh, inter["dfe"], p_f(fh, dfh, inter["dfe"]) if math.isfinite(fh) else 0.0)
    cm = [st.mean(c[j] for c in cs) for j in range(nc)]; b, V = full["b"], full["cov"]
    def lvec(i): return [1.0] + effect_codes(lv[i], lv) + cm
    adj = []
    for i in range(len(lv)):
        L = lvec(i); est = sum(a * c for a, c in zip(L, b)); se = math.sqrt(max(0.0, sum(L[a] * V[a][c] * L[c] for a in range(len(L)) for c in range(len(L)))))
        adj.append((lv[i], sum(1 for v in g if v == lv[i]), st.mean(v for v, gg in zip(y, g) if gg == lv[i]), est, se))
    tc = qt(.05, full["dfe"]); pairs = []; m = len(lv) * (len(lv) - 1) // 2
    for i in range(len(lv)):
        for j in range(i + 1, len(lv)):
            L = [a - c for a, c in zip(lvec(i), lvec(j))]; d = sum(a * c for a, c in zip(L, b))
            se = math.sqrt(max(0.0, sum(L[a] * V[a][c] * L[c] for a in range(len(L)) for c in range(len(L)))))
            t = d / se if se else math.inf
            pairs.append((lv[i], lv[j], d, se, min(1.0, p_t(t, full["dfe"]) * m) if se else 0.0))
    return dict(levels=lv, full=full, terms=terms, hom=hom, adj=adj, pairs=pairs, tc=tc, sse=full["sse"], dfe=full["dfe"], n=len(y))
