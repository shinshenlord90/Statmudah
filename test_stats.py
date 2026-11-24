import smstats as s
for got, want in [(s.p_t(2.228, 10), .05), (s.p_t(1.96, 1e6), .05), (s.p_f(4.103, 2, 10), .05),
                  (s.p_chi2(3.841, 1), .05), (s.p_chi2(18.307, 10), .05), (s.p_chi2(2.0, 4), .7358)]:
    assert abs(got - want) < 1e-3, (got, want)
print("ok")
import statistics as st, math, random
x = [65, 78, 55, 88, 72, 81, 60, 92, 68, 75]; y = [70, 80, 61, 85, 75, 86, 66, 90, 72, 79]
m = s.ols(y, [[v] for v in x]); lr = st.linear_regression(x, y); r = st.correlation(x, y)
assert abs(m["b"][1] - lr.slope) < 1e-9 and abs(m["b"][0] - lr.intercept) < 1e-9
assert abs(m["r2"] - r * r) < 1e-9 and abs(m["t"][1] - r * math.sqrt(8 / (1 - r * r))) < 1e-6
random.seed(1); X = [[random.random(), random.random()] for _ in range(50)]
Y = [1 + 2 * a + 3 * b + random.gauss(0, .01) for a, b in X]
assert all(abs(g - w) < .05 for g, w in zip(s.ols(Y, X)["b"], [1, 2, 3]))
assert s.ols(Y, [[a, 2 * a] for a, _ in X]) is None  # kolinear
print("regresi ok")
# nilai rujukan dari scipy 1.18 / statsmodels 0.15
w, p = s.shapiro([65, 78, 55, 88, 72, 81, 60, 92, 68, 75]); assert abs(w - .983967) < 1e-5 and abs(p - .982837) < 1e-5
m = s.logit([0, 0, 1, 0, 1, 1, 1, 1, 0, 0], [[1, 2], [2, 1], [3, 4], [4, 3], [5, 6], [6, 5], [7, 8], [8, 7], [2, 5], [6, 2]])
assert all(abs(a - b) < 1e-5 for a, b in zip(m["b"], [-11.134863, .951418, 1.827228])) and abs(m["ll"] + 2.278924) < 1e-5
assert s.logit([0, 0, 0, 1, 1, 1], [[1], [2], [3], [4], [5], [6]]) is None  # pemisahan sempurna
assert abs(s.vif(X)[0] - 1) < .01 and s.durbin_watson([1, -1, 1, -1]) == 3.0
print("andaian & logistik ok")
# ANOVA dua hala, Tukey, Spearman, Levene: rujukan scipy 1.18 / statsmodels 0.15
g = [[60, 65, 70, 62], [80, 85, 78, 90], [50, 58, 55]]
assert abs(s.p_f(*s.levene(g)[:3]) - .686081) < 1e-5 and abs(s.ptukey(3.5, 3, 10) - .922897) < 1e-5
assert abs(next(p for i, j, d, se, p, lo, hi in s.tukey(g) if (i, j) == (0, 1)) - .001129) < 1e-5
assert abs(st.correlation(s.ranks([1, 2, 3, 4, 5, 6]), s.ranks([2, 1, 4, 3, 6, 5])) - .828571) < 1e-5
assert s.ranks([10, 20, 20, 30]) == [1, 2.5, 2.5, 4]
m = s.anova2([3, 4, 5, 6, 7, 9, 2, 3, 8, 9, 5, 4], list("PPPQQQPPPQQQ"), list("xxxxxxyyyyyy"))
assert all(abs(m["terms"][k][0] - w) < 1e-6 for k, w in (("A", 18.75), ("B", .75), ("AB", 2.083333))) and abs(m["sse"] - 41.333333) < 1e-5
assert s.anova2([1, 2, 3, 4], list("PPQQ"), list("xyxx")) is None  # sel (Q, y) kosong
print("anova2, tukey, spearman, levene ok")
# Fasa 1: rujukan scipy 1.18
x, a, b, y = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5], [1, 2, 2, 3, 4, 5], [3, 4, 4, 5, 5, 6, 6], [2, 2, 3, 5, 4, 6, 7, 6, 4, 3, 6]
g1, _, g2, _ = s.skew_kurt(x); assert abs(g1 - .664050) < 1e-5 and abs(g2 - .650510) < 1e-5
assert abs(s.mann_whitney(a, b)[2] - .035426) < 1e-5 and abs(s.wilcoxon(x, y)[3] - .854464) < 1e-5
assert abs(s.kruskal([a, b, [5, 6, 7, 7]])[0] - 9.303025) < 1e-5
assert s.skew_kurt([1, 2, 3]) is None and s.wilcoxon([1, 2], [1, 2]) is None
print("fasa 1 statistik ok")
# Fasa 2: rujukan pingouin 0.5 / factor_analyzer 0.5 (Rotator varimax, toleransi ketat)
X = [[4, 5, 4, 2, 1, 2], [3, 4, 3, 2, 2, 1], [5, 5, 4, 4, 5, 4], [2, 1, 2, 4, 5, 4], [4, 4, 5, 2, 2, 3],
     [1, 2, 1, 5, 4, 5], [3, 3, 4, 3, 3, 3], [5, 4, 5, 1, 2, 1], [2, 2, 3, 4, 4, 5], [4, 5, 5, 3, 2, 2]]
assert abs(s.reliability(X)["alpha"] - -.198190) < 1e-5   # alpha negatif: item 4-6 berlawanan arah
R = s.corr_matrix(X); kmo, msa, chi, df, pb = s.kmo_bartlett(R, len(X))
assert abs(kmo - .545238) < 1e-5 and abs(chi - 52.568724) < 1e-4 and df == 15
assert all(abs(a - b) < 1e-5 for a, b in zip(s.jacobi_eig(R)[0], [4.45768, .881185, .342343, .243997, .065568, .009227]))
V, _T = s.varimax(s.extract(R, 2, "pca")[0])
ref = [[.943485, .261573], [.837552, .353584], [.840152, .400978], [.422816, .857863], [.240088, .908846], [.379473, .863007]]
cols = [[abs(r[j]) for r in V] for j in range(2)]; rc = [[r[j] for r in ref] for j in range(2)]
assert all(min(max(abs(a - b) for a, b in zip(c, rcol)) for c in cols) < 1e-5 for rcol in rc)  # sama hingga tanda & susunan
assert s.kmo_bartlett([[1, 1], [1, 1]], 10) is None and s.mahalanobis([[1, 2], [2, 4], [3, 6]]) is None  # singular
print("fasa 2 statistik ok")
