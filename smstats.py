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
                f=(ssr / k) / mse if mse else math.inf, yhat=yhat, e=e)

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
