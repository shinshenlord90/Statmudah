"""Semak setiap rentetan _() / sig() dalam statmudah.py ada terjemahan EN dengan {ruang letak} yang sama."""
import ast, string, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from i18n import EN
src = ast.parse(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "statmudah.py"), encoding="utf-8").read()); keys = set()
for n in ast.walk(src):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("_", "sig"):
        for a in (n.args[:1] if n.func.id == "_" else n.args[1:3]):
            if isinstance(a, ast.Constant) and isinstance(a.value, str): keys.add(a.value)
fields = lambda s: {f for _t, f, _s, _c in string.Formatter().parse(s) if f}
missing = sorted(k for k in keys if k not in EN)
bad = sorted(k for k in keys & EN.keys() if fields(k) != fields(EN[k]))
unused = sorted(EN.keys() - keys)
assert not missing, f"tiada terjemahan: {missing}"
assert not bad, f"ruang letak berbeza: {bad}"
assert not unused, f"terjemahan tidak digunakan: {unused}"
print(f"i18n ok ({len(keys)} rentetan)")
