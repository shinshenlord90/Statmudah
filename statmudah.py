#!/usr/bin/python3
"""StatMudah - aplikasi statistik ringkas (seperti PSPP) dengan rupa Windows 7."""
import base64, csv, html, json, math, os, statistics as st, tkinter as tk
from collections import Counter
from tkinter import ttk, filedialog, messagebox, simpledialog
from smstats import *
from i18n import EN

VERSION = "2.1"
CONF = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "statmudah", "settings.json")
SET = {"lang": "ms"}

def load_settings():
    try:
        with open(CONF, encoding="utf-8") as f: SET.update(json.load(f))
    except (OSError, ValueError): pass

def save_settings():
    try:
        os.makedirs(os.path.dirname(CONF), exist_ok=True)
        with open(CONF, "w", encoding="utf-8") as f: json.dump(SET, f)
    except OSError: pass  # tetapan bahasa tidak kritikal

def _(text, /, **kw):
    """Terjemah rentetan BM ke bahasa semasa, kemudian isi {nama}."""
    t = EN.get(text, text) if SET["lang"] == "en" else text
    return t.format(**kw) if kw else t

# ---------- format nombor gaya APA ----------
def fp(p): return "< .001" if p < .001 else ("1.000" if p >= .9995 else f"{p:.3f}"[1:])   # jadual
def pp(p): return "< .001" if p < .001 else "= " + fp(p)                                    # ayat
def f2(x): return f"{x:.2f}"
def nolead(x):  # APA: tiada sifar di depan bagi nilai yang tidak boleh melebihi 1 (r, p)
    s = f"{x:.2f}"; return s.replace("0.", ".", 1) if abs(x) < 1 else s
def fmtn(v): return str(int(v)) if float(v).is_integer() else f"{v:.4f}".rstrip("0").rstrip(".")
def sig(p, a, b): return _(a) if p < .05 else _(b)

# ---------- blok output (untuk Paparan Output dan eksport HTML) ----------
class Table:
    def __init__(self, head, rows): self.head, self.rows = [str(h) for h in head], [[str(x) for x in r] for r in rows]
    def ascii(self):
        w = [max(len(h), *(len(r[i]) for r in self.rows)) + 2 if self.rows else len(h) + 2 for i, h in enumerate(self.head)]
        line = "+" + "+".join("-" * x for x in w) + "+"
        fmt = lambda r: "|" + "|".join(v.rjust(w[i] - 1) + " " for i, v in enumerate(r)) + "|"
        return [line, fmt(self.head), line] + [fmt(r) for r in self.rows] + [line]
    def html(self):
        e = html.escape
        # lebar lajur eksplisit: tanpanya LibreOffice/Word membahagi lebar sama rata dan memotong perkataan
        w = [10 * max(len(h), *(len(r[i]) for r in self.rows)) + 30 if self.rows else 10 * len(h) + 30 for i, h in enumerate(self.head)]
        if sum(w) > 620: w = [x * 620 // sum(w) for x in w]  # muat dalam lebar halaman A4
        # border+frame+rules: garisan mendatar gaya APA yang juga difahami LibreOffice/Word (CSS border diabaikan di sana)
        return (f'<table class="apa" cellpadding="4" width="{sum(w)}" border="1" frame="hsides" rules="groups">' + "".join(f'<col width="{x}">' for x in w) + "<thead><tr>"
                + "".join(f"<th nowrap>{e(h)}</th>" for h in self.head) + "</tr></thead><tbody>"
                + "".join("<tr>" + "".join(f"<td nowrap>{e(v)}</td>" for v in r) + "</tr>" for r in self.rows) + "</tbody></table>")

class Apa(str): pass      # ayat laporan APA
class Plot(tuple): pass   # (operasi lukisan, lebar, tinggi)

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

# ---------- dialog ----------
class Dialog(tk.Toplevel):
    def __init__(self, root, title):
        super().__init__(root); self.title(title); self.configure(bg=BG); self.resizable(False, False)
        self.transient(root); self.result = None
    def buttons(self, **grid):
        bar = ttk.Frame(self); bar.grid(sticky="e", padx=8, pady=8, **grid)
        ttk.Button(bar, text="OK", command=self.ok).pack(side="left", padx=3)
        ttk.Button(bar, text=_("Batal"), command=self.destroy).pack(side="left", padx=3)
        self.bind("<Return>", lambda e: self.ok()); self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set(); self.wait_window()

class PickDialog(Dialog):
    """fields: senarai (label, pilih banyak?, angka sahaja?)."""
    def __init__(self, app, title, fields):
        super().__init__(app.root, title); self.boxes = []
        for i, (label, multi, numeric) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=0, column=i, sticky="w", padx=8, pady=(8, 2))
            lb = tk.Listbox(self, selectmode="extended" if multi else "browse", exportselection=False,
                            height=12, width=24, font=FONT, selectbackground=SEL, selectforeground="black")
            names = [c for c in app.cols if not numeric or app.numeric(c)]
            for n in names: lb.insert("end", n)
            lb.grid(row=1, column=i, padx=8); self.boxes.append((lb, names, multi))
        if any(m for _l, m, _n in fields):
            ttk.Label(self, text=_("Tip: Ctrl+klik atau Shift+klik untuk pilih banyak.")).grid(row=2, column=0, columnspan=len(fields), sticky="w", padx=8)
        self.buttons(row=3, column=0, columnspan=len(fields))
    def ok(self):
        out = []
        for lb, names, multi in self.boxes:
            sel = [names[i] for i in lb.curselection()]
            if not sel: return messagebox.showwarning(_("Pilih"), _("Sila pilih pemboleh ubah."), parent=self)
            out.append(sel if multi else sel[0])
        self.result = out; self.destroy()

class FormDialog(Dialog):
    """fields: ("entry", label, lalai) atau ("radio", label, [pilihan], indeks lalai). Hasil: senarai nilai."""
    def __init__(self, app, title, fields):
        super().__init__(app.root, title); self.vars = []
        for i, f in enumerate(fields):
            ttk.Label(self, text=f[1]).grid(row=i, column=0, sticky="nw", padx=8, pady=6)
            if f[0] == "entry":
                v = tk.StringVar(value=f[2]); e = ttk.Entry(self, textvariable=v, width=30); e.grid(row=i, column=1, padx=8, pady=6)
                if i == 0: e.focus()
            else:
                v = tk.IntVar(value=f[3]); fr = ttk.Frame(self); fr.grid(row=i, column=1, sticky="w", padx=8, pady=6)
                for j, o in enumerate(f[2]): ttk.Radiobutton(fr, text=o, variable=v, value=j).pack(anchor="w")
            self.vars.append(v)
        self.buttons(row=len(fields), column=0, columnspan=2)
    def ok(self): self.result = [v.get() for v in self.vars]; self.destroy()

class GroupDialog(Dialog):
    """Pilih tepat 2 kumpulan (seperti 'Define Groups' PSPP)."""
    def __init__(self, root, var, groups):
        super().__init__(root, _("Pilih 2 Kumpulan"))
        self.keys = sorted(groups, key=sortkey)
        ttk.Label(self, text=_("'{v}' ada {k} kumpulan.\nKlik 2 kumpulan untuk dibandingkan:", v=var, k=len(self.keys))).grid(row=0, sticky="w", padx=8, pady=(8, 2))
        self.lb = tk.Listbox(self, selectmode="multiple", exportselection=False, height=min(12, len(self.keys)), width=30,
                             font=FONT, selectbackground=SEL, selectforeground="black")
        for k in self.keys: self.lb.insert("end", _("{k}   ({n} kes)", k=k, n=len(groups[k])))
        self.lb.grid(row=1, padx=8)
        self.buttons(row=2, column=0)
    def ok(self):
        sel = self.lb.curselection()
        if len(sel) != 2: return messagebox.showwarning(_("Pilih"), _("Sila pilih tepat 2 kumpulan (dipilih: {n}).", n=len(sel)), parent=self)
        self.result = [self.keys[i] for i in sel]; self.destroy()

# ---------- plot: satu senarai operasi, dilukis ke Canvas dan ke SVG ----------
def plot_ops(title, xs, ys, xl, yl, ref, W=380, H=280):
    L, B = 50, 40
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if ref == "diag": x0 = y0 = min(x0, y0); x1 = y1 = max(x1, y1)
    if ref in ("zero", "scree"): y0, y1 = min(y0, 0), max(y1, 1 if ref == "scree" else 0)
    x1, y1 = (x1 if x1 > x0 else x0 + 1), (y1 if y1 > y0 else y0 + 1)
    px = lambda v: L + (v - x0) / (x1 - x0) * (W - L - 15); py = lambda v: H - B - (v - y0) / (y1 - y0) * (H - B - 30)
    ops = [("text", W / 2, 12, title, "center", 0, True), ("rect", L, 30, W - 15, H - B)]
    ops += [("text", px(v), H - B + 10, f"{v:.3g}", "center", 0, False) for v in (x0, x1)]
    ops += [("text", L - 4, py(v), f"{v:.3g}", "e", 0, False) for v in (y0, y1)]
    ops += [("text", W / 2, H - 10, xl, "center", 0, False), ("text", 12, H / 2 - B / 2, yl, "center", 90, False)]
    if ref == "scree":
        ops.append(("line", L, py(1), W - 15, py(1)))
        ops += [("seg", px(a), py(b), px(c), py(d)) for a, b, c, d in zip(xs, ys, xs[1:], ys[1:])]
    else: ops.append(("line", L, py(0), W - 15, py(0)) if ref == "zero" else ("line", px(x0), py(x0), px(x1), py(x1)))
    ops += [("dot", px(x), py(y)) for x, y in zip(xs, ys)]
    return Plot((ops, W, H))

def draw_canvas(c, ops):
    for o in ops:
        if o[0] == "text": c.create_text(o[1], o[2], text=o[3], anchor={"center": "center", "e": "e"}[o[4]], angle=o[5],
                                         font=("DejaVu Sans", 9, "bold") if o[6] else FONT, fill="#1E3A8A" if o[6] else "black")
        elif o[0] == "rect": c.create_rectangle(*o[1:], outline="#888")
        elif o[0] == "line": c.create_line(*o[1:], fill="#C0392B", dash=(4, 2))
        elif o[0] == "seg": c.create_line(*o[1:], fill="#3C7FB1", width=1.5)
        else: c.create_oval(o[1] - 3, o[2] - 3, o[1] + 3, o[2] + 3, fill="#3C7FB1", outline="#1E3A8A")

def svg(ops, W, H):
    e = html.escape; out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="DejaVu Sans, Arial" font-size="11"><rect width="{W}" height="{H}" fill="white"/>']
    for o in ops:
        if o[0] == "text":
            anc = {"center": "middle", "e": "end"}[o[4]]; rot = f' transform="rotate(-{o[5]} {o[1]:.1f} {o[2]:.1f})"' if o[5] else ""
            out.append(f'<text x="{o[1]:.1f}" y="{o[2] + 4:.1f}" text-anchor="{anc}"{rot}{" font-weight=\"bold\"" if o[6] else ""}>{e(o[3])}</text>')
        elif o[0] == "rect": out.append(f'<rect x="{o[1]}" y="{o[2]}" width="{o[3] - o[1]}" height="{o[4] - o[2]}" fill="none" stroke="#888"/>')
        elif o[0] == "line": out.append(f'<line x1="{o[1]:.1f}" y1="{o[2]:.1f}" x2="{o[3]:.1f}" y2="{o[4]:.1f}" stroke="#C0392B" stroke-dasharray="4 2"/>')
        elif o[0] == "seg": out.append(f'<line x1="{o[1]:.1f}" y1="{o[2]:.1f}" x2="{o[3]:.1f}" y2="{o[4]:.1f}" stroke="#3C7FB1" stroke-width="1.5"/>')
        else: out.append(f'<circle cx="{o[1]:.1f}" cy="{o[2]:.1f}" r="3" fill="#3C7FB1" stroke="#1E3A8A"/>')
    return "".join(out) + "</svg>"

HTML_HEAD = """<!doctype html><html><head><meta charset="utf-8"><title>StatMudah Output</title><style>
body{font-family:"Times New Roman",serif;font-size:12pt;color:#000;background:#fff}
@media screen{body{max-width:900px;margin:24px auto;padding:0 16px}}
h2{font-size:12pt;font-weight:bold;margin:28px 0 8px}
table.apa{border-collapse:collapse;margin:8px 0 12px}
table.apa th{border-top:1.5px solid #000;border-bottom:1px solid #000;font-weight:normal;text-align:center;white-space:nowrap;padding:0}
table.apa td{text-align:center;white-space:nowrap;padding:0}
table.apa tbody tr:last-child td{border-bottom:1.5px solid #000}
p.apa{background:#F3F7FB;border-left:3px solid #3C7FB1;padding:6px 10px}
</style></head><body>
"""

# ---------- aplikasi ----------
class App:
    missing = set()   # kod data hilang (cth. "99") - dianggap kosong dalam semua analisis

    def __init__(self, root):
        self.root, self.cols, self.rows, self.path, self.blocks = root, [], [], None, []
        root.title("StatMudah"); root.geometry("1000x650"); root.configure(bg=BG); style(root)
        self.menu(); self.tb = None; self.toolbar()
        self.status = ttk.Label(root, style="Status.TLabel"); self.status.pack(fill="x", side="bottom")
        self.nb = ttk.Notebook(root); self.nb.pack(fill="both", expand=True, padx=4, pady=2)
        f = ttk.Frame(self.nb); self.nb.add(f)
        self.tree = ttk.Treeview(f, show="headings", selectmode="browse")
        ys, xs = ttk.Scrollbar(f, command=self.tree.yview), ttk.Scrollbar(f, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y"); xs.pack(side="bottom", fill="x"); self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.edit_cell)
        o = ttk.Frame(self.nb); self.nb.add(o)
        self.out = tk.Text(o, font=("DejaVu Sans Mono", 10), wrap="none", bg="white", relief="flat")
        oy, ox = ttk.Scrollbar(o, command=self.out.yview), ttk.Scrollbar(o, orient="horizontal", command=self.out.xview)
        self.out.configure(yscrollcommand=oy.set, xscrollcommand=ox.set)
        oy.pack(side="right", fill="y"); ox.pack(side="bottom", fill="x"); self.out.pack(fill="both", expand=True)
        self.out.tag_configure("note", wrap="word")  # ayat panjang dibalut; jadual kekal tanpa balut
        self.out.tag_configure("h", font=("DejaVu Sans", 11, "bold"), foreground="#1E3A8A")
        self.out.tag_configure("apa", font=("DejaVu Sans", 10), foreground="#14532D", background="#ECFDF3", lmargin1=6, lmargin2=6, wrap="word")
        self.tabs(); self.new(sample=True)

    def tabs(self):
        self.nb.tab(0, text=_("  Paparan Data  ")); self.nb.tab(1, text=_("  Paparan Output  "))

    def menu(self):
        m = tk.Menu(self.root, bg=BG, font=FONT, relief="flat"); self.root.config(menu=m)
        mk = lambda parent: tk.Menu(parent, tearoff=0, bg="white", font=FONT, activebackground=SEL, activeforeground="black")
        def fill(menu, items):
            for it in items:
                if it is None: menu.add_separator()
                elif isinstance(it[1], list): s = mk(menu); fill(s, it[1]); menu.add_cascade(label=it[0], menu=s)
                else: menu.add_command(label=it[0], command=it[1], accelerator=it[2] if len(it) > 2 else "")
        def sub(name, items): s = mk(m); fill(s, items); m.add_cascade(label=name, menu=s)
        sub(_("Fail"), [(_("Baru"), self.new, "Ctrl+N"), (_("Buka CSV / Excel..."), self.open, "Ctrl+O"), (_("Simpan"), self.save, "Ctrl+S"),
                        (_("Simpan Sebagai..."), lambda: self.save(True)), None,
                        (_("Eksport Output ke HTML (untuk Word)..."), self.export_html), (_("Simpan Output sebagai Teks..."), self.save_output),
                        None, (_("Keluar"), self.root.quit)])
        sub(_("Edit"), [(_("Tambah Baris"), self.add_row), (_("Tambah Pemboleh Ubah"), self.add_col),
                        (_("Namakan Semula Pemboleh Ubah"), self.rename_col), None, (_("Padam Baris Dipilih"), self.del_row),
                        (_("Padam Pemboleh Ubah"), self.del_col), None, (_("Kosongkan Output"), self.clear_output)])
        sub(_("Data"), [(_("Songsangkan Item (Kod Semula)..."), self.reverse_items), (_("Kira Pemboleh Ubah (Skor Konstruk)..."), self.compute), None,
                        (_("Analisis Data Hilang..."), self.missing_report), (_("Kod Data Hilang..."), self.missing_codes), None,
                        (_("Cari Kes Berulang..."), self.duplicates), (_("Semak Julat Sah..."), self.range_check), None,
                        (_("Saringan Data (sebelum SEM)"), [(_("Outlier Univariat (|z| > 3.29)..."), self.outliers_z),
                                                            (_("Outlier Multivariat (Mahalanobis)..."), self.outliers_mahal),
                                                            (_("Ujian Satu Faktor Harman (CMB)..."), self.harman)])])
        sub(_("Analisis"), [(_("Statistik Deskriptif & Normaliti..."), self.descriptives), (_("Frekuensi..."), self.frequencies), None,
                            (_("Korelasi Pearson..."), self.correlation), (_("Korelasi Spearman..."), lambda: self.correlation(True)), None,
                            (_("Skala"), [(_("Kebolehpercayaan (Cronbach's Alpha)..."), self.reliability),
                                          (_("Analisis Faktor Penerokaan (EFA)..."), self.efa)]), None,
                            (_("Ujian-t Sampel Bebas..."), self.ttest), (_("Ujian-t Berpasangan..."), self.paired),
                            (_("ANOVA Sehala..."), self.anova), (_("ANOVA Dua Hala..."), self.anova2), (_("Khi Kuasa Dua..."), self.chisq), None,
                            (_("Ujian Bukan Parametrik"), [(_("Mann-Whitney U (2 kumpulan bebas)..."), self.mannwhitney),
                                                           (_("Wilcoxon (2 ukuran berpasangan)..."), self.wilcoxon),
                                                           (_("Kruskal-Wallis (≥3 kumpulan)..."), self.kruskal)]), None,
                            (_("Regresi Linear..."), self.regression), (_("Regresi Logistik (Binari)..."), self.logistic)])
        sub(_("Bantuan"), [(_("Cara Guna"), self.help), (_("Bahasa / Language"), [("Bahasa Melayu", lambda: self.set_lang("ms")), ("English", lambda: self.set_lang("en"))]),
                           (_("Perihal"), lambda: messagebox.showinfo(_("Perihal"), _("StatMudah {v}\nAnalisis statistik mudah.", v=VERSION)))])
        for k, f in (("n", self.new), ("o", self.open), ("s", self.save)): self.root.bind(f"<Control-{k}>", lambda e, f=f: f())

    def toolbar(self):
        if self.tb: self.tb.destroy()
        self.tb = tb = ttk.Frame(self.root, style="Tool.TFrame")
        tb.pack(fill="x", **({"before": self.nb} if hasattr(self, "nb") else {}))
        for t, c in ((_("📄 Baru"), self.new), (_("📂 Buka"), self.open), (_("💾 Simpan"), self.save), ("|", 0),
                     (_("➕ Baris"), self.add_row), (_("➕ Pemboleh Ubah"), self.add_col), ("|", 0),
                     (_("Σ Deskriptif"), self.descriptives), (_("📊 Frekuensi"), self.frequencies), (_("t Ujian-t"), self.ttest),
                     (_("📝 Eksport"), self.export_html), (_("❓ Bantuan"), self.help)):
            if t == "|": ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=4, pady=3)
            else: ttk.Button(tb, text=t, style="Tool.TButton", width=0, command=c).pack(side="left", padx=1, pady=2)

    def set_lang(self, lang):
        SET["lang"] = lang; save_settings(); self.menu(); self.toolbar(); self.tabs(); self.refresh()

    # ----- data -----
    def refresh(self):
        self.tree.delete(*self.tree.get_children()); self.tree["columns"] = ["#"] + self.cols
        self.tree.heading("#", text="#"); self.tree.column("#", width=45, anchor="e", stretch=False)
        for c in self.cols: self.tree.heading(c, text=c); self.tree.column(c, width=90, anchor="e")
        for i, r in enumerate(self.rows): self.tree.insert("", "end", iid=str(i), values=[i + 1] + r)
        codes = _("   |   Kod hilang: {c}", c=", ".join(sorted(App.missing))) if App.missing else ""
        self.status["text"] = _("  {p}   |   {n} kes   |   {k} pemboleh ubah{c}   |   Dwiklik sel untuk edit",
                                p=self.path or _("Tanpa nama"), n=len(self.rows), k=len(self.cols), c=codes)

    def new(self, sample=False):
        self.path = None
        if sample:  # data contoh supaya pengguna baru boleh terus cuba
            self.cols = ["jantina", "umur", "markah_ujian1", "markah_ujian2"]
            self.rows = [[g, str(a), str(m1), str(m2)] for g, a, m1, m2 in [
                ("L", 21, 65, 70), ("P", 22, 78, 80), ("L", 20, 55, 61), ("P", 23, 88, 85), ("L", 24, 72, 75),
                ("P", 21, 81, 86), ("L", 22, 60, 66), ("P", 20, 92, 90), ("L", 23, 68, 72), ("P", 22, 75, 79)]]
        else: self.cols, self.rows = ["var1", "var2"], [["", ""] for _i in range(5)]
        self.refresh()

    def open(self):
        p = filedialog.askopenfilename(filetypes=[(_("Data (CSV, Excel)"), "*.csv *.xlsx"), ("CSV", "*.csv"), ("Excel", "*.xlsx"), (_("Semua"), "*")])
        if not p: return
        try:
            if p.lower().endswith(".xlsx"): data = read_xlsx(p)
            else:
                with open(p, newline="", encoding="utf-8-sig") as f: data = list(csv.reader(f))
        except Exception as e:  # fail rosak/tidak disokong: beritahu pengguna, jangan tutup aplikasi
            return messagebox.showerror(_("Ralat"), _("Fail tidak dapat dibaca:\n{e}", e=e))
        data = [r for r in data if any(c.strip() for c in r)]
        if not data: return messagebox.showerror(_("Ralat"), _("Fail kosong."))
        self.cols = [c.strip() or f"var{i+1}" for i, c in enumerate(data[0])]
        self.rows = [[c.strip() for c in (r + [""] * len(self.cols))[:len(self.cols)]] for r in data[1:]]
        self.path = p; self.refresh()

    def save(self, as_new=False):
        if as_new or not self.path or self.path.lower().endswith(".xlsx"):  # .xlsx tidak ditulis semula; simpan sebagai CSV
            p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not p: return
            self.path = p
        try:
            with open(self.path, "w", newline="", encoding="utf-8") as f: csv.writer(f).writerows([self.cols] + self.rows)
        except OSError as e: return messagebox.showerror(_("Ralat"), str(e))
        self.refresh()

    def save_output(self):
        p = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[(_("Teks"), "*.txt")])
        if p:
            with open(p, "w", encoding="utf-8") as f: f.write(self.out.get("1.0", "end"))

    def export_html(self):
        if not self.blocks: return messagebox.showinfo(_("Eksport"), _("Tiada output untuk dieksport. Jalankan analisis dahulu."))
        p = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML", "*.html")])
        if not p: return
        body = []
        for b in self.blocks:
            if isinstance(b, tuple) and b[0] == "h": body.append(f"<h2>{html.escape(b[1])}</h2>")
            elif isinstance(b, Table): body.append(b.html())
            elif isinstance(b, Apa): body.append(f'<p class="apa">{html.escape(b)}</p>')
            elif isinstance(b, Plot):
                data = base64.b64encode(svg(*b).encode()).decode()
                body.append(f'<img src="data:image/svg+xml;base64,{data}" width="{b[1]}" height="{b[2]}" alt="plot"> ')
            elif b: body.append(f"<p>{html.escape(b)}</p>")
        try:
            with open(p, "w", encoding="utf-8") as f: f.write(HTML_HEAD + "\n".join(body) + "\n</body></html>\n")
        except OSError as e: return messagebox.showerror(_("Ralat"), str(e))
        messagebox.showinfo(_("Eksport"), _("Output disimpan:\n{p}\n\nBuka dalam pelayar atau LibreOffice/Word, kemudian salin jadual ke tesis.", p=p))

    def clear_output(self): self.out.delete("1.0", "end"); self.blocks = []

    def edit_cell(self, e):
        row, col = self.tree.identify_row(e.y), self.tree.identify_column(e.x)
        ci = int(col[1:]) - 2
        if not row or ci < 0: return
        x, y, w, h = self.tree.bbox(row, col)
        ent = ttk.Entry(self.tree); ent.insert(0, self.rows[int(row)][ci]); ent.select_range(0, "end")
        ent.place(x=x, y=y, width=w, height=h); ent.focus()
        def done(ev=None):
            self.rows[int(row)][ci] = ent.get().strip(); ent.destroy()
            self.tree.item(row, values=[int(row) + 1] + self.rows[int(row)])
        ent.bind("<Return>", done); ent.bind("<FocusOut>", done); ent.bind("<Escape>", lambda ev: ent.destroy())

    def add_row(self): self.rows.append([""] * len(self.cols)); self.refresh(); self.tree.see(str(len(self.rows) - 1))
    def add_col(self):
        n = simpledialog.askstring(_("Pemboleh Ubah Baru"), _("Nama pemboleh ubah:"), parent=self.root)
        if n and n not in self.cols: self.cols.append(n); [r.append("") for r in self.rows]; self.refresh()
    def rename_col(self):
        if not self.cols: return
        r = PickDialog(self, _("Namakan Semula"), [(_("Pemboleh ubah:"), False, False)]).result
        if not r: return
        new = simpledialog.askstring(_("Namakan Semula"), _("Nama baru:"), parent=self.root, initialvalue=r[0])
        if new and new not in self.cols: self.cols[self.cols.index(r[0])] = new; self.refresh()
    def del_row(self):
        s = self.tree.selection()
        if s and messagebox.askyesno(_("Padam"), _("Padam baris dipilih?")): del self.rows[int(s[0])]; self.refresh()
    def del_col(self):
        r = PickDialog(self, _("Padam Pemboleh Ubah"), [(_("Pemboleh ubah:"), True, False)]).result
        if r and messagebox.askyesno(_("Padam"), _("Padam {v}?", v=", ".join(r[0]))):
            keep = [i for i, c in enumerate(self.cols) if c not in r[0]]
            self.cols = [self.cols[i] for i in keep]; self.rows = [[x[i] for i in keep] for x in self.rows]; self.refresh()

    # ----- helper analisis -----
    @staticmethod
    def blank(v): return v.strip() == "" or v.strip() in App.missing
    @staticmethod
    def num(v):
        if App.blank(v): return None
        try: return float(v.replace(",", "."))
        except ValueError: return None
    def values(self, c):
        i = self.cols.index(c); return [v for v in (self.num(r[i]) for r in self.rows) if v is not None]
    def numeric(self, c): return len(self.values(c)) > 0
    def pairs(self, a, b):
        i, j = self.cols.index(a), self.cols.index(b)
        return [(x, y) for x, y in ((self.num(r[i]), self.num(r[j])) for r in self.rows) if x is not None and y is not None]
    def groups(self, dep, grp):
        i, j = self.cols.index(dep), self.cols.index(grp); g = {}
        for row in self.rows:
            v = self.num(row[i])
            if v is not None and not self.blank(row[j]): g.setdefault(row[j].strip(), []).append(v)
        return dict(sorted(g.items(), key=lambda kv: sortkey(kv[0])))
    def two_groups(self, title, dep, grp):
        """Kumpulan untuk ujian 2 kumpulan; minta pengguna pilih jika ada > 2. None jika batal/tidak sah."""
        g = self.groups(dep, grp)
        if len(g) < 2:
            messagebox.showwarning(title, _("Pemboleh ubah kumpulan perlu sekurang-kurangnya 2 kumpulan (ada {n}: {v}).", n=len(g), v=", ".join(g) or "-")); return None
        if len(g) > 2:
            pick = GroupDialog(self.root, grp, g).result
            if not pick: return None
            g = {k: g[k] for k in pick}
        return g
    def case_id(self, i): return _("baris {n}", n=i + 1) + (f" ({self.cols[0]}={self.rows[i][0]})" if self.cols else "")

    def complete(self, cols):
        """Kes lengkap (listwise) bagi lajur angka: (indeks baris, nilai)."""
        idx = [self.cols.index(c) for c in cols]; ids, rows = [], []
        for k, row in enumerate(self.rows):
            v = [self.num(row[i]) for i in idx]
            if None not in v: ids.append(k); rows.append(v)
        return ids, rows

    def table(self, head, rows): return [Table(head, rows)]
    def apa(self, s): return [Apa(_("Laporan APA (salin & sunting): ") + s)]

    def write(self, title, items):
        self.blocks.append(("h", title)); self.out.insert("end", title + "\n", "h")
        for it in items:
            self.blocks.append(it)
            if isinstance(it, Table): self.out.insert("end", "\n".join(it.ascii()) + "\n")
            elif isinstance(it, Apa): self.out.insert("end", it + "\n", "apa")
            elif isinstance(it, Plot):
                c = tk.Canvas(self.out, width=it[1], height=it[2], bg="white", highlightthickness=1, highlightbackground=BORDER)
                draw_canvas(c, it[0]); self.out.window_create("end", window=c, padx=4, pady=4)
            else: self.out.insert("end", it + "\n", "note")
        self.out.insert("end", "\n"); self.out.see("end"); self.nb.select(1)

    # ----- menu Data -----
    def reverse_items(self):
        r = PickDialog(self, _("Songsangkan Item"), [(_("Item untuk disongsangkan:"), True, True)]).result
        if not r: return
        vals = [v for c in r[0] for v in self.values(c)]
        f = FormDialog(self, _("Songsangkan Item"), [("entry", _("Nilai minimum skala:"), fmtn(min(vals))), ("entry", _("Nilai maksimum skala:"), fmtn(max(vals)))]).result
        if not f: return
        lo, hi = self.num(f[0]), self.num(f[1])
        if lo is None or hi is None or lo >= hi: return messagebox.showwarning(_("Songsangkan Item"), _("Minimum dan maksimum mesti nombor, dan minimum < maksimum."))
        made, skipped, bad = [], [], 0
        for c in r[0]:
            new = c + "_r"
            if new in self.cols: skipped.append(new); continue
            i = self.cols.index(c); self.cols.append(new)
            for row in self.rows:
                v = self.num(row[i])
                if v is not None and lo <= v <= hi: row.append(fmtn(lo + hi - v))
                else: row.append(""); bad += v is not None  # nilai luar julat tidak disongsangkan
            made.append(new)
        self.refresh()
        out = [_("Formula: baru = {s} − lama. Item asal tidak diubah.", s=fmtn(lo + hi)), _("Pemboleh ubah baru: {v}", v=", ".join(made) or "-")]
        if skipped: out.append(_("Sudah wujud (tidak ditulis semula): {v}", v=", ".join(skipped)))
        if bad: out.append(_("AMARAN: {n} nilai di luar julat {lo}–{hi} dibiarkan kosong. Semak dengan Data > Semak Julat Sah.", n=bad, lo=fmtn(lo), hi=fmtn(hi)))
        self.write(_("Songsangkan Item"), out)

    def compute(self):
        r = PickDialog(self, _("Kira Pemboleh Ubah"), [(_("Item:"), True, True)]).result
        if not r: return
        f = FormDialog(self, _("Kira Pemboleh Ubah"), [("entry", _("Nama pemboleh ubah baru:"), ""), ("radio", _("Kaedah:"), [_("Min item"), _("Jumlah item")], 0)]).result
        if not f: return
        name = f[0].strip()
        if not name or name in self.cols: return messagebox.showwarning(_("Kira Pemboleh Ubah"), _("Nama kosong atau sudah wujud."))
        idx = [self.cols.index(c) for c in r[0]]; self.cols.append(name); blanks = 0
        for row in self.rows:
            v = [self.num(row[i]) for i in idx]
            if None in v: row.append(""); blanks += 1   # ada item hilang: skor dibiarkan kosong
            else: row.append(fmtn(sum(v) / len(v) if f[1] == 0 else sum(v)))
        self.refresh()
        self.write(_("Kira Pemboleh Ubah"), [_("{n} = {m} ({v})", n=name, m=_("min") if f[1] == 0 else _("jumlah"), v=", ".join(r[0])),
                                            _("{k} kes dibiarkan kosong kerana ada item yang hilang.", k=blanks)])

    def missing_report(self):
        r = PickDialog(self, _("Analisis Data Hilang"), [(_("Pemboleh ubah:"), True, False)]).result
        if not r: return
        idx = [self.cols.index(c) for c in r[0]]; n = len(self.rows)
        rows = [[c, n - sum(self.blank(x[i]) for x in self.rows), sum(self.blank(x[i]) for x in self.rows),
                 f"{100 * sum(self.blank(x[i]) for x in self.rows) / n:.1f}" if n else "-"] for c, i in zip(r[0], idx)]
        bad = [k for k, row in enumerate(self.rows) if any(self.blank(row[i]) for i in idx)]
        out = self.table([_("Pemboleh ubah"), _("N sah"), _("Hilang"), _("% Hilang")], rows)
        out.append(_("Kes dengan sekurang-kurangnya satu nilai hilang: {k} daripada {n} ({p}%). Kes lengkap: {c}.",
                     k=len(bad), n=n, p=f"{100 * len(bad) / n:.1f}" if n else "0", c=n - len(bad)))
        if bad: out.append(_("Kes terlibat: ") + "; ".join(self.case_id(k) for k in bad[:50]) + (" ..." if len(bad) > 50 else ""))
        self.write(_("Analisis Data Hilang"), out)
        if not bad: return
        f = FormDialog(self, _("Tindakan Data Hilang"), [("radio", _("Tindakan:"), [_("Tiada (laporan sahaja)"), _("Buang kes yang ada nilai hilang (listwise)"),
                                                                                   _("Ganti nilai hilang dengan min pemboleh ubah")], 0)]).result
        if not f or f[0] == 0: return
        if not messagebox.askyesno(_("Sahkan"), _("Tindakan ini mengubah data. Selepas ini, simpan dengan Fail > Simpan Sebagai (nama baru) supaya data asal kekal. Teruskan?")): return
        if f[0] == 1:
            self.rows = [row for k, row in enumerate(self.rows) if k not in set(bad)]
            log = [_("{k} kes dibuang. N sekarang = {n}.", k=len(bad), n=len(self.rows))]
        else:
            log = []
            for c, i in zip(r[0], idx):
                v = self.values(c)
                if not v: log.append(_("{c}: bukan nombor, tidak diganti.", c=c)); continue
                m = st.mean(v); k = 0
                for row in self.rows:
                    if self.blank(row[i]): row[i] = fmtn(round(m, 4)); k += 1
                if k: log.append(_("{c}: {k} nilai diganti dengan min {m}.", c=c, k=k, m=fmtn(round(m, 4))))
        self.refresh(); self.write(_("Tindakan Data Hilang"), log)

    def missing_codes(self):
        f = FormDialog(self, _("Kod Data Hilang"), [("entry", _("Kod yang dianggap hilang (pisah dengan koma), cth. 99, -1:"), ", ".join(sorted(App.missing)))]).result
        if f is None: return
        App.missing = {c.strip() for c in f[0].split(",") if c.strip()}; self.refresh()
        self.write(_("Kod Data Hilang"), [_("Nilai berikut dianggap hilang dalam semua analisis: {c}", c=", ".join(sorted(App.missing)) or "-"),
                                         _("Nota: kod ini tidak disimpan dalam fail CSV; tetapkan semula selepas membuka fail.")])

    def duplicates(self):
        r = PickDialog(self, _("Cari Kes Berulang"), [(_("Pemboleh ubah ID:"), False, False)]).result
        if not r: return
        i = self.cols.index(r[0]); ids, same = {}, {}
        for k, row in enumerate(self.rows):
            if not self.blank(row[i]): ids.setdefault(row[i].strip(), []).append(k + 1)
            same.setdefault(tuple(v.strip() for j, v in enumerate(row) if j != i), []).append(k + 1)
        d1 = [[key, len(v), ", ".join(map(str, v))] for key, v in ids.items() if len(v) > 1]
        d2 = [[len(v), ", ".join(map(str, v))] for v in same.values() if len(v) > 1]
        out = [_("ID berulang:")] + (self.table([r[0], _("Bilangan"), _("Baris")], d1) if d1 else [_("Tiada.")])
        out += ["", _("Kes yang sama sepenuhnya (selain ID):")] + (self.table([_("Bilangan"), _("Baris")], d2) if d2 else [_("Tiada.")])
        if d1 or d2: out.append(_("Semak baris ini di Paparan Data; padam yang berulang dengan Edit > Padam Baris Dipilih."))
        self.write(_("Cari Kes Berulang"), out)

    def range_check(self):
        r = PickDialog(self, _("Semak Julat Sah"), [(_("Pemboleh ubah:"), True, False)]).result
        if not r: return
        f = FormDialog(self, _("Semak Julat Sah"), [("entry", _("Nilai minimum sah:"), "1"), ("entry", _("Nilai maksimum sah:"), "5")]).result
        if not f: return
        lo, hi = self.num(f[0]), self.num(f[1])
        if lo is None or hi is None or lo > hi: return messagebox.showwarning(_("Semak Julat Sah"), _("Minimum dan maksimum mesti nombor, dan minimum ≤ maksimum."))
        rows = []
        for k, row in enumerate(self.rows):
            for c in r[0]:
                v = row[self.cols.index(c)]
                if self.blank(v): continue
                n = self.num(v)
                if n is None: rows.append([k + 1, row[0], c, v, _("bukan nombor")])
                elif not lo <= n <= hi: rows.append([k + 1, row[0], c, v, _("di luar julat")])
        out = [_("Julat sah: {lo} hingga {hi}. Nilai kosong dan kod hilang tidak disemak.", lo=fmtn(lo), hi=fmtn(hi))]
        out += self.table([_("Baris"), self.cols[0], _("Pemboleh ubah"), _("Nilai"), _("Masalah")], rows) if rows else [_("Tiada masalah ditemui.")]
        if rows: out.append(_("Betulkan nilai ini di Paparan Data (dwiklik sel), atau tetapkan sebagai kod hilang."))
        self.write(_("Semak Julat Sah"), out)

    # ----- analisis -----
    def descriptives(self):
        r = PickDialog(self, _("Statistik Deskriptif & Normaliti"), [(_("Pemboleh ubah (angka):"), True, True)]).result
        if not r: return
        rows, norm = [], []
        for c in r[0]:
            v = self.values(c); sd = st.stdev(v) if len(v) > 1 else 0
            rows.append([c, len(v), f"{st.mean(v):.3f}", f"{st.median(v):.3f}", f"{sd:.3f}", fmtn(min(v)), fmtn(max(v))])
            sk, sw = skew_kurt(v), shapiro(v)
            norm.append([c] + ([f"{sk[0]:.3f}", f"{sk[1]:.3f}", f"{sk[0]/sk[1]:.2f}", f"{sk[2]:.3f}", f"{sk[3]:.3f}", f"{sk[2]/sk[3]:.2f}"] if sk else ["-"] * 6)
                        + ([f"{sw[0]:.3f}", fp(sw[1])] if sw else ["-", "-"]))
        out = self.table([_("Pemboleh ubah"), "N", _("Min"), _("Median"), _("SP"), _("Minimum"), _("Maksimum")], rows)
        out += ["", _("Normaliti")] + self.table([_("Pemboleh ubah"), _("Kepencongan"), _("RP"), "z", _("Kurtosis"), _("RP"), "z", "Shapiro-Wilk W", "Sig."], norm)
        out.append(_("Panduan: |z| > 1.96 (n < 50) atau > 3.29 (n 50–300) menunjukkan taburan tidak normal; untuk n > 300 lihat nilai kepencongan (|2|) dan kurtosis (|7|). Shapiro-Wilk Sig. < .05 = tidak normal."))
        self.write(_("Statistik Deskriptif & Normaliti"), out)

    def frequencies(self):
        r = PickDialog(self, _("Frekuensi"), [(_("Pemboleh ubah:"), True, False)]).result
        if not r: return
        for c in r[0]:
            i = self.cols.index(c); cnt = Counter(x[i].strip() for x in self.rows if not self.blank(x[i])); n = sum(cnt.values()); cum = 0; rows = []
            for k, f in sorted(cnt.items(), key=lambda kv: sortkey(kv[0])):
                cum += f; rows.append([k, f, f"{100*f/n:.1f}", f"{100*cum/n:.1f}"])
            rows.append([_("Jumlah"), n, "100.0", ""])
            out = self.table([_("Nilai"), _("Frekuensi"), _("Peratus Sah"), _("Peratus Kumulatif")], rows)
            miss = len(self.rows) - n
            if miss: out.append(_("Hilang: {m} kes (tidak dikira dalam peratus sah).", m=miss))
            self.write(_("Frekuensi: {c}", c=c), out)

    def correlation(self, spearman=False):
        name = _("Korelasi Spearman") if spearman else _("Korelasi Pearson")
        r = PickDialog(self, name, [(_("Pemboleh ubah (pilih ≥2):"), True, True)]).result
        if not r: return
        vs = r[0]
        if len(vs) < 2: return messagebox.showwarning(name, _("Pilih sekurang-kurangnya 2 pemboleh ubah."))
        rows, sent = [], []; sym = "rs" if spearman else "r"
        for a in range(len(vs)):
            for b in range(a + 1, len(vs)):
                p = self.pairs(vs[a], vs[b]); n = len(p)
                if n < 3: rows.append([vs[a], vs[b], n, "-", "-"]); continue
                xs, ys = [x for x, _y in p], [y for _x, y in p]
                if spearman: xs, ys = ranks(xs), ranks(ys)  # Spearman = Pearson atas pangkat
                try: rr = st.correlation(xs, ys)
                except st.StatisticsError: rows.append([vs[a], vs[b], n, "-", "-"]); continue
                t = rr * math.sqrt((n - 2) / max(1e-15, 1 - rr * rr)); p = p_t(t, n - 2)
                rows.append([vs[a], vs[b], n, f"{rr:.3f}", fp(p)])
                sent.append(_("Terdapat korelasi {dir} {res} antara {a} dan {b}, {s}({df}) = {r}, p {p}.", dir=_("positif") if rr > 0 else _("negatif"),
                              res=sig(p, "yang signifikan", "yang tidak signifikan"), a=vs[a], b=vs[b], s=sym, df=n - 2, r=nolead(rr), p=pp(p)))
        out = self.table([_("Pemboleh ubah 1"), _("Pemboleh ubah 2"), "N", "rho" if spearman else "r", _("Sig. (2-hujung)")], rows)
        self.write(name, out + (self.apa(" ".join(sent)) if sent else []))

    def ttest(self):
        title = _("Ujian-t Sampel Bebas")
        r = PickDialog(self, title, [(_("Pemboleh ubah ujian:"), False, True), (_("Pemboleh ubah kumpulan:"), False, False)]).result
        if not r: return
        g = self.two_groups(title, *r)
        if not g: return
        (k1, a), (k2, b) = g.items()
        if len(a) < 2 or len(b) < 2: return messagebox.showwarning(title, _("Setiap kumpulan perlu sekurang-kurangnya 2 nilai."))
        m1, m2, v1, v2, n1, n2 = st.mean(a), st.mean(b), st.variance(a), st.variance(b), len(a), len(b)
        out = self.table([_("Kumpulan"), "N", _("Min"), _("SP")], [[k1, n1, f"{m1:.3f}", f"{v1**.5:.3f}"], [k2, n2, f"{m2:.3f}", f"{v2**.5:.3f}"]])
        sp = ((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2); se = math.sqrt(sp * (1 / n1 + 1 / n2)); se_w = math.sqrt(v1 / n1 + v2 / n2)
        if se == 0 or se_w == 0: return messagebox.showwarning(title, _("Varians sifar; ujian tidak boleh dikira."))
        t1, df1 = (m1 - m2) / se, n1 + n2 - 2
        df2 = se_w**4 / ((v1 / n1)**2 / (n1 - 1) + (v2 / n2)**2 / (n2 - 1)); t2 = (m1 - m2) / se_w
        d = cohen_d(a, b); L = levene([a, b]); lp = p_f(*L[:3]) if L else 1.0
        out += ["", _("Ujian Levene Kesamaan Varians")] + self.table(["F", _("dk") + "1", _("dk") + "2", "Sig."], [[f"{L[0]:.3f}", L[1], L[2], fp(lp)]] if L else [["-"] * 4])
        out += self.table(["", "t", _("dk"), _("Sig. (2-hujung)"), _("Beza Min"), "Cohen's d"],
                          [[_("Varians sama"), f"{t1:.3f}", df1, fp(p_t(t1, df1)), f"{m1-m2:.3f}", f"{d:.3f}"],
                           [_("Varians tak sama (Welch)"), f"{t2:.3f}", f"{df2:.2f}", fp(p_t(t2, df2)), f"{m1-m2:.3f}", ""]])
        out.append(_("Panduan: Sig. Levene ≥ .05 → baca baris 'Varians sama'; < .05 → baca baris 'Welch'. Cohen's d: 0.2 kecil, 0.5 sederhana, 0.8 besar."))
        t, df = (t1, str(df1)) if lp >= .05 else (t2, f"{df2:.2f}"); p = p_t(t, float(df))
        out += self.apa(_("Ujian-t sampel bebas menunjukkan {res} dalam {dv} antara {g1} (M = {m1}, SP = {s1}) dan {g2} (M = {m2}, SP = {s2}), t({df}) = {t}, p {p}, d = {d}.",
                          res=sig(p, "perbezaan yang signifikan", "perbezaan yang tidak signifikan"), dv=r[0], g1=k1, m1=f2(m1), s1=f2(v1**.5),
                          g2=k2, m2=f2(m2), s2=f2(v2**.5), df=df, t=f2(t), p=pp(p), d=f2(abs(d))))
        self.write(_("{t}: {a} mengikut {b}", t=title, a=r[0], b=r[1]), out)

    def paired(self):
        title = _("Ujian-t Berpasangan")
        r = PickDialog(self, title, [(_("Pemboleh ubah 1:"), False, True), (_("Pemboleh ubah 2:"), False, True)]).result
        if not r: return
        pr = self.pairs(*r); d = [x - y for x, y in pr]; n = len(d)
        if n < 2 or st.stdev(d) == 0: return messagebox.showwarning(title, _("Data tidak mencukupi atau perbezaan sentiasa sama."))
        x, y = [p[0] for p in pr], [p[1] for p in pr]
        t = st.mean(d) / (st.stdev(d) / math.sqrt(n)); p = p_t(t, n - 1); dz = st.mean(d) / st.stdev(d)
        out = self.table([_("Pemboleh ubah"), "N", _("Min"), _("SP")], [[r[0], n, f"{st.mean(x):.3f}", f"{st.stdev(x):.3f}"], [r[1], n, f"{st.mean(y):.3f}", f"{st.stdev(y):.3f}"]])
        out += self.table(["N", _("Beza Min"), _("SP Beza"), "t", _("dk"), _("Sig. (2-hujung)"), "Cohen's dz"],
                          [[n, f"{st.mean(d):.3f}", f"{st.stdev(d):.3f}", f"{t:.3f}", n - 1, fp(p), f"{dz:.3f}"]])
        out += self.apa(_("Ujian-t sampel berpasangan menunjukkan {res} antara {v1} (M = {m1}, SP = {s1}) dan {v2} (M = {m2}, SP = {s2}), t({df}) = {t}, p {p}, d = {d}.",
                          res=sig(p, "perbezaan yang signifikan", "perbezaan yang tidak signifikan"), v1=r[0], m1=f2(st.mean(x)), s1=f2(st.stdev(x)),
                          v2=r[1], m2=f2(st.mean(y)), s2=f2(st.stdev(y)), df=n - 1, t=f2(t), p=pp(p), d=f2(abs(dz))))
        self.write(_("{t}: {a} - {b}", t=title, a=r[0], b=r[1]), out)

    def anova(self):
        title = _("ANOVA Sehala")
        r = PickDialog(self, title, [(_("Pemboleh ubah bersandar:"), False, True), (_("Faktor (kumpulan):"), False, False)]).result
        if not r: return
        g = self.groups(*r); keys, gl = list(g), list(g.values())
        res = anova1(gl)
        if res is None: return messagebox.showwarning(title, _("Perlu ≥2 kumpulan, data mencukupi, dan varians dalam kumpulan bukan sifar."))
        f, d1, d2, ssb, ssw = res; p = p_f(f, d1, d2); eta = ssb / (ssb + ssw)
        out = self.table([_("Kumpulan"), "N", _("Min"), _("SP")], [[kk, len(x), f"{st.mean(x):.3f}", f"{st.stdev(x):.3f}" if len(x) > 1 else "-"] for kk, x in g.items()])
        L = levene(gl)
        out += ["", _("Ujian Levene Kesamaan Varians")] + self.table(["F", _("dk") + "1", _("dk") + "2", "Sig."], [[f"{L[0]:.3f}", L[1], L[2], fp(p_f(*L[:3]))]] if L else [["-"] * 4])
        out += self.table([_("Sumber"), _("JK"), _("dk"), _("MK"), "F", "Sig.", "η²"],
                   [[_("Antara kumpulan"), f"{ssb:.3f}", d1, f"{ssb/d1:.3f}", f"{f:.3f}", fp(p), f"{eta:.3f}"],
                    [_("Dalam kumpulan"), f"{ssw:.3f}", d2, f"{ssw/d2:.3f}", "", "", ""], [_("Jumlah"), f"{ssb+ssw:.3f}", d1 + d2, "", "", "", ""]])
        out.append(_("Panduan η²: .01 kecil, .06 sederhana, .14 besar."))
        if len(g) >= 3:
            out += ["", _("Ujian Post-hoc Tukey HSD")] + self.table(["(I)", "(J)", _("Beza Min (I-J)"), _("Ralat Piawai"), "Sig.", _("SK 95% Bawah"), _("SK 95% Atas")],
                   [[keys[i], keys[j], f"{dd:.3f}" + ("*" if pv < .05 else ""), f"{se:.3f}", fp(pv), f"{lo:.3f}", f"{hi:.3f}"]
                    for i, j, dd, se, pv, lo, hi in tukey(gl)])
            out.append(_("* Beza min signifikan pada aras .05."))
        out += self.apa(_("ANOVA sehala menunjukkan kesan {iv} {res} terhadap {dv}, F({d1}, {d2}) = {f}, p {p}, η² = {e}.",
                          iv=r[1], res=sig(p, "yang signifikan", "yang tidak signifikan"), dv=r[0], d1=d1, d2=d2, f=f2(f), p=pp(p), e=nolead(eta)))
        self.write(_("{t}: {a} mengikut {b}", t=title, a=r[0], b=r[1]), out)

    def anova2(self):
        title = _("ANOVA Dua Hala")
        r = PickDialog(self, title, [(_("Pemboleh ubah bersandar:"), False, True), (_("Faktor A:"), False, False), (_("Faktor B:"), False, False)]).result
        if not r: return
        dep, fa, fb = r
        if fa == fb: return messagebox.showwarning(title, _("Faktor A dan B mesti berbeza."))
        i, ja, jb = (self.cols.index(c) for c in r); data = []
        for row in self.rows:
            v = self.num(row[i])
            if v is not None and not self.blank(row[ja]) and not self.blank(row[jb]): data.append((v, row[ja].strip(), row[jb].strip()))
        m = anova2(*zip(*data)) if data else None
        if m is None: return messagebox.showwarning(title, _("Tidak boleh dikira: setiap faktor perlu ≥2 aras, setiap gabungan A×B perlu ada data, dan data mesti mencukupi."))
        cells = {}
        for v, a, b in data: cells.setdefault((a, b), []).append(v)
        out = [_("Min (N) setiap sel")] + self.table([f"{fa} \\ {fb}"] + m["lb"],
              [[a] + [f"{st.mean(cells[a, b]):.3f} ({len(cells[a, b])})" for b in m["lb"]] for a in m["la"]])
        L = levene(list(cells.values()))
        out += ["", _("Ujian Levene Kesamaan Varians (semua sel)")] + self.table(["F", _("dk") + "1", _("dk") + "2", "Sig."], [[f"{L[0]:.3f}", L[1], L[2], fp(p_f(*L[:3]))]] if L else [["-"] * 4])
        mse = m["sse"] / m["dfe"]; rows, sent = [], []
        for key, label in (("A", fa), ("B", fb), ("AB", f"{fa} × {fb}")):
            ss, df = m["terms"][key]; f = (ss / df) / mse if mse else math.inf; p = p_f(f, df, m["dfe"]) if math.isfinite(f) else 0.0
            pe = ss / (ss + m["sse"])
            rows.append([label, f"{ss:.3f}", df, f"{ss/df:.3f}", f"{f:.3f}", fp(p), f"{pe:.3f}"])
            sent.append(_("Kesan {e} adalah {res}, F({d1}, {d2}) = {f}, p {p}, η²p = {pe}.", e=label, res=sig(p, "signifikan", "tidak signifikan"),
                          d1=df, d2=m["dfe"], f=f2(f), p=pp(p), pe=nolead(pe)))
        rows += [[_("Ralat"), f"{m['sse']:.3f}", m["dfe"], f"{mse:.3f}", "", "", ""], [_("Jumlah terbetul"), f"{m['sst']:.3f}", m["n"] - 1, "", "", "", ""]]
        out += self.table([_("Sumber"), _("JK Jenis III"), _("dk"), _("MK"), "F", "Sig.", "η²p"], rows)
        out.append(_("Panduan: Jika interaksi (A × B) signifikan, kesan A bergantung pada aras B — tafsir min sel, bukan kesan utama sahaja."))
        self.write(_("{t}: {a} mengikut {b} dan {c}", t=title, a=dep, b=fa, c=fb), out + self.apa(" ".join(sent)))

    def chisq(self):
        title = _("Khi Kuasa Dua")
        r = PickDialog(self, title, [(_("Baris:"), False, False), (_("Lajur:"), False, False)]).result
        if not r: return
        i, j = self.cols.index(r[0]), self.cols.index(r[1])
        obs = Counter((x[i].strip(), x[j].strip()) for x in self.rows if not self.blank(x[i]) and not self.blank(x[j]))
        R, C = sorted({a for a, _b in obs}, key=sortkey), sorted({b for _a, b in obs}, key=sortkey); n = sum(obs.values())
        if len(R) < 2 or len(C) < 2: return messagebox.showwarning(title, _("Setiap pemboleh ubah perlu ≥2 kategori."))
        rt = {a: sum(obs[a, b] for b in C) for a in R}; ct = {b: sum(obs[a, b] for a in R) for b in C}
        exp = {(a, b): rt[a] * ct[b] / n for a in R for b in C}
        x2 = sum((obs[k] - e) ** 2 / e for k, e in exp.items()); df = (len(R) - 1) * (len(C) - 1); p = p_chi2(x2, df)
        v = math.sqrt(x2 / (n * (min(len(R), len(C)) - 1))); low = sum(e < 5 for e in exp.values())
        out = self.table([f"{r[0]} \\ {r[1]}"] + C + [_("Jumlah")], [[a] + [obs[a, b] for b in C] + [rt[a]] for a in R] + [[_("Jumlah")] + [ct[b] for b in C] + [n]])
        out += self.table([_("Khi kuasa dua"), _("dk"), "Sig.", "Cramér's V"], [[f"{x2:.3f}", df, fp(p), f"{v:.3f}"]])
        out.append(_("{k} daripada {t} sel ({pc}%) mempunyai kekerapan jangkaan < 5{w}", k=low, t=len(exp), pc=f"{100 * low / len(exp):.1f}",
                     w=_(" — melebihi 20%, keputusan khi kuasa dua kurang dipercayai.") if low / len(exp) > .2 else "."))
        out += self.apa(_("Ujian khi kuasa dua kebebasan menunjukkan hubungan {res} antara {a} dan {b}, χ²({df}, N = {n}) = {x}, p {p}, V Cramér = {v}.",
                          res=sig(p, "yang signifikan", "yang tidak signifikan"), a=r[0], b=r[1], df=df, n=n, x=f2(x2), p=pp(p), v=nolead(v)))
        self.write(_("{t}: {a} x {b}", t=title, a=r[0], b=r[1]), out)

    # ----- bukan parametrik -----
    def mannwhitney(self):
        title = "Mann-Whitney U"
        r = PickDialog(self, title, [(_("Pemboleh ubah ujian:"), False, True), (_("Pemboleh ubah kumpulan:"), False, False)]).result
        if not r: return
        g = self.two_groups(title, *r)
        if not g: return
        (k1, a), (k2, b) = g.items(); res = mann_whitney(a, b)
        if res is None: return messagebox.showwarning(title, _("Data tidak mencukupi atau semua nilai sama."))
        u, z, p, eff, mr1, mr2 = res
        out = self.table([_("Kumpulan"), "N", _("Median"), _("Min Pangkat")], [[k1, len(a), fmtn(st.median(a)), f"{mr1:.2f}"], [k2, len(b), fmtn(st.median(b)), f"{mr2:.2f}"]])
        out += self.table(["U", "Z", _("Sig. (2-hujung)"), "r = |Z|/√N"], [[f"{u:.1f}", f"{z:.3f}", fp(p), f"{eff:.3f}"]])
        out.append(_("Panduan r: .1 kecil, .3 sederhana, .5 besar. Sig. asimptotik dengan pembetulan seri."))
        out += self.apa(_("Ujian Mann-Whitney U menunjukkan {res} dalam {dv} antara {g1} (Mdn = {md1}) dan {g2} (Mdn = {md2}), U = {u}, z = {z}, p {p}, r = {r}.",
                          res=sig(p, "perbezaan yang signifikan", "perbezaan yang tidak signifikan"), dv=r[0], g1=k1, md1=fmtn(st.median(a)),
                          g2=k2, md2=fmtn(st.median(b)), u=f"{u:.1f}", z=f2(z), p=pp(p), r=nolead(eff)))
        self.write(_("{t}: {a} mengikut {b}", t=title, a=r[0], b=r[1]), out)

    def wilcoxon(self):
        title = _("Ujian Pangkat Bertanda Wilcoxon")
        r = PickDialog(self, title, [(_("Pemboleh ubah 1:"), False, True), (_("Pemboleh ubah 2:"), False, True)]).result
        if not r: return
        pr = self.pairs(*r); x, y = [p[0] for p in pr], [p[1] for p in pr]; res = wilcoxon(x, y)
        if res is None: return messagebox.showwarning(title, _("Data tidak mencukupi atau tiada perbezaan langsung."))
        wp, wm, z, p, eff, nz = res
        out = self.table([_("Pemboleh ubah"), "N", _("Median")], [[r[0], len(x), fmtn(st.median(x))], [r[1], len(y), fmtn(st.median(y))]])
        out += self.table([_("Pangkat +"), _("Pangkat −"), _("Seri (dibuang)"), "Z", _("Sig. (2-hujung)"), "r = |Z|/√n"],
                          [[f"{wp:.1f}", f"{wm:.1f}", len(x) - nz, f"{z:.3f}", fp(p), f"{eff:.3f}"]])
        out.append(_("Pangkat + bermaksud {a} > {b}. n = bilangan pasangan yang berbeza.", a=r[0], b=r[1]))
        out += self.apa(_("Ujian pangkat bertanda Wilcoxon menunjukkan {res} antara {v1} (Mdn = {m1}) dan {v2} (Mdn = {m2}), z = {z}, p {p}, r = {r}.",
                          res=sig(p, "perbezaan yang signifikan", "perbezaan yang tidak signifikan"), v1=r[0], m1=fmtn(st.median(x)),
                          v2=r[1], m2=fmtn(st.median(y)), z=f2(z), p=pp(p), r=nolead(eff)))
        self.write(_("{t}: {a} - {b}", t=title, a=r[0], b=r[1]), out)

    def kruskal(self):
        title = "Kruskal-Wallis"
        r = PickDialog(self, title, [(_("Pemboleh ubah bersandar:"), False, True), (_("Faktor (kumpulan):"), False, False)]).result
        if not r: return
        g = self.groups(*r); res = kruskal(list(g.values()))
        if res is None: return messagebox.showwarning(title, _("Perlu ≥2 kumpulan dan data mencukupi (dan tidak semua nilai sama)."))
        h, df, p, eps, mr = res
        out = self.table([_("Kumpulan"), "N", _("Median"), _("Min Pangkat")], [[k, len(v), fmtn(st.median(v)), f"{m:.2f}"] for (k, v), m in zip(g.items(), mr)])
        out += self.table(["H", _("dk"), "Sig.", "ε²"], [[f"{h:.3f}", df, fp(p), f"{eps:.3f}"]])
        out.append(_("Jika signifikan, bandingkan pasangan kumpulan dengan Mann-Whitney U dan pembetulan Bonferroni (α / bilangan perbandingan)."))
        out += self.apa(_("Ujian Kruskal-Wallis menunjukkan {res} dalam {dv} merentas kumpulan {iv}, H({df}) = {h}, p {p}, ε² = {e}.",
                          res=sig(p, "perbezaan yang signifikan", "perbezaan yang tidak signifikan"), dv=r[0], iv=r[1], df=df, h=f2(h), p=pp(p), e=nolead(eps)))
        self.write(_("{t}: {a} mengikut {b}", t=title, a=r[0], b=r[1]), out)

    # ----- regresi -----
    def regression(self):
        title = _("Regresi Linear")
        r = PickDialog(self, title, [(_("Pemboleh ubah bersandar (Y):"), False, True), (_("Peramal (X, boleh >1):"), True, True)]).result
        if not r: return
        dep, ind = r
        if dep in ind: return messagebox.showwarning(title, _("Y tidak boleh juga menjadi peramal."))
        idx = [self.cols.index(c) for c in [dep] + ind]; data = []
        for row in self.rows:  # buang kes yang ada nilai kosong (listwise)
            v = [self.num(row[i]) for i in idx]
            if None not in v: data.append(v)
        m = ols([d[0] for d in data], [d[1:] for d in data]) if data else None
        if m is None: return messagebox.showwarning(title, _("Tidak boleh dikira: data tidak mencukupi, Y malar, atau peramal berkolinear."))
        pf = lambda x, df: p_t(x, df) if math.isfinite(x) else 0.0
        pmod = p_f(m["f"], m["k"], m["dfe"]) if math.isfinite(m["f"]) else 0.0
        out = self.table(["N", "R", "R²", _("R² Terlaras"), _("Ralat Piawai Anggaran")],
                         [[m["n"], f"{math.sqrt(max(0, m['r2'])):.3f}", f"{m['r2']:.3f}", f"{m['adj']:.3f}", f"{m['see']:.3f}"]])
        out += self.table([_("Sumber"), _("JK"), _("dk"), _("MK"), "F", "Sig."],
                          [[_("Regresi"), f"{m['ssr']:.3f}", m["k"], f"{m['ssr']/m['k']:.3f}", f"{m['f']:.3f}", fp(pmod)],
                           [_("Reja"), f"{m['sse']:.3f}", m["dfe"], f"{m['sse']/m['dfe']:.3f}", "", ""],
                           [_("Jumlah"), f"{m['sst']:.3f}", m["n"] - 1, "", "", ""]])
        xs = [d[1:] for d in data]; vf = [None] + vif(xs)
        fv = lambda v: "-" if v is None else ("∞" if math.isinf(v) else f"{v:.3f}")
        out += self.table(["", "B", _("Ralat Piawai"), "Beta", "t", "Sig.", _("Toleransi"), "VIF"],
                          [[name, f"{m['b'][a]:.3f}", f"{m['se'][a]:.3f}", "" if a == 0 else f"{m['beta'][a]:.3f}",
                            f"{m['t'][a]:.3f}", fp(pf(m["t"][a], m["dfe"])),
                            "" if a == 0 else fv(None if vf[a] is None else 1 / vf[a]), "" if a == 0 else fv(vf[a])]
                           for a, name in enumerate([_("(Pemalar)")] + ind)])
        ok = lambda p: _("Dipenuhi") if p >= .05 else _("Dilanggar")   # Sig. >= .05: andaian tidak ditolak
        sw, bp, dw = shapiro(m["e"]), breusch_pagan(m["e"], xs), durbin_watson(m["e"]) if m["sse"] > 0 else None
        na = _("Tak boleh dikira")
        rows = [[_("Normaliti reja (Shapiro-Wilk)"), f"W = {sw[0]:.3f}", fp(sw[1]), ok(sw[1])] if sw else [_("Normaliti reja (Shapiro-Wilk)"), "-", "-", na],
                [_("Homoskedastisiti (Breusch-Pagan, dk={d})", d=bp[1]), f"χ² = {bp[0]:.3f}", fp(p_chi2(*bp)), ok(p_chi2(*bp))] if bp else [_("Homoskedastisiti (Breusch-Pagan)"), "-", "-", na],
                [_("Kebebasan reja (Durbin-Watson)"), f"d = {dw:.3f}" if dw is not None else "-", "", "-" if dw is None else (_("Dipenuhi") if 1.5 <= dw <= 2.5 else _("Semak"))],
                [_("Multikolinearan (VIF maks)"), fv(max((v for v in vf[1:] if v is not None), default=None)), "",
                 _("Dipenuhi") if all(v is not None and v < 10 for v in vf[1:]) else _("Semak")]]
        out += ["", _("Ujian Andaian Regresi")] + self.table([_("Andaian"), _("Statistik"), "Sig.", _("Keputusan")], rows)
        out.append(_("Panduan: Sig. ≥ .05 = andaian dipenuhi; Durbin-Watson 1.5–2.5 = OK; VIF < 10 = OK."))
        sent = [_("Model regresi adalah {res}, F({k}, {df}) = {f}, p {p}, dan menerangkan {pc}% varians dalam {dv} (R² = {r2}).",
                  res=sig(pmod, "signifikan", "tidak signifikan"), k=m["k"], df=m["dfe"], f=f2(m["f"]), p=pp(pmod), pc=f"{100 * m['r2']:.1f}", dv=dep, r2=nolead(m["r2"]))]
        for a, name in enumerate(ind, 1):
            p = pf(m["t"][a], m["dfe"])
            sent.append(_("{x} ialah peramal {res} bagi {dv} (B = {b}, β = {beta}, t({df}) = {t}, p {p}).", x=name, res=sig(p, "yang signifikan", "yang tidak signifikan"),
                          dv=dep, b=f2(m["b"][a]), beta=nolead(m["beta"][a]) if abs(m["beta"][a]) < 1 else f2(m["beta"][a]), df=m["dfe"], t=f2(m["t"][a]), p=pp(p)))
        out += self.apa(" ".join(sent))
        sd = m["see"] or 1; z = sorted(v / sd for v in m["e"]); n = len(z); N = st.NormalDist()
        out += [plot_ops(_("Reja lwn Nilai Ramalan"), m["yhat"], m["e"], _("Nilai ramalan"), _("Reja"), "zero"),
                plot_ops(_("Plot Q-Q Normal Reja"), [N.inv_cdf((i - .375) / (n + .25)) for i in range(1, n + 1)], z, _("Kuantil teori"), _("Reja piawai"), "diag")]
        self.write(_("{t}: {a} ~ {b}", t=title, a=dep, b=" + ".join(ind)), out)

    def logistic(self):
        title = _("Regresi Logistik (Binari)")
        r = PickDialog(self, title, [(_("Pemboleh ubah bersandar (2 kategori):"), False, False), (_("Peramal (X, angka):"), True, True)]).result
        if not r: return
        dep, ind = r
        if dep in ind: return messagebox.showwarning(title, _("Y tidak boleh juga menjadi peramal."))
        di, idx = self.cols.index(dep), [self.cols.index(c) for c in ind]; data = []
        for row in self.rows:  # listwise
            v = [self.num(row[i]) for i in idx]
            if not self.blank(row[di]) and None not in v: data.append((row[di].strip(), v))
        cats = sorted({d[0] for d in data}, key=sortkey)
        if len(cats) != 2: return messagebox.showwarning(title, _("Pemboleh ubah bersandar mesti ada tepat 2 kategori (ada {n}).", n=len(cats)))
        y = [int(d[0] == cats[1]) for d in data]; xs = [d[1] for d in data]
        m = logit(y, xs) if len(data) > len(ind) + 1 else None
        if m is None: return messagebox.showwarning(title, _("Model tidak menumpu: data tidak mencukupi, peramal berkolinear, atau pemisahan sempurna (satu peramal meramal Y dengan tepat)."))
        pmod = p_chi2(m["chi2"], m["k"])
        out = [_("Pengekodan: {a} = 0, {b} = 1   (kebarangkalian yang dimodelkan: {d} = {b})", a=cats[0], b=cats[1], d=dep)]
        out += self.table(["N", _("-2 Log Kebolehjadian"), _("R² Cox & Snell"), _("R² Nagelkerke")], [[m["n"], f"{-2*m['ll']:.3f}", f"{m['cs']:.3f}", f"{m['nk']:.3f}"]])
        out += ["", _("Ujian Omnibus Model")] + self.table(["χ²", _("dk"), "Sig."], [[f"{m['chi2']:.3f}", m["k"], fp(pmod)]])
        ex = lambda b: f"{math.exp(b):.3f}" if b < 700 else "∞"
        out += self.table(["", "B", _("Ralat Piawai"), "Wald", _("dk"), "Sig.", "Exp(B)"],
                          [[name, f"{m['b'][a]:.3f}", f"{m['se'][a]:.3f}", f"{m['wald'][a]:.3f}", 1,
                            fp(p_chi2(m["wald"][a], 1)) if math.isfinite(m["wald"][a]) else "< .001", ex(m["b"][a])]
                           for a, name in enumerate([_("(Pemalar)")] + ind)])
        pred = [int(p >= .5) for p in m["p"]]; cnt = Counter(zip(y, pred))
        pc = lambda a: f"{100*cnt[a, a]/(cnt[a, 0]+cnt[a, 1]):.1f}"; tot = 100 * (cnt[0, 0] + cnt[1, 1]) / len(y)
        out += ["", _("Jadual Klasifikasi (titik potong 0.5)")] + self.table([_("Sebenar \\ Ramalan"), cats[0], cats[1], _("% Betul")],
               [[cats[0], cnt[0, 0], cnt[0, 1], pc(0)], [cats[1], cnt[1, 0], cnt[1, 1], pc(1)], [_("Keseluruhan"), "", "", f"{tot:.1f}"]])
        out.append(_("Panduan: Exp(B) > 1 = peluang Y=1 meningkat bila X naik satu unit; Exp(B) < 1 = menurun."))
        out += self.apa(_("Model regresi logistik adalah {res}, χ²({k}, N = {n}) = {x}, p {p}, R² Nagelkerke = {nk}, dan mengklasifikasikan {pc}% kes dengan betul.",
                          res=sig(pmod, "signifikan", "tidak signifikan"), k=m["k"], n=m["n"], x=f2(m["chi2"]), p=pp(pmod), nk=nolead(m["nk"]), pc=f"{tot:.1f}"))
        self.write(_("{t}: {a} ~ {b}", t=title, a=dep, b=" + ".join(ind)), out)

    # ----- skala: kebolehpercayaan & EFA -----
    def reliability(self):
        title = _("Kebolehpercayaan (Cronbach's Alpha)")
        r = PickDialog(self, title, [(_("Item skala:"), True, True)]).result
        if not r: return
        items = r[0]
        if len(items) < 2: return messagebox.showwarning(title, _("Pilih sekurang-kurangnya 2 item."))
        ids, rows = self.complete(items); rel = reliability(rows)
        if rel is None or rel["alpha"] is None: return messagebox.showwarning(title, _("Tidak boleh dikira: kes lengkap tidak mencukupi atau varians skor jumlah sifar."))
        a = rel["alpha"]
        out = self.table([_("N (kes lengkap)"), _("Bilangan item"), "Cronbach's α", _("α item terpiawai")], [[rel["n"], rel["k"], f"{a:.3f}", f"{rel['std']:.3f}"]])
        if len(rows) < len(self.rows): out.append(_("{k} kes dikecualikan kerana ada item hilang (listwise).", k=len(self.rows) - len(rows)))
        fx = lambda v: "-" if v is None else f"{v:.3f}"
        out += ["", _("Statistik Item-Jumlah")] + self.table(
            [_("Item"), _("Min"), _("SP"), _("Min skala jika dibuang"), _("Varians skala jika dibuang"), _("Korelasi item-jumlah terbetul"), _("α jika item dibuang")],
            [[c, f"{it['mean']:.3f}", f"{it['sd']:.3f}", f"{it['smd']:.3f}", f"{it['svd']:.3f}", fx(it["ritc"]), fx(it["aid"])] for c, it in zip(items, rel["items"])])
        neg = [c for c, it in zip(items, rel["items"]) if it["ritc"] is not None and it["ritc"] < 0]
        weak = [c for c, it in zip(items, rel["items"]) if it["ritc"] is not None and 0 <= it["ritc"] < .3]
        up = [c for c, it in zip(items, rel["items"]) if it["aid"] is not None and it["aid"] > a + .001]
        if neg: out.append(_("AMARAN: {v} mempunyai korelasi item-jumlah negatif — mungkin item songsang. Songsangkan dahulu (Data > Songsangkan Item), kemudian ulang analisis dengan item _r.", v=", ".join(neg)))
        if weak: out.append(_("Korelasi item-jumlah < .30 (item lemah): {v}", v=", ".join(weak)))
        if up: out.append(_("Membuang item ini akan menaikkan α: {v} — pertimbangkan dari segi teori sebelum membuang.", v=", ".join(up)))
        out.append(_("Panduan α: ≥ .90 cemerlang, ≥ .80 baik, ≥ .70 boleh diterima, ≥ .60 dipersoalkan, ≥ .50 lemah, < .50 tidak boleh diterima."))
        lab = next(l for th, l in ((.9, _("cemerlang")), (.8, _("baik")), (.7, _("boleh diterima")), (.6, _("dipersoalkan")), (.5, _("lemah")), (-9, _("tidak boleh diterima"))) if a >= th)
        out += self.apa(_("Kebolehpercayaan konsistensi dalaman bagi skala {k} item ini adalah {lab} (α Cronbach = {a}).", k=rel["k"], lab=lab, a=nolead(a)))
        self.write(_("{t}: {v}", t=title, v=", ".join(items)), out)

    def efa(self):
        title = _("Analisis Faktor Penerokaan (EFA)")
        r = PickDialog(self, title, [(_("Item:"), True, True)]).result
        if not r: return
        items = r[0]; p = len(items)
        if p < 3: return messagebox.showwarning(title, _("Pilih sekurang-kurangnya 3 item."))
        f = FormDialog(self, title, [("radio", _("Kaedah pengekstrakan:"), ["Principal Axis Factoring (PAF)", "Principal Components (PCA)"], 0),
                                     ("radio", _("Putaran:"), ["Varimax", "Promax", _("Tiada")], 0),
                                     ("entry", _("Bilangan faktor (kosong = eigen > 1):"), ""), ("entry", _("Sembunyikan muatan di bawah:"), "0.40")]).result
        if not f: return
        ids, rows = self.complete(items); n = len(rows)
        if n <= p: return messagebox.showwarning(title, _("Kes lengkap ({n}) mesti lebih banyak daripada bilangan item ({p}).", n=n, p=p))
        R = corr_matrix(rows); kb = kmo_bartlett(R, n)
        if kb is None: return messagebox.showwarning(title, _("Matriks korelasi singular: ada item yang sama atau berkolinear sempurna (cth. M3 dan M3_r dipilih bersama). Buang salah satu."))
        kmo, msa, chi, df, pb = kb; vals, _v = jacobi_eig(R)
        try: k = int(f[2]) if f[2].strip() else sum(v > 1 for v in vals); cut = float(f[3].replace(",", "."))
        except ValueError: return messagebox.showwarning(title, _("Bilangan faktor dan had muatan mesti nombor."))
        if not 1 <= k < p: return messagebox.showwarning(title, _("Bilangan faktor mesti antara 1 dan {m}.", m=p - 1))
        meth = "paf" if f[0] == 0 else "pca"; L, h0, h, it, ok = extract(R, k, meth)
        rot = ["varimax", "promax", "none"][f[1]] if k > 1 else "none"
        if rot == "varimax": P, Sm, phi = varimax(L)[0], None, None
        elif rot == "promax":
            res = promax(L)
            if res is None: return messagebox.showwarning(title, _("Putaran Promax gagal (matriks singular). Cuba Varimax."))
            P, Sm, phi = res
        else: P, Sm, phi = L, None, None
        mname = ["Principal Axis Factoring", "Principal Components"][f[0]]; rname = {"varimax": "Varimax", "promax": "Promax", "none": _("tiada")}[rot]
        out = [_("Kaedah: {m}; putaran: {r}; N = {n} kes lengkap; {p} item.", m=mname, r=rname, n=n, p=p)]
        if k == 1 and f[1] != 2: out.append(_("Hanya 1 faktor diekstrak, jadi putaran tidak dijalankan."))
        out += self.table(["KMO", "Bartlett χ²", _("dk"), "Sig."], [[f"{kmo:.3f}", f"{chi:.3f}", df, fp(pb)]])
        out.append(_("Panduan: KMO ≥ .60 dan Bartlett Sig. < .05 bermaksud data sesuai untuk analisis faktor. MSA item < .50 → pertimbangkan untuk membuang item."))
        if not ok: out.append(_("AMARAN: pengekstrakan tidak menumpu selepas {i} lelaran — keputusan tidak boleh dipercayai. Kurangkan bilangan faktor.", i=it))
        if any(x > 1 for x in h): out.append(_("AMARAN: kes Heywood (komunaliti > 1) — biasanya terlalu banyak faktor atau item terlalu sedikit bagi setiap faktor."))
        out += ["", _("Komunaliti")] + self.table([_("Item"), _("Awal"), _("Pengekstrakan"), "MSA"],
                                                  [[c, f"{a:.3f}", f"{b:.3f}", f"{m:.3f}" + (" *" if m < .5 else "")] for c, a, b, m in zip(items, h0, h, msa)])
        ss_e = [sum(r_[j] ** 2 for r_ in L) for j in range(k)]
        ss_r = [sum(r_[j] ** 2 for r_ in P) for j in range(k)] if rot == "varimax" else None
        cum = [sum(vals[:i + 1]) / p * 100 for i in range(p)]
        rows = []
        for i in range(p):
            row = [i + 1, f"{vals[i]:.3f}", f"{vals[i] / p * 100:.2f}", f"{cum[i]:.2f}"]
            row += [f"{ss_e[i]:.3f}", f"{ss_e[i] / p * 100:.2f}", f"{sum(ss_e[:i + 1]) / p * 100:.2f}"] if i < k else ["", "", ""]
            if ss_r: row += [f"{ss_r[i]:.3f}", f"{ss_r[i] / p * 100:.2f}", f"{sum(ss_r[:i + 1]) / p * 100:.2f}"] if i < k else ["", "", ""]
            rows.append(row)
        head = [_("Faktor"), _("Eigen awal"), _("% Varians"), _("% Kumulatif"), _("SS pengekstrakan"), _("% Varians"), _("% Kumulatif")]
        if ss_r: head += [_("SS putaran"), _("% Varians"), _("% Kumulatif")]
        out += ["", _("Jumlah Varians Diterangkan")] + self.table(head, rows)
        if rot == "promax": out.append(_("Untuk putaran oblik (Promax), jumlah kuasa dua muatan putaran tidak boleh dijumlahkan; rujuk matriks pola dan struktur."))
        out.append(plot_ops(_("Plot Scree"), list(range(1, p + 1)), vals, _("Faktor"), _("Nilai eigen"), "scree"))
        order = sorted(range(p), key=lambda i: (max(range(k), key=lambda j: abs(P[i][j])), -max(abs(x) for x in P[i])))
        fmtl = lambda x: f"{x:.3f}" if abs(x) >= cut else ""
        mat = lambda M: self.table([_("Item")] + [str(j + 1) for j in range(k)], [[items[i]] + [fmtl(x) for x in M[i]] for i in order])
        name = {"varimax": _("Matriks Faktor Berputar (Varimax)"), "promax": _("Matriks Pola (Promax)"), "none": _("Matriks Faktor (tanpa putaran)")}[rot]
        out += ["", name] + mat(P)
        if rot == "promax":
            out += ["", _("Matriks Struktur")] + mat(Sm)
            out += ["", _("Matriks Korelasi Faktor")] + self.table([_("Faktor")] + [str(j + 1) for j in range(k)], [[i + 1] + [f"{x:.3f}" for x in phi[i]] for i in range(k)])
        out.append(_("Item diisih mengikut faktor dan saiz muatan; muatan |x| < {c} disembunyikan.", c=fmtn(cut)))
        none_ = [items[i] for i in range(p) if all(abs(x) < cut for x in P[i])]
        cross = [items[i] for i in range(p) if sum(abs(x) >= cut for x in P[i]) > 1]
        if none_: out.append(_("Item tanpa muatan ≥ {c}: {v}", c=fmtn(cut), v=", ".join(none_)))
        if cross: out.append(_("Item dengan muatan silang (≥ {c} pada > 1 faktor): {v}", c=fmtn(cut), v=", ".join(cross)))
        pct = sum(ss_e) / p * 100
        out += self.apa(_("Analisis faktor penerokaan ({m}, putaran {r}) dijalankan ke atas {p} item (N = {n}). Nilai KMO = {kmo} dan ujian sfera Bartlett adalah {res}, χ²({df}) = {chi}, p {pb}. Sebanyak {k} faktor dikekalkan ({crit}) dan menerangkan {pct}% daripada jumlah varians.",
                          m=mname, r=rname, p=p, n=n, kmo=nolead(kmo), res=sig(pb, "signifikan", "tidak signifikan"), df=df, chi=f2(chi), pb=pp(pb), k=k,
                          crit=_("nilai eigen > 1") if not f[2].strip() else _("ditetapkan oleh penyelidik"), pct=f"{pct:.2f}"))
        self.write(_("{t}: {v}", t=title, v=", ".join(items)), out)

    # ----- saringan data -----
    def outliers_z(self):
        title = _("Outlier Univariat (|z| > 3.29)")
        r = PickDialog(self, title, [(_("Pemboleh ubah (angka):"), True, True)]).result
        if not r: return
        rows = []
        for c in r[0]:
            i = self.cols.index(c); v = [(k, self.num(row[i])) for k, row in enumerate(self.rows)]; v = [(k, x) for k, x in v if x is not None]
            if len(v) < 3: continue
            m, sd = st.mean(x for _k, x in v), st.stdev(x for _k, x in v)
            rows += [[k + 1, self.rows[k][0], c, fmtn(x), f"{(x - m) / sd:.2f}"] for k, x in v if sd and abs((x - m) / sd) > 3.29]
        out = self.table([_("Baris"), self.cols[0], _("Pemboleh ubah"), _("Nilai"), "z"], rows) if rows else [_("Tiada outlier univariat ditemui.")]
        out.append(_("Panduan: semak dahulu sama ada outlier ialah ralat kemasukan data (betulkan) atau nilai sebenar (kekalkan, atau laporkan analisis dengan dan tanpa kes itu)."))
        self.write(title, out)

    def outliers_mahal(self):
        title = _("Outlier Multivariat (Mahalanobis)")
        r = PickDialog(self, title, [(_("Pemboleh ubah (angka, ≥2):"), True, True)]).result
        if not r: return
        if len(r[0]) < 2: return messagebox.showwarning(title, _("Pilih sekurang-kurangnya 2 pemboleh ubah."))
        ids, rows = self.complete(r[0])
        if len(rows) <= len(r[0]): return messagebox.showwarning(title, _("Kes lengkap tidak mencukupi."))
        md = mahalanobis(rows)
        if md is None: return messagebox.showwarning(title, _("Matriks kovarians singular: ada pemboleh ubah yang berkolinear sempurna (cth. item dan skor jumlahnya). Buang salah satu."))
        flag = sorted([(d, p, k) for (d, p), k in zip(md, ids) if p < .001], reverse=True)
        out = [_("N = {n} kes lengkap; dk = {k}; kriteria: p < .001.", n=len(rows), k=len(r[0]))]
        out += self.table([_("Baris"), self.cols[0], "D²", "p"], [[k + 1, self.rows[k][0], f"{d:.3f}", fp(p)] for d, p, k in flag]) if flag else [_("Tiada outlier multivariat ditemui.")]
        out.append(_("{k} kes ({pc}%) dikenal pasti sebagai outlier multivariat.", k=len(flag), pc=f"{100 * len(flag) / len(rows):.1f}"))
        self.write(_("{t}: {v}", t=title, v=", ".join(r[0])), out)

    def harman(self):
        title = _("Ujian Satu Faktor Harman (CMB)")
        r = PickDialog(self, title, [(_("Semua item pengukuran (semua konstruk):"), True, True)]).result
        if not r: return
        if len(r[0]) < 3: return messagebox.showwarning(title, _("Pilih sekurang-kurangnya 3 item."))
        ids, rows = self.complete(r[0])
        if len(rows) <= len(r[0]): return messagebox.showwarning(title, _("Kes lengkap tidak mencukupi."))
        vals, _v = jacobi_eig(corr_matrix(rows)); p = len(r[0]); pc = vals[0] / p * 100
        out = [_("Kaedah: Principal Components tanpa putaran, satu faktor; N = {n} kes lengkap; {p} item.", n=len(rows), p=p)]
        out += self.table([_("Eigen faktor pertama"), _("% Varians faktor pertama"), _("Bilangan faktor eigen > 1")], [[f"{vals[0]:.3f}", f"{pc:.2f}", sum(v > 1 for v in vals)]])
        out.append(_("Keputusan: tiada petunjuk bias kaedah biasa yang serius (< 50%).") if pc < 50 else _("AMARAN: faktor tunggal menerangkan ≥ 50% varians — kemungkinan bias kaedah biasa (CMB)."))
        out += self.apa(_("Ujian satu faktor Harman (PCA tanpa putaran) menunjukkan bahawa faktor pertama menerangkan {pc}% daripada jumlah varians, iaitu {cmp} ambang 50%.",
                          pc=f"{pc:.2f}", cmp=_("di bawah") if pc < 50 else _("melebihi")))
        self.write(title, out)

    def help(self):
        messagebox.showinfo(_("Cara Guna"), _(
            "1. Fail > Buka CSV / Excel, atau taip data di 'Paparan Data' (dwiklik sel untuk edit).\n"
            "2. Setiap lajur = satu pemboleh ubah, setiap baris = satu kes (responden).\n"
            "3. Bersihkan data dahulu melalui menu Data: Cari Kes Berulang, Semak Julat Sah, Kod Data Hilang, Analisis Data Hilang.\n"
            "4. Songsangkan item negatif dan kira skor konstruk melalui menu Data.\n"
            "5. Pilih ujian dari menu Analisis. Keputusan dan ayat laporan APA keluar di 'Paparan Output'.\n"
            "6. Fail > Eksport Output ke HTML untuk menyalin jadual ke Word/LibreOffice.\n\n"
            "Sig. < .05 biasanya bermaksud keputusan signifikan."))

def main():
    load_settings(); root = tk.Tk(); App(root); root.mainloop()

if __name__ == "__main__":
    main()
