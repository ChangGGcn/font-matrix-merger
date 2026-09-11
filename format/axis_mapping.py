# -*- coding: utf-8 -*-
"""轴空间映射与变体函数重参数化 (跨设计空间合成的基础设施)

三层坐标 (每个轴独立):

    user  --fvar 归一化-->  pre  --avar-->  norm

  * user: fvar 的用户坐标 (min/default/max);
  * pre:  由 (min, default, max) 双段线性归一化到 [-1, 1] (default → 0);
  * norm: avar 的分段线性映射之后的坐标; OpenType 变体数据
    (gvar tuple 支撑 / VarStore region / HVAR 索引) 的峰值都在这个空间。

跨字体合成时, 源字体的 norm 空间与合并字体的 norm 空间通过 user 空间相连:

    T: merged_norm --(合并 fvar 反归一化)--> user --(源 fvar 归一化 + 源 avar)--> src_norm

T 是分段线性的, 所以源字体的 hat 支撑经 T 复合后仍是分段线性: 把 T 的断点
纳入节点, 就能用**有限个 hat 之和精确表示** —— 这正是"必要时插值出新 master"
(新 hat 的峰值就是插值出来的 master 位置, 权重是该位置源函数的值)。

OT 语义提醒 (supportScalar, ot=True):
  * 峰值 0 的轴被忽略 → "该字体在此轴恒定" 用**省略该轴**表达 (等价于 lifting 补 0);
  * 支撑下界 < 0 < 上界 的 tuple 会被忽略 → 细化产生的 hat 必须落在 0 的一侧,
    且不能跨越 0 (映射单调且 0 映射到 0, 故源侧合法的 hat 像也合法);
  * 支撑在合并域边界被截断时, 用 start == peak == 边界 的"半 hat"表达。
"""
import itertools

from fontTools.varLib.models import supportScalar

AXIS_MIN = -1.0
AXIS_MAX = 1.0
EPS = 1e-9


def _clamp_axis(v):
    return max(AXIS_MIN, min(AXIS_MAX, v))


def invert_piecewise(pl, y, flat="left"):
    """在分段线性映射上**逐段反解** x 使 pl.map(x) == y。

    不能直接用"把点对调再排序"的 PL 逆: 平台段 (avar 的钳制段) 会让相邻
    段的斜率整体偏掉。这里逐段线性求解, 只有平台段本身有歧义 —— 按
    flat 参数取左端/右端。
    """
    xs, ys = pl.xs, pl.ys
    if not xs:
        return y
    if y <= ys[0]:
        return xs[0] + (y - ys[0])
    if y >= ys[-1]:
        return xs[-1] + (y - ys[-1])
    for i in range(len(xs) - 1):
        y0, y1 = ys[i], ys[i + 1]
        if abs(y1 - y0) < EPS:
            if abs(y - y0) < EPS:
                return xs[i] if flat == "left" else xs[i + 1]
            continue
        if min(y0, y1) - EPS <= y <= max(y0, y1) + EPS:
            t = (y - y0) / (y1 - y0)
            return xs[i] + t * (xs[i + 1] - xs[i])
    return xs[-1]


class PiecewiseLinear:
    """分段线性映射 (与 fontTools.models.piecewiseLinearMap 同语义)。

    只用于**单调不减**的映射 (fvar 归一化 / avar); 逆映射对平台段取左端点。
    """

    def __init__(self, points):
        pts = sorted(points)
        self.xs = [p[0] for p in pts]
        self.ys = [p[1] for p in pts]

    @classmethod
    def identity(cls):
        return cls([(-1.0, -1.0), (0.0, 0.0), (1.0, 1.0)])

    @classmethod
    def fvar(cls, triple):
        """norm -> user (双段线性反归一化)。

        注意单侧轴: min == default 时归一化域只有 [0, 1] (用户值小于 default
        会被 normalizeValue 钳到 default), default == max 时只有 [-1, 0]。
        绝不能建成带平台段的映射 —— 其逆会在平台段选错端点, 把整段斜率带偏。
        """
        lower, default, upper = triple
        if lower == default == upper:
            return cls([(0.0, default)])
        if lower == default:
            return cls([(0.0, default), (1.0, upper)])
        if upper == default:
            return cls([(-1.0, lower), (0.0, default)])
        return cls([(-1.0, lower), (0.0, default), (1.0, upper)])

    @classmethod
    def avar(cls, segments):
        """pre(归一化) -> norm: avar SegmentMap; 缺省为恒等"""
        if not segments:
            return cls.identity()
        return cls(sorted((float(k), float(v)) for k, v in segments.items()))

    def map(self, x):
        """映射一个值 (域外按 fontTools 的平移规则外推)"""
        xs, ys = self.xs, self.ys
        if not xs:
            return x
        for i, v in enumerate(xs):
            if abs(x - v) < EPS:
                return ys[i]
        if x < xs[0]:
            return x + ys[0] - xs[0]
        if x > xs[-1]:
            return x + ys[-1] - xs[-1]
        lo = 0
        for i, v in enumerate(xs):
            if v < x:
                lo = i
            else:
                break
        hi = lo + 1
        x0, x1 = xs[lo], xs[hi]
        y0, y1 = ys[lo], ys[hi]
        return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    def inverse(self):
        """单调不减映射的逆 (平台段取**右端点**)。

        平台段 [xa, xb] → y 的原像不唯一; 取右端点 xb 能让平台之后那段
        上升区间保持正确斜率 (取左端点会把整段斜率拉偏)。fvar 的单侧轴
        已经在 :meth:`fvar` 里建成无平台段的映射, 这里的平台只可能来自
        avar 的钳制段 —— 规范上罕见, 且两种取法都只影响平台邻域的斜率。
        """
        pts = []
        for x, y in zip(self.xs, self.ys):
            if pts and abs(y - pts[-1][0]) < EPS:
                pts[-1] = (y, x)
                continue
            pts.append((y, x))
        return PiecewiseLinear(pts)

    def compose(self, other):
        """self(other(x)) —— 两个分段线性映射的复合仍是分段线性的,
        断点 = other 的断点 ∪ self 断点在 other 下的原像。"""
        xs = set(other.xs)
        for y in self.xs:
            xs.add(other.inverse().map(y))
        pts = [(x, self.map(other.map(x))) for x in sorted(xs)]
        # 去掉重复点, 保证严格递增
        out = []
        for x, y in pts:
            if out and abs(x - out[-1][0]) < EPS:
                continue
            out.append((x, y))
        return PiecewiseLinear(out)

    def breakpoints(self, lo=AXIS_MIN, hi=AXIS_MAX):
        """[lo, hi] 内的断点 (不含端点)"""
        return [x for x in self.xs if lo + EPS < x < hi - EPS]

    def is_identity(self):
        return (len(self.xs) == 3 and self.xs == [-1.0, 0.0, 1.0]
                and all(abs(x - y) < EPS for x, y in zip(self.xs, self.ys)))

    def __repr__(self):
        return "PiecewiseLinear(%r)" % (list(zip(self.xs, self.ys)),)


class AxisMapping:
    """一个轴: 合并空间 (norm') 与源字体空间 (norm) 之间的映射。"""

    def __init__(self, merged_triple, merged_avar, source_triple, source_avar):
        self.merged_triple = tuple(merged_triple)
        self.source_triple = tuple(source_triple)
        self.merged_avar = dict(merged_avar or {})
        self.source_avar = dict(source_avar or {})

        pl_merged_fvar = PiecewiseLinear.fvar(self.merged_triple)
        pl_merged_avar = PiecewiseLinear.avar(merged_avar)
        pl_src_fvar = PiecewiseLinear.fvar(self.source_triple)
        pl_src_avar = PiecewiseLinear.avar(source_avar)

        # 中间层: 归一化坐标 <-> 用户坐标
        self._merged_user = pl_merged_fvar.compose(pl_merged_avar.inverse())
        self._user_merged = pl_merged_avar.compose(pl_merged_fvar.inverse())
        self._src_user = pl_src_fvar.compose(pl_src_avar.inverse())
        self._user_src = pl_src_avar.compose(pl_src_fvar.inverse())
        # 轴范围外的钳制发生在**用户空间** (字体/实例化器的行为), 不在
        # 归一化空间 —— 必须显式建模, 否则域外会线性外推出不存在的 master。
        self._clamp_merged_user = (self.merged_triple[0], self.merged_triple[2])
        self._clamp_src_user = (self.source_triple[0], self.source_triple[2])

    # -- 坐标变换 (带用户空间钳制) ----------------------------------------
    def to_source(self, x):
        """合并归一化坐标 → 源归一化坐标 (用户空间钳到源轴范围)"""
        # 平台段取**右端**: 平台左侧的用户区间被 avar 压成同一个归一化点,
        # 字体在该点只能渲染一个值; 取右端使函数在平台右侧保持连续, 从而
        # 能被 hat 精确表示 (取左端会在平台处产生内部跳变)。
        user = invert_piecewise(self._user_merged, x, flat="right")
        lo, hi = self._clamp_src_user
        user = max(lo, min(hi, user))
        return _clamp_axis(self._user_src.map(user))

    def to_merged(self, y):
        """源归一化坐标 → 合并归一化坐标 (用户空间钳到合并轴范围)"""
        user = self._src_user.map(y)
        lo, hi = self._clamp_merged_user
        user = max(lo, min(hi, user))
        return _clamp_axis(self._user_merged.map(user))

    def kinks_merged(self):
        """合并轴上函数可能折弯的位置 (合并归一化坐标)。

        来源: 合并/源两边的 fvar 端点与默认点、两边 avar 的折点 —— 全部先
        换到用户空间, 再映射到合并归一化坐标。多给节点不会破坏精确性
        (分段线性函数在更细的节点集上插值仍然精确), 漏给才会。
        """
        # 未钳制复合函数的断点 (与 to_source 的构造同源)
        comp = (PiecewiseLinear.avar(self.source_avar)
                .compose(PiecewiseLinear.fvar(self.source_triple).inverse())
                .compose(PiecewiseLinear.fvar(self.merged_triple))
                .compose(PiecewiseLinear.avar(self.merged_avar).inverse()))
        xs = set(comp.xs) | {AXIS_MIN, 0.0, AXIS_MAX}
        # 用户空间钳制点: 合并用户坐标 = 源轴端点的位置
        u2n = (PiecewiseLinear.avar(self.merged_avar)
               .compose(PiecewiseLinear.fvar(self.merged_triple).inverse()))
        for u in self._clamp_src_user:
            xs.add(u2n.map(u))
        # 平台段两端 (逐段反解在平台上有歧义 → 两端都作折点)
        um = self._user_merged
        for i in range(len(um.xs) - 1):
            if abs(um.ys[i + 1] - um.ys[i]) < EPS:
                xs.add(um.ys[i])
                xs.add(um.ys[i + 1])
        lo, hi = self._clamp_merged_user
        return sorted(_clamp_axis(x) for x in xs
                      if lo - EPS <= self._merged_user.map(x) <= hi + EPS)

    def collapsing_flats(self):
        """返回合并 avar 的"压缩平台段": [(norm, user_lo, user_hi)]。

        平台段把一段用户区间 [user_lo, user_hi] 压成同一个归一化点 norm,
        而源字体在这段区间上的插值函数通常**不是常数** —— 合并字体在该点
        只能渲染一个值, 因此这段区间上"逐点等价"在 OT 变体模型里不可达。
        调用方应据此告警, 或改用 avar_mode=2 (放弃 avar) 的策略。
        """
        out = []
        um, xs, ys = self._user_merged, self._user_merged.xs, self._user_merged.ys
        for i in range(len(xs) - 1):
            if abs(ys[i + 1] - ys[i]) < EPS and abs(xs[i + 1] - xs[i]) > EPS:
                out.append((ys[i], min(xs[i], xs[i + 1]), max(xs[i], xs[i + 1])))
        return out

    def is_identity(self):
        """轴空间 (范围 + avar 映射) 完全一致 → 不需要重参数化"""
        return (tuple(self.merged_triple) == tuple(self.source_triple)
                and dict(self.merged_avar or {}) == dict(self.source_avar or {}))

    def __repr__(self):
        return ("AxisMapping(merged=%r, source=%r)"
                % (self.merged_triple, self.source_triple))


def axis_mappings(merged_axes, merged_avar, source_axes, source_avar):
    """为两套轴空间构造 {axisTag: AxisMapping} (只含双方共有的轴)。

    Args:
        merged_axes/source_axes: {tag: (min, default, max)}
        merged_avar/source_avar: {tag: {from: to}} 或 None
    """
    merged_avar = merged_avar or {}
    source_avar = source_avar or {}
    out = {}
    for tag, src_triple in source_axes.items():
        if tag not in merged_axes:
            continue
        out[tag] = AxisMapping(merged_axes[tag], merged_avar.get(tag),
                               src_triple, source_avar.get(tag))
    return out


def source_location(mapping, x):
    """合并归一化坐标 → 源归一化坐标 (用户空间钳到源轴范围)。

    字体在自身轴范围之外是钳制的 —— 求值与折点收集都必须用这个版本。
    """
    return mapping.to_source(x)


def reachable_range(mapping):
    """该轴的**可达**源归一化区间。

    源字体的轴可能是单侧的 (min == default 或 default == max), 此时
    归一化坐标只覆盖一半; 落在不可达一侧的支撑永远不会被激活 —— 调用方
    应把它当作恒 0 处理, 而不是硬算 (会得到病态结果)。
    """
    lo_u = max(mapping.merged_triple[0], mapping.source_triple[0])
    hi_u = min(mapping.merged_triple[2], mapping.source_triple[2])
    if lo_u > hi_u:
        return (0.0, 0.0)
    lo = mapping._user_src.map(lo_u)
    hi = mapping._user_src.map(hi_u)
    return (min(lo, hi), max(lo, hi))


def hat_value(x, lower, peak, upper):
    """单轴 OT hat 标量 (supportScalar 的 1D 特化, 便于测试/自检)"""
    if peak == 0.0:
        return 1.0
    if x == peak:
        return 1.0
    if x <= lower or x >= upper:
        return 0.0
    if x < peak:
        return (x - lower) / (peak - lower)
    return (upper - x) / (upper - peak)


def support_value(loc_norm, support):
    """OT 支撑在多轴归一化位置上的标量 (峰值 0 的轴被忽略)"""
    return supportScalar(loc_norm, support, ot=True)


def refine_1d(lower, peak, upper, mapping, eps=EPS, shift=0.0):
    """把单轴 hat 精确展开成合并空间的一组 hat。

    做法: 把 hat∘T 的**节点** (映射到合并空间的支撑端点/峰 + 落在支撑内的
    映射断点) 找出来, 用节点基函数 (nodal basis) 分解 —— 每个节点上的基
    函数恰好就是一个 OT hat (start=左邻, peak=节点, end=右邻), 权重为该点
    的函数值。端点越界时把"虚拟邻点"钳到域边界, 得到 start==peak 的半 hat。

    Args:
        shift: 重定基量 c = φ(T(0))。非零时被减掉 (使函数在合并默认位置
            为 0), 并把 0 强制纳入节点 —— 保证生成的 hat 不跨 0。

    Returns:
        [(l, p, u, weight), ...] —— 权重之和逐点复现 hat ∘ T - shift
    """
    to_src, to_merged = mapping.to_source, mapping.to_merged

    def _src_at(x):
        """合并坐标 → 源空间的归一化坐标 (钳到源域: 字体在轴范围外是钳制)"""
        return mapping.to_source(x)

    # 支撑像在合并空间里的范围 (可能被 [-1,1] 域截断)
    lo_m = _clamp_axis(to_merged(lower))
    hi_m = _clamp_axis(to_merged(upper))
    # 节点 = 真实折点全集:
    #   * 轴域两端 (-1, 1) 与**钳制点** to_merged(±1) —— 源字体在自身轴范围
    #     之外是钳制的, 若源在轴端有 master (支撑 peak == ±1), 合并域里就会
    #     出现一段常数"平台", 必须由这两个边界节点界定, 否则节点基会把它
    #     插成斜坡;
    #   * 支撑像的两端与峰 (hat 自身的折点);
    #   * T 在合并域的断点 (它们**已经是**合并空间坐标, 不能再过一遍映射);
    #   * 0 (归一化的默认点, 通常是 T 的折点, 也是重定基后的零点)。
    knots = [AXIS_MIN, AXIS_MAX, lo_m,
             _clamp_axis(to_merged(peak)), hi_m, 0.0]
    knots.extend(mapping.kinks_merged())
    xs = []
    for v in sorted(knots):
        v = round(_clamp_axis(v), 10)
        if not xs or abs(v - xs[-1]) > EPS:
            xs.append(v)
    ys = [hat_value(_src_at(x), lower, peak, upper) - shift for x in xs]
    if len(xs) < 2 or max(ys) <= eps:
        return []
    # 剪掉"函数在该节点两侧仍共线"的冗余节点: tent 基只需要斜率变化点
    # (线性段中间放 tent 也能拼出同样的函数, 但会平白多出 tuple)
    if len(xs) > 2:
        keep = [0]
        for i in range(1, len(xs) - 1):
            s1 = (ys[i] - ys[i - 1]) / (xs[i] - xs[i - 1])
            s2 = (ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i])
            if abs(s1 - s2) > 1e-9:
                keep.append(i)
        keep.append(len(xs) - 1)
        xs = [xs[i] for i in keep]
        ys = [ys[i] for i in keep]
    tiny = 1e-6

    def _true(x):
        return hat_value(_src_at(x), lower, peak, upper) - shift

    terms = []
    n = len(xs)
    for i, y in enumerate(ys):
        if abs(y) <= eps:
            continue
        x = xs[i]
        if i > 0:
            left = xs[i - 1]
        elif _true(x - tiny) <= eps:
            # peak == lower 的"左半 hat": 峰左侧立刻归零 → start == peak
            left = x
        elif n > 1:                       # 域边界截断: 镜像, 越界则半 hat
            left = max(AXIS_MIN, x - (xs[1] - x))
            if left >= x:
                left = x
        else:
            left = x
        if i < n - 1:
            right = xs[i + 1]
        elif _true(x + tiny) <= eps:
            # peak == upper 的"右半 hat": 峰右侧立刻归零 → end == peak
            # (OT 语义在 v == peak 处取 1, 越过即 0 —— 必须用半 hat 复现)
            right = x
        elif i > 0:                       # 域边界截断
            right = min(AXIS_MAX, x + (x - xs[i - 1]))
            if right <= x:
                right = x
        else:
            right = x
        if left == x == right:
            continue
        terms.append((left, x, right, y))
    return terms


def refine_support(support, mappings, eps=EPS):
    """单轴的细化结果合并成多轴项 (不做重定基; 见 refine_support_rebased)。"""
    per_axis = []
    for tag, (lower, peak, upper) in support.items():
        if peak == 0.0 or (lower < 0.0 < upper):
            continue                      # OT: 被忽略的轴
        mapping = mappings.get(tag)
        if mapping is None:
            raise KeyError("合并空间缺少轴 %r, 无法重参数化" % tag)
        per_axis.append((tag, refine_1d(lower, peak, upper, mapping, eps)))
    if not per_axis:
        return []
    out = []
    for combo in itertools.product(*[terms for _, terms in per_axis]):
        sup = {}
        weight = 1.0
        for (tag, _), (l, p, u, y) in zip(per_axis, combo):
            sup[tag] = (l, p, u)
            weight *= y
        if abs(weight) > eps:
            out.append((sup, weight))
    return out


def axis_support_at_default(tag, support, mapping):
    """该轴支撑在**合并默认位置**处的标量 φ(T(0))。

    ≠ 0 意味着源字体的默认点与合并字体的默认点不重合 (跨设计空间),
    该元组的贡献必须重新定基 —— 见 refine_support_rebased。
    """
    lower, peak, upper = support
    if peak == 0.0 or (lower < 0.0 < upper):
        return 1.0
    return hat_value(source_location(mapping, 0.0), lower, peak, upper)


def refine_support_rebased(support, mappings, eps=EPS):
    """重定基后的多轴精确展开: 返回 (C, terms)。

    C  = Π_axis φ_axis(T_axis(0)) —— 该元组在合并默认位置的值, 必须并进
         **默认 master** (glyf 轮廓增量 + 幽灵点算出的 hmtx 等)。
    terms 之和 = Π_axis φ_axis(T_axis(x)) - C, 且每一项都是合法 OT hat
    (峰值 ≠ 0、不跨 0), 在合并默认位置取值 0。

    分解用包含-排除恒等式 (a_i = φ_i(T_i(x_i)), c_i = φ_i(T_i(0))):

        Π a_i - Π c_i = Σ_{∅≠S} [Π_{i∈S} (a_i - c_i)] · [Π_{j∉S} c_j]

    右边每个 S 项都是"逐轴函数之积", 可以逐轴细化后做笛卡尔积; 含 c_j = 0
    的 S 项直接为零被剪掉 —— 源/合并默认点重合时 (c_j ≡ 0) 只剩 S = 全轴,
    退化成普通的逐轴细化。
    """
    # OT 语义: 峰值 0 或跨 0 的支撑轴会被引擎忽略 (supportScalar)
    axes = []
    for tag in support:
        lower, peak, upper = support[tag]
        if peak == 0.0 or (lower < 0.0 < upper):
            continue
        axes.append((tag, support[tag]))
    if not axes:
        return 1.0, []
    c = {}
    for tag, (lower, peak, upper) in axes:
        mapping = mappings.get(tag)
        if mapping is None:
            raise KeyError("合并空间缺少轴 %r, 无法重参数化" % tag)
        rlo, rhi = reachable_range(mapping)
        if upper <= rlo + EPS or lower >= rhi - EPS:
            # 该轴在本字体里根本到不了这个支撑 → 整个 tuple 恒 0
            return 0.0, []
        c[tag] = axis_support_at_default(tag, (lower, peak, upper), mapping)
    constant = 1.0
    for v in c.values():
        constant *= v

    out = []
    n = len(axes)
    for mask in range(1, 1 << n):
        picked = [axes[i] for i in range(n) if mask & (1 << i)]
        rest = [axes[i] for i in range(n) if not (mask & (1 << i))]
        scale = 1.0
        for tag, _ in rest:
            scale *= c[tag]
        if abs(scale) <= eps:
            continue                      # 该项恒为 0
        per_axis = []
        for tag, (lower, peak, upper) in picked:
            mapping = mappings[tag]
            terms = refine_1d(lower, peak, upper, mapping, eps, shift=c[tag])
            if not terms:                 # 该轴上 a_i ≡ c_i (常量) → 该项为 0
                per_axis = []
                break
            per_axis.append((tag, terms))
        if not per_axis:
            continue
        for combo in itertools.product(*[terms for _, terms in per_axis]):
            sup = {}
            weight = scale
            for (tag, _), (l, p, u, w) in zip(per_axis, combo):
                sup[tag] = (l, p, u)
                weight *= w
            if abs(weight) > eps:
                out.append((sup, weight))
    return constant, out


def evaluate_supports(loc_norm, terms):
    """Σ weight · supportScalar(loc) —— 用于自检细化是否精确"""
    total = 0.0
    for support, weight in terms:
        total += weight * support_value(loc_norm, support)
    return total


def fvar_triples(font):
    return {a.axisTag: (a.minValue, a.defaultValue, a.maxValue)
            for a in font["fvar"].axes}


def avar_segments(font):
    """{tag: {from: to}}; 无 avar 表返回 {}"""
    if "avar" not in font:
        return {}
    return {tag: dict(pts) for tag, pts in (font["avar"].segments or {}).items()}
