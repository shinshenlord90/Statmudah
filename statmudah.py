#!/usr/bin/python3
"""StatMudah - aplikasi statistik ringkas (seperti PSPP) dengan rupa Windows 7."""
import csv, math, statistics as st, tkinter as tk
from collections import Counter
from tkinter import ttk, filedialog, messagebox, simpledialog

# ---------- statistik (tiada kebergantungan luar) ----------
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

# ---------- rupa Windows 7 ----------
BG, PANEL, BORDER, SEL = "#F0F0F0", "#DCE6F4", "#A0AFC3", "#CCE8FF"
FONT = ("DejaVu Sans", 9)

def style(root):
    s = ttk.Style(root); s.theme_use("clam")
    s.configure(".", background=BG, font=FONT)
    s.configure("TButton", padding=(10, 3), background="#E8E8E8", bordercolor="#707070", relief="raised")
    s.map("TButton", background=[("active", "#DCEFFC")], bordercolor=[("active", "#3C7FB1")])
    s.configure("Tool.TButton", padding=(6, 2), background=PANEL, relief="flat", bordercolor=PANEL)
    s.map("Tool.TButton", background=[("active", "#FDF4BF")], bordercolor=[("active", "#E5C365")])
    s.configure("Treeview", background="white", fieldbackground="white", rowheight=22, bordercolor=BORDER)
    s.map("Treeview", background=[("selected", SEL)], foreground=[("selected", "black")])
    s.configure("Treeview.Heading", background="#F7F9FC", bordercolor=BORDER, relief="groove")
    s.configure("TNotebook", background=PANEL, bordercolor=BORDER)
    s.configure("TNotebook.Tab", padding=(12, 4), background="#E3EAF4")
    s.map("TNotebook.Tab", background=[("selected", "white")])
    s.configure("Tool.TFrame", background=PANEL)
    s.configure("Status.TLabel", background=PANEL, padding=(6, 2))

# ---------- dialog pilih pemboleh ubah ----------
class PickDialog(tk.Toplevel):
    """fields: list of (label, multi, numeric_only)."""
    def __init__(self, app, title, fields):
        super().__init__(app.root); self.title(title); self.configure(bg=BG); self.resizable(False, False)
        self.transient(app.root); self.result = None; self.boxes = []
        for i, (label, multi, numeric) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=0, column=i, sticky="w", padx=8, pady=(8, 2))
            lb = tk.Listbox(self, selectmode="extended" if multi else "browse", exportselection=False,
                            height=10, width=24, font=FONT, selectbackground=SEL, selectforeground="black")
            names = [c for c in app.cols if not numeric or app.numeric(c)]
            for n in names: lb.insert("end", n)
            lb.grid(row=1, column=i, padx=8); self.boxes.append((lb, names, multi))
        bar = ttk.Frame(self); bar.grid(row=2, column=0, columnspan=len(fields), sticky="e", padx=8, pady=8)
        ttk.Button(bar, text="OK", command=self.ok).pack(side="left", padx=3)
        ttk.Button(bar, text="Batal", command=self.destroy).pack(side="left", padx=3)
        self.bind("<Return>", lambda e: self.ok()); self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set(); self.wait_window()

    def ok(self):
        out = []
        for lb, names, multi in self.boxes:
            sel = [names[i] for i in lb.curselection()]
            if not sel: return messagebox.showwarning("Pilih", "Sila pilih pemboleh ubah.", parent=self)
            out.append(sel if multi else sel[0])
        self.result = out; self.destroy()

class GroupDialog(tk.Toplevel):
    """Pilih tepat 2 kumpulan daripada nilai pemboleh ubah kumpulan (seperti 'Define Groups' PSPP)."""
    def __init__(self, root, var, groups):
        super().__init__(root); self.title("Pilih 2 Kumpulan"); self.configure(bg=BG); self.resizable(False, False)
        self.transient(root); self.result = None
        self.keys = sorted(groups, key=lambda k: (App.num(k) is None, App.num(k) or 0, k))
        ttk.Label(self, text=f"'{var}' ada {len(self.keys)} kumpulan.\nKlik 2 kumpulan untuk dibandingkan:").pack(anchor="w", padx=8, pady=(8, 2))
        self.lb = tk.Listbox(self, selectmode="multiple", exportselection=False, height=min(12, len(self.keys)), width=30,
                             font=FONT, selectbackground=SEL, selectforeground="black")
        for k in self.keys: self.lb.insert("end", f"{k}   ({len(groups[k])} kes)")
        self.lb.pack(padx=8)
        bar = ttk.Frame(self); bar.pack(anchor="e", padx=8, pady=8)
        ttk.Button(bar, text="OK", command=self.ok).pack(side="left", padx=3)
        ttk.Button(bar, text="Batal", command=self.destroy).pack(side="left", padx=3)
        self.bind("<Return>", lambda e: self.ok()); self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set(); self.wait_window()

    def ok(self):
        sel = self.lb.curselection()
        if len(sel) != 2: return messagebox.showwarning("Pilih", f"Sila pilih tepat 2 kumpulan (dipilih: {len(sel)}).", parent=self)
        self.result = [self.keys[i] for i in sel]; self.destroy()

# ---------- aplikasi ----------
class App:
    def __init__(self, root):
        self.root, self.cols, self.rows, self.path = root, [], [], None
        root.title("StatMudah"); root.geometry("960x620"); root.configure(bg=BG); style(root)
        self.menu(); self.toolbar()
        self.status = ttk.Label(root, style="Status.TLabel"); self.status.pack(fill="x", side="bottom")
        self.nb = ttk.Notebook(root); self.nb.pack(fill="both", expand=True, padx=4, pady=2)
        f = ttk.Frame(self.nb); self.nb.add(f, text="  Paparan Data  ")
        self.tree = ttk.Treeview(f, show="headings", selectmode="browse")
        ys, xs = ttk.Scrollbar(f, command=self.tree.yview), ttk.Scrollbar(f, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y"); xs.pack(side="bottom", fill="x"); self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.edit_cell)
        o = ttk.Frame(self.nb); self.nb.add(o, text="  Paparan Output  ")
        self.out = tk.Text(o, font=("DejaVu Sans Mono", 10), wrap="none", bg="white", relief="flat")
        oy = ttk.Scrollbar(o, command=self.out.yview); self.out.configure(yscrollcommand=oy.set)
        oy.pack(side="right", fill="y"); self.out.pack(fill="both", expand=True)
        self.out.tag_configure("h", font=("DejaVu Sans", 11, "bold"), foreground="#1E3A8A")
        self.new(sample=True)

    def menu(self):
        m = tk.Menu(self.root, bg=BG, font=FONT, relief="flat"); self.root.config(menu=m)
        def sub(name, items):
            s = tk.Menu(m, tearoff=0, bg="white", font=FONT, activebackground=SEL, activeforeground="black")
            for it in items:
                s.add_separator() if it is None else s.add_command(label=it[0], command=it[1], accelerator=it[2] if len(it) > 2 else "")
            m.add_cascade(label=name, menu=s)
        sub("Fail", [("Baru", self.new, "Ctrl+N"), ("Buka CSV...", self.open, "Ctrl+O"), ("Simpan", self.save, "Ctrl+S"),
                     ("Simpan Sebagai...", lambda: self.save(True)), None, ("Simpan Output...", self.save_output), None, ("Keluar", self.root.quit)])
        sub("Edit", [("Tambah Baris", self.add_row), ("Tambah Pemboleh Ubah", self.add_col),
                     ("Namakan Semula Pemboleh Ubah", self.rename_col), None, ("Padam Baris Dipilih", self.del_row),
                     ("Padam Pemboleh Ubah", self.del_col), None, ("Kosongkan Output", lambda: self.out.delete("1.0", "end"))])
        sub("Analisis", [("Statistik Deskriptif...", self.descriptives), ("Frekuensi...", self.frequencies), None,
                         ("Korelasi Pearson...", self.correlation), ("Korelasi Spearman...", lambda: self.correlation(True)), ("Ujian-t Sampel Bebas...", self.ttest),
                         ("Ujian-t Berpasangan...", self.paired), ("ANOVA Sehala...", self.anova), ("ANOVA Dua Hala...", self.anova2), ("Khi Kuasa Dua...", self.chisq), None,
                         ("Regresi Linear...", self.regression), ("Regresi Logistik (Binari)...", self.logistic)])
        sub("Bantuan", [("Cara Guna", self.help), ("Perihal", lambda: messagebox.showinfo("Perihal", "StatMudah 1.0\nAnalisis statistik mudah."))])
        for k, f in (("n", self.new), ("o", self.open), ("s", self.save)): self.root.bind(f"<Control-{k}>", lambda e, f=f: f())

    def toolbar(self):
        tb = ttk.Frame(self.root, style="Tool.TFrame"); tb.pack(fill="x")
        for t, c in (("📄 Baru", self.new), ("📂 Buka", self.open), ("💾 Simpan", self.save), ("|", 0),
                     ("➕ Baris", self.add_row), ("➕ Pemboleh Ubah", self.add_col), ("|", 0),
                     ("Σ Deskriptif", self.descriptives), ("📊 Frekuensi", self.frequencies), ("t Ujian-t", self.ttest), ("❓ Bantuan", self.help)):
            if t == "|": ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=4, pady=3)
            else: ttk.Button(tb, text=t, style="Tool.TButton", width=0, command=c).pack(side="left", padx=1, pady=2)

    # ----- data -----
    def refresh(self):
        self.tree.delete(*self.tree.get_children()); self.tree["columns"] = ["#"] + self.cols
        self.tree.heading("#", text="#"); self.tree.column("#", width=45, anchor="e", stretch=False)
        for c in self.cols: self.tree.heading(c, text=c); self.tree.column(c, width=110, anchor="e")
        for i, r in enumerate(self.rows): self.tree.insert("", "end", iid=str(i), values=[i + 1] + r)
        self.status["text"] = f"  {self.path or 'Tanpa nama'}   |   {len(self.rows)} kes   |   {len(self.cols)} pemboleh ubah   |   Dwiklik sel untuk edit"

    def new(self, sample=False):
        self.path = None
        if sample:  # data contoh supaya pengguna baru boleh terus cuba
            self.cols = ["jantina", "umur", "markah_ujian1", "markah_ujian2"]
            self.rows = [[g, str(a), str(m1), str(m2)] for g, a, m1, m2 in [
                ("L", 21, 65, 70), ("P", 22, 78, 80), ("L", 20, 55, 61), ("P", 23, 88, 85), ("L", 24, 72, 75),
                ("P", 21, 81, 86), ("L", 22, 60, 66), ("P", 20, 92, 90), ("L", 23, 68, 72), ("P", 22, 75, 79)]]
        else: self.cols, self.rows = ["var1", "var2"], [["", ""] for _ in range(5)]
        self.refresh()

    def open(self):
        p = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Semua", "*")])
        if not p: return
        try:
            with open(p, newline="", encoding="utf-8-sig") as f: data = list(csv.reader(f))
        except (OSError, UnicodeDecodeError, csv.Error) as e: return messagebox.showerror("Ralat", str(e))
        if not data: return messagebox.showerror("Ralat", "Fail kosong.")
        self.cols = [c or f"var{i+1}" for i, c in enumerate(data[0])]
        self.rows = [(r + [""] * len(self.cols))[:len(self.cols)] for r in data[1:]]
        self.path = p; self.refresh()

    def save(self, as_new=False):
        if as_new or not self.path:
            p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not p: return
            self.path = p
        try:
            with open(self.path, "w", newline="", encoding="utf-8") as f: csv.writer(f).writerows([self.cols] + self.rows)
        except OSError as e: return messagebox.showerror("Ralat", str(e))
        self.refresh()

    def save_output(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Teks", "*.txt")])
        if p:
            with open(p, "w", encoding="utf-8") as f: f.write(self.out.get("1.0", "end"))

    def edit_cell(self, e):
        row, col = self.tree.identify_row(e.y), self.tree.identify_column(e.x)
        ci = int(col[1:]) - 2
        if not row or ci < 0: return
        x, y, w, h = self.tree.bbox(row, col)
        ent = ttk.Entry(self.tree); ent.insert(0, self.rows[int(row)][ci]); ent.select_range(0, "end")
        ent.place(x=x, y=y, width=w, height=h); ent.focus()
        def done(_=None):
            self.rows[int(row)][ci] = ent.get().strip(); ent.destroy()
            self.tree.item(row, values=[int(row) + 1] + self.rows[int(row)])
        ent.bind("<Return>", done); ent.bind("<FocusOut>", done); ent.bind("<Escape>", lambda _: ent.destroy())

    def add_row(self): self.rows.append([""] * len(self.cols)); self.refresh(); self.tree.see(str(len(self.rows) - 1))
    def add_col(self):
        n = simpledialog.askstring("Pemboleh Ubah Baru", "Nama pemboleh ubah:", parent=self.root)
        if n and n not in self.cols: self.cols.append(n); [r.append("") for r in self.rows]; self.refresh()
    def rename_col(self):
        if not self.cols: return
        old = simpledialog.askstring("Namakan Semula", f"Nama lama ({', '.join(self.cols)}):", parent=self.root)
        if old not in self.cols: return
        new = simpledialog.askstring("Namakan Semula", "Nama baru:", parent=self.root)
        if new and new not in self.cols: self.cols[self.cols.index(old)] = new; self.refresh()
    def del_row(self):
        s = self.tree.selection()
        if s and messagebox.askyesno("Padam", "Padam baris dipilih?"): del self.rows[int(s[0])]; self.refresh()
    def del_col(self):
        r = PickDialog(self, "Padam Pemboleh Ubah", [("Pemboleh ubah:", True, False)]).result
        if r and messagebox.askyesno("Padam", f"Padam {', '.join(r[0])}?"):
            keep = [i for i, c in enumerate(self.cols) if c not in r[0]]
            self.cols = [self.cols[i] for i in keep]; self.rows = [[x[i] for i in keep] for x in self.rows]; self.refresh()

    # ----- helper analisis -----
    @staticmethod
    def num(v):
        try: return float(v.replace(",", "."))
        except ValueError: return None
    def values(self, c):
        i = self.cols.index(c); return [v for v in (self.num(r[i]) for r in self.rows) if v is not None]
    def numeric(self, c): return len(self.values(c)) > 0
    def pairs(self, a, b):
        i, j = self.cols.index(a), self.cols.index(b)
        return [(x, y) for x, y in ((self.num(r[i]), self.num(r[j])) for r in self.rows) if x is not None and y is not None]

    def write(self, title, lines):
        self.out.insert("end", title + "\n", "h"); self.out.insert("end", "\n".join(lines) + "\n\n")
        self.out.see("end"); self.nb.select(1)

    def table(self, head, rows):
        rows = [[str(x) for x in r] for r in rows]; w = [max(len(str(h)), *(len(r[i]) for r in rows)) + 2 for i, h in enumerate(head)]
        line = "+" + "+".join("-" * x for x in w) + "+"
        fmt = lambda r: "|" + "|".join(str(v).rjust(w[i] - 1) + " " for i, v in enumerate(r)) + "|"
        return [line, fmt(head), line] + [fmt(r) for r in rows] + [line]

    # ----- analisis -----
    def descriptives(self):
        r = PickDialog(self, "Statistik Deskriptif", [("Pemboleh ubah (angka):", True, True)]).result
        if not r: return
        rows = []
        for c in r[0]:
            v = self.values(c); sd = st.stdev(v) if len(v) > 1 else 0
            rows.append([c, len(v), f"{st.mean(v):.3f}", f"{st.median(v):.3f}", f"{sd:.3f}", f"{min(v):g}", f"{max(v):g}"])
        self.write("Statistik Deskriptif", self.table(["Pemboleh ubah", "N", "Min", "Median", "SP", "Minimum", "Maksimum"], rows))

    def frequencies(self):
        r = PickDialog(self, "Frekuensi", [("Pemboleh ubah:", True, False)]).result
        if not r: return
        for c in r[0]:
            i = self.cols.index(c); cnt = Counter(x[i] for x in self.rows if x[i] != ""); n = sum(cnt.values()); cum = 0; rows = []
            for k, f in sorted(cnt.items(), key=lambda kv: (self.num(kv[0]) is None, self.num(kv[0]) or 0, kv[0])):
                cum += f; rows.append([k, f, f"{100*f/n:.1f}", f"{100*cum/n:.1f}"])
            rows.append(["Jumlah", n, "100.0", ""])
            self.write(f"Frekuensi: {c}", self.table(["Nilai", "Frekuensi", "Peratus", "Peratus Kumulatif"], rows))

    def correlation(self, spearman=False):
        name = "Korelasi Spearman" if spearman else "Korelasi Pearson"
        r = PickDialog(self, name, [("Pemboleh ubah (pilih ≥2):", True, True)]).result
        if not r: return
        vs = r[0]
        if len(vs) < 2: return messagebox.showwarning("Korelasi", "Pilih sekurang-kurangnya 2 pemboleh ubah.")
        rows = []
        for a in range(len(vs)):
            for b in range(a + 1, len(vs)):
                p = self.pairs(vs[a], vs[b]); n = len(p)
                if n < 3: rows.append([vs[a], vs[b], n, "-", "-"]); continue
                xs, ys = [x for x, _ in p], [y for _, y in p]
                if spearman: xs, ys = ranks(xs), ranks(ys)  # Spearman = Pearson atas pangkat
                try: rr = st.correlation(xs, ys)
                except st.StatisticsError: rows.append([vs[a], vs[b], n, "-", "-"]); continue
                t = rr * math.sqrt((n - 2) / max(1e-15, 1 - rr * rr))
                rows.append([vs[a], vs[b], n, f"{rr:.3f}", fp(p_t(t, n - 2))])
        self.write(name, self.table(["Pemboleh ubah 1", "Pemboleh ubah 2", "N", "rho" if spearman else "r", "Sig. (2-hujung)"], rows))

    def groups(self, dep, grp):
        i, j = self.cols.index(dep), self.cols.index(grp); g = {}
        for row in self.rows:
            v = self.num(row[i])
            if v is not None and row[j] != "": g.setdefault(row[j], []).append(v)
        return g

    def ttest(self):
        r = PickDialog(self, "Ujian-t Sampel Bebas", [("Pemboleh ubah ujian:", False, True), ("Pemboleh ubah kumpulan:", False, False)]).result
        if not r: return
        g = self.groups(*r)
        if len(g) < 2: return messagebox.showwarning("Ujian-t", f"Pemboleh ubah kumpulan perlu sekurang-kurangnya 2 kumpulan (ada {len(g)}: {', '.join(g) or 'tiada'}).")
        if len(g) > 2:
            pick = GroupDialog(self.root, r[1], g).result
            if not pick: return
            g = {k: g[k] for k in pick}
        (k1, a), (k2, b) = g.items()
        if len(a) < 2 or len(b) < 2: return messagebox.showwarning("Ujian-t", "Setiap kumpulan perlu sekurang-kurangnya 2 nilai.")
        m1, m2, v1, v2, n1, n2 = st.mean(a), st.mean(b), st.variance(a), st.variance(b), len(a), len(b)
        out = self.table(["Kumpulan", "N", "Min", "SP"], [[k1, n1, f"{m1:.3f}", f"{v1**.5:.3f}"], [k2, n2, f"{m2:.3f}", f"{v2**.5:.3f}"]])
        sp = ((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2); se = math.sqrt(sp * (1 / n1 + 1 / n2))
        se_w = math.sqrt(v1 / n1 + v2 / n2)
        rows = []
        if se > 0:
            t = (m1 - m2) / se; rows.append(["Varians sama", f"{t:.3f}", n1 + n2 - 2, fp(p_t(t, n1 + n2 - 2)), f"{m1-m2:.3f}"])
        if se_w > 0:
            df = se_w**4 / ((v1 / n1)**2 / (n1 - 1) + (v2 / n2)**2 / (n2 - 1)); t = (m1 - m2) / se_w
            rows.append(["Varians tak sama (Welch)", f"{t:.3f}", f"{df:.2f}", fp(p_t(t, df)), f"{m1-m2:.3f}"])
        if not rows: return messagebox.showwarning("Ujian-t", "Varians sifar; ujian tidak boleh dikira.")
        out += ["", "Ujian Levene Kesamaan Varians"] + self.levene_table([a, b])
        out += ["Panduan: Sig. Levene ≥ .05 → baca baris 'Varians sama'; < .05 → baca baris 'Welch'."]
        self.write(f"Ujian-t Sampel Bebas: {r[0]} mengikut {r[1]}", out + self.table(["", "t", "dk", "Sig. (2-hujung)", "Beza Min"], rows))

    def levene_table(self, groups):
        L = levene(groups)
        return self.table(["F", "dk1", "dk2", "Sig."], [[f"{L[0]:.3f}", L[1], L[2], fp(p_f(*L[:3]))] if L else ["-", "-", "-", "-"]])

    def paired(self):
        r = PickDialog(self, "Ujian-t Berpasangan", [("Pemboleh ubah 1:", False, True), ("Pemboleh ubah 2:", False, True)]).result
        if not r: return
        d = [x - y for x, y in self.pairs(*r)]; n = len(d)
        if n < 2 or st.stdev(d) == 0: return messagebox.showwarning("Ujian-t", "Data tidak mencukupi atau perbezaan sentiasa sama.")
        t = st.mean(d) / (st.stdev(d) / math.sqrt(n))
        self.write(f"Ujian-t Berpasangan: {r[0]} - {r[1]}", self.table(["N", "Beza Min", "SP Beza", "t", "dk", "Sig. (2-hujung)"],
                   [[n, f"{st.mean(d):.3f}", f"{st.stdev(d):.3f}", f"{t:.3f}", n - 1, fp(p_t(t, n - 1))]]))

    def anova(self):
        r = PickDialog(self, "ANOVA Sehala", [("Pemboleh ubah bersandar:", False, True), ("Faktor (kumpulan):", False, False)]).result
        if not r: return
        g = dict(sorted(self.groups(*r).items(), key=lambda kv: sortkey(kv[0]))); keys, gl = list(g), list(g.values())
        res = anova1(gl)
        if res is None: return messagebox.showwarning("ANOVA", "Perlu ≥2 kumpulan, data mencukupi, dan varians dalam kumpulan bukan sifar.")
        f, d1, d2, ssb, ssw = res
        out = self.table(["Kumpulan", "N", "Min", "SP"], [[kk, len(x), f"{st.mean(x):.3f}", f"{st.stdev(x):.3f}" if len(x) > 1 else "-"] for kk, x in g.items()])
        out += ["", "Ujian Levene Kesamaan Varians"] + self.levene_table(gl)
        out += self.table(["Sumber", "JK", "dk", "MK", "F", "Sig."],
                   [["Antara kumpulan", f"{ssb:.3f}", d1, f"{ssb/d1:.3f}", f"{f:.3f}", fp(p_f(f, d1, d2))],
                    ["Dalam kumpulan", f"{ssw:.3f}", d2, f"{ssw/d2:.3f}", "", ""], ["Jumlah", f"{ssb+ssw:.3f}", d1 + d2, "", "", ""]])
        if len(g) >= 3:
            out += ["", "Ujian Post-hoc Tukey HSD"] + self.table(["(I)", "(J)", "Beza Min (I-J)", "Ralat Piawai", "Sig.", "SK 95% Bawah", "SK 95% Atas"],
                   [[keys[i], keys[j], f"{d:.3f}" + ("*" if p < .05 else ""), f"{se:.3f}", fp(p), f"{lo:.3f}", f"{hi:.3f}"]
                    for i, j, d, se, p, lo, hi in tukey(gl)])
            out += ["* Beza min signifikan pada aras .05."]
        self.write(f"ANOVA Sehala: {r[0]} mengikut {r[1]}", out)

    def anova2(self):
        r = PickDialog(self, "ANOVA Dua Hala", [("Pemboleh ubah bersandar:", False, True), ("Faktor A:", False, False), ("Faktor B:", False, False)]).result
        if not r: return
        dep, fa, fb = r
        if fa == fb: return messagebox.showwarning("ANOVA Dua Hala", "Faktor A dan B mesti berbeza.")
        i, ja, jb = (self.cols.index(c) for c in r); data = []
        for row in self.rows:
            v = self.num(row[i])
            if v is not None and row[ja] != "" and row[jb] != "": data.append((v, row[ja], row[jb]))
        m = anova2(*zip(*data)) if data else None
        if m is None: return messagebox.showwarning("ANOVA Dua Hala", "Tidak boleh dikira: setiap faktor perlu ≥2 aras, setiap gabungan A×B perlu ada data, dan data mesti mencukupi.")
        cells = {}
        for v, a, b in data: cells.setdefault((a, b), []).append(v)
        out = ["Min (N) setiap sel"] + self.table([f"{fa} \\ {fb}"] + m["lb"],
              [[a] + [f"{st.mean(cells[a, b]):.3f} ({len(cells[a, b])})" for b in m["lb"]] for a in m["la"]])
        out += ["", "Ujian Levene Kesamaan Varians (semua sel)"] + self.levene_table(list(cells.values()))
        mse = m["sse"] / m["dfe"]; rows = []
        for key, label in (("A", fa), ("B", fb), ("AB", f"{fa} × {fb}")):
            ss, df = m["terms"][key]; f = (ss / df) / mse if mse else math.inf
            rows.append([label, f"{ss:.3f}", df, f"{ss/df:.3f}", f"{f:.3f}", fp(p_f(f, df, m["dfe"])) if math.isfinite(f) else "< .001"])
        rows += [["Ralat", f"{m['sse']:.3f}", m["dfe"], f"{mse:.3f}", "", ""], ["Jumlah terbetul", f"{m['sst']:.3f}", m["n"] - 1, "", "", ""]]
        out += self.table(["Sumber", "JK Jenis III", "dk", "MK", "F", "Sig."], rows)
        out += ["Panduan: Jika interaksi (A × B) signifikan, kesan A bergantung pada aras B — tafsir min sel, bukan kesan utama sahaja."]
        self.write(f"ANOVA Dua Hala: {dep} mengikut {fa} dan {fb}", out)

    def chisq(self):
        r = PickDialog(self, "Khi Kuasa Dua", [("Baris:", False, False), ("Lajur:", False, False)]).result
        if not r: return
        i, j = self.cols.index(r[0]), self.cols.index(r[1])
        obs = Counter((x[i], x[j]) for x in self.rows if x[i] != "" and x[j] != "")
        R, C = sorted({a for a, _ in obs}), sorted({b for _, b in obs}); n = sum(obs.values())
        if len(R) < 2 or len(C) < 2: return messagebox.showwarning("Khi Kuasa Dua", "Setiap pemboleh ubah perlu ≥2 kategori.")
        rt = {a: sum(obs[a, b] for b in C) for a in R}; ct = {b: sum(obs[a, b] for a in R) for b in C}
        x2 = sum((obs[a, b] - rt[a] * ct[b] / n)**2 / (rt[a] * ct[b] / n) for a in R for b in C); df = (len(R) - 1) * (len(C) - 1)
        tab = self.table([f"{r[0]} \\ {r[1]}"] + C + ["Jumlah"], [[a] + [obs[a, b] for b in C] + [rt[a]] for a in R] + [["Jumlah"] + [ct[b] for b in C] + [n]])
        self.write(f"Khi Kuasa Dua: {r[0]} x {r[1]}", tab + self.table(["Khi kuasa dua", "dk", "Sig."], [[f"{x2:.3f}", df, fp(p_chi2(x2, df))]]))

    def regression(self):
        r = PickDialog(self, "Regresi Linear", [("Pemboleh ubah bersandar (Y):", False, True), ("Peramal (X, boleh >1):", True, True)]).result
        if not r: return
        dep, ind = r
        if dep in ind: return messagebox.showwarning("Regresi", "Y tidak boleh juga menjadi peramal.")
        idx = [self.cols.index(c) for c in [dep] + ind]; data = []
        for row in self.rows:  # buang kes yang ada nilai kosong (listwise)
            v = [self.num(row[i]) for i in idx]
            if None not in v: data.append(v)
        m = ols([d[0] for d in data], [d[1:] for d in data]) if data else None
        if m is None: return messagebox.showwarning("Regresi", "Tidak boleh dikira: data tidak mencukupi, Y malar, atau peramal berkolinear.")
        pf = lambda x, df: fp(p_t(x, df)) if math.isfinite(x) else "< .001"
        out = self.table(["N", "R", "R²", "R² Terlaras", "Ralat Piawai Anggaran"],
                         [[m["n"], f"{math.sqrt(max(0, m['r2'])):.3f}", f"{m['r2']:.3f}", f"{m['adj']:.3f}", f"{m['see']:.3f}"]])
        out += self.table(["Sumber", "JK", "dk", "MK", "F", "Sig."],
                          [["Regresi", f"{m['ssr']:.3f}", m["k"], f"{m['ssr']/m['k']:.3f}", f"{m['f']:.3f}",
                            fp(p_f(m["f"], m["k"], m["dfe"])) if math.isfinite(m["f"]) else "< .001"],
                           ["Reja", f"{m['sse']:.3f}", m["dfe"], f"{m['sse']/m['dfe']:.3f}", "", ""],
                           ["Jumlah", f"{m['sst']:.3f}", m["n"] - 1, "", "", ""]])
        xs = [d[1:] for d in data]; vf = [None] + vif(xs)
        fv = lambda v: "-" if v is None else ("∞" if math.isinf(v) else f"{v:.3f}")
        out += self.table(["", "B", "Ralat Piawai", "Beta", "t", "Sig.", "Toleransi", "VIF"],
                          [[name, f"{m['b'][a]:.3f}", f"{m['se'][a]:.3f}", "" if a == 0 else f"{m['beta'][a]:.3f}",
                            f"{m['t'][a]:.3f}", pf(m["t"][a], m["dfe"]),
                            "" if a == 0 else fv(None if vf[a] is None else 1 / vf[a]), "" if a == 0 else fv(vf[a])]
                           for a, name in enumerate(["(Pemalar)"] + ind)])
        # ujian andaian: Sig. >= .05 bermaksud andaian tidak ditolak
        ok = lambda p: "Dipenuhi" if p >= .05 else "Dilanggar"
        sw, bp, dw = shapiro(m["e"]), breusch_pagan(m["e"], xs), durbin_watson(m["e"]) if m["sse"] > 0 else None
        rows = [["Normaliti reja (Shapiro-Wilk)", "W = " + f"{sw[0]:.3f}", fp(sw[1]), ok(sw[1])] if sw else ["Normaliti reja (Shapiro-Wilk)", "-", "-", "Tak boleh dikira"],
                [f"Homoskedastisiti (Breusch-Pagan, dk={bp[1]})", "χ² = " + f"{bp[0]:.3f}", fp(p_chi2(*bp)), ok(p_chi2(*bp))] if bp else ["Homoskedastisiti (Breusch-Pagan)", "-", "-", "Tak boleh dikira"],
                ["Kebebasan reja (Durbin-Watson)", "d = " + f"{dw:.3f}" if dw is not None else "-", "",
                 "-" if dw is None else ("Dipenuhi" if 1.5 <= dw <= 2.5 else "Semak")],
                ["Multikolinearan (VIF maks)", fv(max((v for v in vf[1:] if v is not None), default=None)), "",
                 "Dipenuhi" if all(v is not None and v < 10 for v in vf[1:]) else "Semak"]]
        out += ["", "Ujian Andaian Regresi"] + self.table(["Andaian", "Statistik", "Sig.", "Keputusan"], rows)
        out += ["Panduan: Sig. ≥ .05 = andaian dipenuhi; Durbin-Watson 1.5–2.5 = OK; VIF < 10 = OK."]
        self.write(f"Regresi Linear: {dep} ~ {' + '.join(ind)}", out)
        sd = m["see"] or 1; z = sorted(v / sd for v in m["e"]); n = len(z); N = st.NormalDist()
        self.plots([("Reja lwn Nilai Ramalan", m["yhat"], m["e"], "Nilai ramalan", "Reja", "zero"),
                    ("Plot Q-Q Normal Reja", [N.inv_cdf((i - .375) / (n + .25)) for i in range(1, n + 1)], z,
                     "Kuantil teori", "Reja piawai", "diag")])

    def plots(self, specs):
        """Lukis plot serakan dalam Paparan Output. spec: (tajuk, x, y, label x, label y, 'zero'|'diag')."""
        W, H, L, B = 380, 280, 50, 40
        for title, xs, ys, xl, yl, ref in specs:
            c = tk.Canvas(self.out, width=W, height=H, bg="white", highlightthickness=1, highlightbackground=BORDER)
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            if ref == "diag": x0 = y0 = min(x0, y0); x1 = y1 = max(x1, y1)
            if ref == "zero": y0, y1 = min(y0, 0), max(y1, 0)
            x1, y1 = (x1 if x1 > x0 else x0 + 1), (y1 if y1 > y0 else y0 + 1)
            px = lambda v: L + (v - x0) / (x1 - x0) * (W - L - 15); py = lambda v: H - B - (v - y0) / (y1 - y0) * (H - B - 30)
            c.create_text(W / 2, 12, text=title, font=("DejaVu Sans", 9, "bold"), fill="#1E3A8A")
            c.create_rectangle(L, 30, W - 15, H - B, outline="#888")
            for v in (x0, x1): c.create_text(px(v), H - B + 10, text=f"{v:.3g}", font=FONT)
            for v in (y0, y1): c.create_text(L - 4, py(v), text=f"{v:.3g}", anchor="e", font=FONT)
            c.create_text(W / 2, H - 10, text=xl, font=FONT); c.create_text(12, H / 2 - B / 2, text=yl, angle=90, font=FONT)
            if ref == "zero": c.create_line(L, py(0), W - 15, py(0), fill="#C0392B", dash=(4, 2))
            else: c.create_line(px(x0), py(x0), px(x1), py(x1), fill="#C0392B", dash=(4, 2))
            for x, y in zip(xs, ys): c.create_oval(px(x) - 3, py(y) - 3, px(x) + 3, py(y) + 3, fill="#3C7FB1", outline="#1E3A8A")
            self.out.window_create("end", window=c, padx=4, pady=4)
        self.out.insert("end", "\n\n"); self.out.see("end")

    def logistic(self):
        r = PickDialog(self, "Regresi Logistik (Binari)", [("Pemboleh ubah bersandar (2 kategori):", False, False), ("Peramal (X, angka):", True, True)]).result
        if not r: return
        dep, ind = r
        if dep in ind: return messagebox.showwarning("Regresi Logistik", "Y tidak boleh juga menjadi peramal.")
        di, idx = self.cols.index(dep), [self.cols.index(c) for c in ind]; data = []
        for row in self.rows:  # listwise
            v = [self.num(row[i]) for i in idx]
            if row[di] != "" and None not in v: data.append((row[di], v))
        cats = sorted({d[0] for d in data}, key=lambda k: (self.num(k) is None, self.num(k) or 0, k))
        if len(cats) != 2: return messagebox.showwarning("Regresi Logistik", f"Pemboleh ubah bersandar mesti ada tepat 2 kategori (ada {len(cats)}).")
        y = [int(d[0] == cats[1]) for d in data]; xs = [d[1] for d in data]
        m = logit(y, xs) if len(data) > len(ind) + 1 else None
        if m is None: return messagebox.showwarning("Regresi Logistik", "Model tidak menumpu: data tidak mencukupi, peramal berkolinear, atau pemisahan sempurna (satu peramal meramal Y dengan tepat).")
        out = [f"Pengekodan: {cats[0]} = 0, {cats[1]} = 1   (kebarangkalian yang dimodelkan: {dep} = {cats[1]})"]
        out += self.table(["N", "-2 Log Kebolehjadian", "R² Cox & Snell", "R² Nagelkerke"],
                          [[m["n"], f"{-2*m['ll']:.3f}", f"{m['cs']:.3f}", f"{m['nk']:.3f}"]])
        out += ["", "Ujian Omnibus Model"] + self.table(["χ²", "dk", "Sig."], [[f"{m['chi2']:.3f}", m["k"], fp(p_chi2(m["chi2"], m["k"]))]])
        ex = lambda b: f"{math.exp(b):.3f}" if b < 700 else "∞"
        out += self.table(["", "B", "Ralat Piawai", "Wald", "dk", "Sig.", "Exp(B)"],
                          [[name, f"{m['b'][a]:.3f}", f"{m['se'][a]:.3f}", f"{m['wald'][a]:.3f}", 1,
                            fp(p_chi2(m["wald"][a], 1)) if math.isfinite(m["wald"][a]) else "< .001", ex(m["b"][a])]
                           for a, name in enumerate(["(Pemalar)"] + ind)])
        pred = [int(p >= .5) for p in m["p"]]; cnt = Counter(zip(y, pred))
        pc = lambda a: f"{100*cnt[a, a]/(cnt[a, 0]+cnt[a, 1]):.1f}"
        out += ["", "Jadual Klasifikasi (titik potong 0.5)"] + self.table(["Sebenar \\ Ramalan", cats[0], cats[1], "% Betul"],
               [[cats[0], cnt[0, 0], cnt[0, 1], pc(0)], [cats[1], cnt[1, 0], cnt[1, 1], pc(1)],
                ["Keseluruhan", "", "", f"{100*(cnt[0, 0]+cnt[1, 1])/len(y):.1f}"]])
        out += ["Panduan: Exp(B) > 1 = peluang Y=1 meningkat bila X naik satu unit; Exp(B) < 1 = menurun."]
        self.write(f"Regresi Logistik: {dep} ~ {' + '.join(ind)}", out)

    def help(self):
        messagebox.showinfo("Cara Guna",
            "1. Masukkan data di 'Paparan Data' (dwiklik sel untuk edit) atau Fail > Buka CSV.\n"
            "2. Setiap lajur = satu pemboleh ubah, setiap baris = satu kes.\n"
            "3. Pilih ujian dari menu Analisis.\n"
            "4. Keputusan keluar di 'Paparan Output'. Fail > Simpan Output untuk simpan.\n\n"
            "Sig. < 0.05 biasanya bermaksud keputusan signifikan.")

def main():
    root = tk.Tk(); App(root); root.mainloop()

if __name__ == "__main__":
    main()
