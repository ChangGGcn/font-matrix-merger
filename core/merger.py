"""FontMerger 主类 — 编排 16 种类型组合的合并流程"""
import copy
from io import BytesIO
from fontTools.ttLib import TTFont
from ..utils.detect import is_cff, is_ttf, is_variable, type_label
from ..format.converter import convert_font_format
from ..format.static_extract import variable_to_static
from ..format.subsetter import create_glyph_subset
from .conflict import resolve_conflicts, plan_alias
from .glyph_copy import merge_glyphs_via_ttx


def _diagnose_empty_merge(m, b, conflicts):
    """诊断为何合并没有新增字形，返回可读的原因"""
    from ..format.cid_convert import _is_cid_font
    mn = set(m.getGlyphOrder())
    bn = set(b.getGlyphOrder())

    # 情况1: 双CID字体字符集高度重叠
    if _is_cid_font(m) and _is_cid_font(b):
        overlap = mn & bn
        if len(overlap) > len(mn) * 0.5:
            return ("两个CID字体字符集高度重叠 (共同字形 {}/{}). "
                    "建议: 调换主/打底顺序, 或将其中一个转为name-keyed后再合并. "
                    "详见 fontTools issue #3890").format(len(overlap), len(mn))

    # 情况2: 打底字形的码位全部与主字体冲突
    if len(conflicts) > len(bn) * 0.9:
        return ("打底字体 {}/{} 字形与主字体码位或名称冲突. "
                "两个字体可能覆盖同一字符集, 合并无意义").format(len(conflicts), len(bn))

    # 情况3: 打底字形的名称全部已在主字体中
    if len(overlap := mn & bn) > len(bn) * 0.9:
        return ("打底字体 {}/{} 字形名已存在于主字体. "
                "可能为同一字体的不同版本").format(len(overlap), len(bn))

    # 情况4: 打底字形数很少
    if len(bn) <= 5:
        return "打底字体字形数过少 (≤5)"

    return "所有打底字形均被主字体覆盖或冲突"


def check_compatibility(main_font, base_font):
    """在合并前检查两个字体的兼容性, 返回 (ok: bool, warnings: list[str])"""
    warnings = []
    from ..format.cid_convert import _is_cid_font

    # CID + CID 同字符集
    if _is_cid_font(main_font) and _is_cid_font(base_font):
        mn = set(main_font.getGlyphOrder())
        bn = set(base_font.getGlyphOrder())
        overlap = mn & bn
        if len(overlap) > len(mn) * 0.5:
            warnings.append(
                "双CID字体: 字符集高度重叠 ({} 个CID名冲突). "
                "合并后新增字形可能为0. "
                "建议: 调换主/打底顺序, 或使用非CID字体作为主字体".format(len(overlap)))

    # 混合轮廓格式 (CFF + glyf)
    if is_cff(main_font) != is_cff(base_font):
        main_type = "CFF" if is_cff(main_font) else "glyf"
        base_type = "CFF" if is_cff(base_font) else "glyf"
        warnings.append(
            "混合轮廓格式: 主字体为{}, 打底为{}. 将自动转换打底字体".format(main_type, base_type))

    # 可变字体提醒: 走 merge_two 的可变路径时, 打底字体会被实例化为静态
    # (新增字形将失去轴变化) —— 这是**信息损失**, 必须明示。
    if is_variable(main_font):
        warnings.append(
            "主字体为可变字体: 默认路径保留主字体可变性, 但打底字形按默认实例合并 "
            "(新增字形不随轴变化); 同源分片请改用 merge_subsets()")
    if is_variable(base_font):
        warnings.append(
            "打底字体为可变字体: 将先实例化为静态再合并, 其字形不随轴变化; "
            "同源分片请改用 merge_subsets()")

    # UPM 不匹配
    main_upm = main_font["head"].unitsPerEm
    base_upm = base_font["head"].unitsPerEm
    if main_upm != base_upm:
        warnings.append(
            "UPM不匹配: 主字体{} vs 打底字体{}. 将自动缩放打底字体".format(main_upm, base_upm))

    return (len([w for w in warnings if "合并后新增字形可能为0" in w]) == 0, warnings)


def _remove_ros(font):
    """从 CFF 字体移除 ROS/FDSelect/FDArray, 转回 name-keyed"""
    if "CFF " not in font:
        return
    td = font["CFF "].cff.topDictIndex[0]
    if hasattr(td, 'ROS'):
        del td.ROS
    if hasattr(td, 'FDSelect'):
        del td.FDSelect
    if hasattr(td, 'FDArray') and td.FDArray and len(td.FDArray) > 0:
        if hasattr(td.FDArray[0], 'Private') and td.FDArray[0].Private:
            td.Private = td.FDArray[0].Private
        del td.FDArray


def _add_cid_prefix(font, prefix):
    """给 CID 字体的所有字形名加前缀，避免与另一个 CID 字体重名。
    同时移除 ROS/FDSelect 转回 name-keyed (消除 CFF 编译时的 CID 约束)。
    .notdef 保留原名。"""
    order = font.getGlyphOrder()
    mapping = {}
    for gn in order:
        if gn == ".notdef":
            mapping[gn] = gn  # 保留 .notdef
        else:
            mapping[gn] = prefix + gn
    new_order = [mapping[gn] for gn in order]

    cff_td = font["CFF "].cff.topDictIndex[0]
    cs = cff_td.CharStrings
    cs.charStrings = {mapping.get(k, k): v for k, v in cs.charStrings.items()}
    cff_td.charset = new_order
    font.setGlyphOrder(new_order)

    # 移除 CID 标记：转回 name-keyed CFF
    if hasattr(cff_td, 'ROS'):
        del cff_td.ROS
    if hasattr(cff_td, 'FDSelect'):
        del cff_td.FDSelect
    # 合并 Private (单 FD 字体)
    if hasattr(cff_td, 'FDArray') and cff_td.FDArray and len(cff_td.FDArray) > 0:
        if hasattr(cff_td.FDArray[0], 'Private') and cff_td.FDArray[0].Private:
            cff_td.Private = cff_td.FDArray[0].Private
        del cff_td.FDArray

    if "hmtx" in font:
        font["hmtx"].metrics = {mapping.get(k, k): v
                                for k, v in font["hmtx"].metrics.items()}
    if "vmtx" in font:
        font["vmtx"].metrics = {mapping.get(k, k): v
                                for k, v in font["vmtx"].metrics.items()}
    for table in font["cmap"].tables:
        if hasattr(table, "cmap") and table.cmap:
            for cp in list(table.cmap.keys()):
                gn = table.cmap[cp]
                table.cmap[cp] = mapping.get(gn, gn)
    if "maxp" in font:
        font["maxp"].numGlyphs = len(new_order)


def _normalize_upm(main_font, base_font):
    """如果 UPM 不同，将打底字体缩放为主字体的 UPM"""
    main_upm = main_font["head"].unitsPerEm
    base_upm = base_font["head"].unitsPerEm
    if main_upm == base_upm:
        return base_font

    from fontTools.ttLib.scaleUpem import scale_upem
    print(f"  [UPM] 缩放打底字体: {base_upm} → {main_upm}")
    scaled = copy.deepcopy(base_font)
    scale_upem(scaled, main_upm)
    return scaled


class FontMerger:
    def __init__(self):
        self.mem = {}

    def ask(self, key, q, opts=None):
        if key in self.mem:
            print(f"  [记忆] {q} → {self.mem[key]}")
            return self.mem[key]
        print(f"\n[询问] {q}")
        if opts:
            for i, o in enumerate(opts, 1):
                print(f"  {i}. {o}")
        while True:
            a = input("> ").strip()
            if opts:
                try:
                    n = int(a) - 1
                    if 0 <= n < len(opts):
                        self.mem[key] = opts[n]
                        return opts[n]
                except ValueError:
                    pass
                print(f"  请输入 1-{len(opts)}")
            else:
                self.mem[key] = a
                return a

    def merge_two(self, m, b):
        ms = not is_variable(m)
        mt = is_ttf(m)
        bs = not is_variable(b)
        bt = is_ttf(b)
        print(f"  主: {type_label(m)} | 打底: {type_label(b)}")

        if ms and not mt:
            if bs and not bt:       return self._sOTF_sOTF(m, b)
            if bs and bt:           return self._sOTF_sTTF(m, b)
            if not bs and not bt:   return self._sOTF_vOTF(m, b)
            if not bs and bt:       return self._sOTF_vTTF(m, b)
        if ms and mt:
            if bs and not bt:       return self._sTTF_sOTF(m, b)
            if bs and bt:           return self._sTTF_sTTF(m, b)
            if not bs and not bt:   return self._sTTF_vOTF(m, b)
            if not bs and bt:       return self._sTTF_vTTF(m, b)
        if not ms and not mt:
            if bs and not bt:       return self._vOTF_sOTF(m, b)
            if bs and bt:           return self._vOTF_sTTF(m, b)
            if not bs and not bt:   return self._vOTF_vOTF(m, b)
            if not bs and bt:       return self._vOTF_vTTF(m, b)
        if not ms and mt:
            if bs and not bt:       return self._vTTF_sOTF(m, b)
            if bs and bt:           return self._vTTF_sTTF(m, b)
            if not bs and not bt:   return self._vTTF_vOTF(m, b)
            if not bs and bt:       return self._vTTF_vTTF(m, b)

    def _do_merge(self, m, b):
        # ── 预处理 ──
        b = _normalize_upm(m, b)

        from ..format.cid_convert import _is_cid_font, ensure_cid_format, cid_to_name
        m_is_cid = _is_cid_font(m)
        b_is_cid = _is_cid_font(b)

        if m_is_cid and b_is_cid:
            # 双 CID: 仿 UFO CIDMap 重映射 — 打底 CID 偏移, 直接复制 CharString
            print("  [CID消歧] 双CID字体, 使用CID偏移+直接CharString复制")
            from ..format.cid_merge import cid_ufo_style_merge
            result = cid_ufo_style_merge(m, b)
            # cid_ufo_style_merge 已包含完整合并+save→reload, 直接返回
            # 但还需处理 OT 特性: 主字体优先
            for tag in ("GSUB", "GPOS", "GDEF"):
                if tag not in result and tag in m:
                    result[tag] = copy.deepcopy(m[tag])
            return result
        elif m_is_cid and not b_is_cid:
            # 主 CID + 打底 name-keyed: 打底转 CID → 走双 CID 路径 (主字体的 CID 结构保留)
            print("  [CID归一] 主字体为 CID: 打底 name→CID, 走双 CID 合并")
            from ..format.cid_convert import ensure_cid_format
            # 打底若是 glyf/TTF: 先转 CFF (cid_ufo_style_merge 是 CFF 专用)
            if not is_cff(b):
                b = convert_font_format(b, to_cff=True)
            _b = ensure_cid_format(b)
            if _b is not b:
                b = _b
            from ..format.cid_merge import cid_ufo_style_merge
            result = cid_ufo_style_merge(m, b)
            for tag in ("GSUB", "GPOS", "GDEF"):
                if tag not in result and tag in m:
                    result[tag] = copy.deepcopy(m[tag])
            return result
        elif not m_is_cid and b_is_cid:
            if "CFF2" in m:
                # 主 CFF2 (无 ROS, FD 体系保留): 打底 CID CFF 直接转 CFF2, 保留 FDArray
                print("  [CID归一] 主字体为CFF2: 打底 CID CFF→CFF2 (FD 保留, inject 时重映射)")
                from fontTools.cffLib.CFFToCFF2 import convertCFFToCFF2
                _b = copy.deepcopy(b)
                _b["CFF "].cff.desubroutinize()
                convertCFFToCFF2(_b)
                b = _b
            else:
                # 主是 name-keyed CFF: 打底转 name-keyed (避免主被强制 CID 后 FD 冲突)
                print("  [CID归一] 打底字体 CID→name (输出统一为 name-keyed)")
                b = cid_to_name(b)

        if is_cff(m) != is_cff(b):
            print("  [转换] 轮廓格式不同，自动转换打底字体...")
            b = convert_font_format(b, to_cff=is_cff(m))
        if is_cff(m) and is_cff(b):
            # CFF 版本对齐: 主 CFF2 参数化, 打底静态 CFF → 先转 CFF2 才能注入
            if "CFF2" in m and "CFF " in b:
                print("  [转换] CFF 版本对齐: 打底 CFF → CFF2 (配合主字体)")
                from fontTools.cffLib.CFFToCFF2 import convertCFFToCFF2
                _base = copy.deepcopy(b)
                _base["CFF "].cff.desubroutinize()
                convertCFFToCFF2(_base)
                b = _base
            elif "CFF " in m and "CFF2" in b:
                print("  [转换] CFF 版本对齐: 打底 CFF2 → CFF (配合主字体)")
                from fontTools.cffLib.CFF2ToCFF import _convertCFF2ToCFF
                from fontTools.ttLib.tables.C_F_F_ import table_C_F_F_
                _base = copy.deepcopy(b)
                _convertCFF2ToCFF(_base["CFF2"].cff, _base)
                cff_data = _base["CFF2"].cff
                del _base["CFF2"]
                cff_table = table_C_F_F_("CFF ")
                cff_table.cff = cff_data
                _base["CFF "] = cff_table
                b = _base

        # ── 冲突检测与合并 ──
        # 自动命名字形 (post 3.0 的 glyphNNNNN) 跨字体同名但不同源: 改名后加入
        alias = plan_alias(m, b)
        if alias:
            from .glyph_rename import renamed_copy
            print(f"  [改名] {len(alias)} 个自动命名字形重名, 加别名后加入")
            b = renamed_copy(b, alias)
        cf = resolve_conflicts(m, b)
        print(f"  [冲突] {len(cf)} 个字形")
        mn = set(m.getGlyphOrder())
        to_add = [gn for gn in b.getGlyphOrder()
                  if gn not in cf and gn not in mn]
        print(f"  [新增] {len(to_add)} 个字形")
        if not to_add:
            reason = _diagnose_empty_merge(m, b, cf)
            print(f"  [提示] 无新增字形 — {reason}")
            return copy.deepcopy(m)

        CHUNK_SIZE = 5000
        if len(to_add) > CHUNK_SIZE:
            return self._chunked_merge(m, b, to_add, CHUNK_SIZE)

        try:
            result = merge_glyphs_via_ttx(m, b, to_add)
            print(f"  合并后字形: {len(result.getGlyphOrder())}")
            # 合并打底 OT 特性 (修剪到仅与保留字形相关, 冲突以主为准)
            _merge_base_layout_once(result, b, to_add)
            return result
        except Exception as e:
            print(f"  [合并失败] {e}")
            return copy.deepcopy(m)

    def _chunked_merge(self, m, b, to_add, chunk_size):
        """分块合并: 将打底字体按 chunk_size 拆分, 逐块合并到主字体"""
        chunks = [to_add[i:i+chunk_size] for i in range(0, len(to_add), chunk_size)]
        print(f"  [分块] {len(chunks)} 块, 每块 ≤{chunk_size} 字形")
        current = m
        for i, chunk in enumerate(chunks):
            print(f"    块 {i+1}/{len(chunks)}: {len(chunk)} 字形...", end=" ", flush=True)
            try:
                current = merge_glyphs_via_ttx(current, b, chunk)
                print(f"→ {len(current.getGlyphOrder())} 字形")
            except Exception as e:
                print(f"失败: {e}")
                return current if len(current.getGlyphOrder()) > len(m.getGlyphOrder()) else copy.deepcopy(m)
        # 分块完成后统一合并打底 OT 特性一次
        _merge_base_layout_once(current, b, to_add)
        return current

    # ---- 静态+静态 ----
    def _sOTF_sOTF(self, m, b): return self._do_merge(m, b)
    def _sTTF_sTTF(self, m, b): return self._do_merge(m, b)
    def _sOTF_sTTF(self, m, b):
        self.ask("sOTF_sTTF", "导出为 TTF 还是 OTF？", ["OTF", "TTF"])
        return self._do_merge(m, b)
    def _sTTF_sOTF(self, m, b):
        self.ask("sTTF_sOTF", "导出为 TTF 还是 OTF？", ["TTF", "OTF"])
        return self._do_merge(m, b)

    # ---- 静态+可变 ----
    def _sOTF_vOTF(self, m, b): return self._do_merge(m, variable_to_static(b))
    def _sOTF_vTTF(self, m, b): return self._do_merge(m, variable_to_static(b))
    def _sTTF_vOTF(self, m, b): return self._do_merge(m, variable_to_static(b))
    def _sTTF_vTTF(self, m, b): return self._do_merge(m, variable_to_static(b))

    # ---- 可变OTF为主+静态打底 ----
    def _vOTF_sOTF(self, m, b):
        fmt = self.ask("vOTF_sOTF", "导出为可变/静态？", ["可变", "静态"])
        if fmt == "静态": return self._do_merge(variable_to_static(m), b)
        return self._do_merge(m, b)
    def _vOTF_sTTF(self, m, b):
        fmt = self.ask("vOTF_sTTF", "导出为可变/静态？", ["可变", "静态"])
        if fmt == "静态":
            self.ask("vOTF_sTTF2", "TTF/OTF？", ["TTF", "OTF"])
            return self._do_merge(variable_to_static(m), b)
        return self._do_merge(m, b)

    # ---- 可变TTF为主+静态打底 ----
    def _vTTF_sOTF(self, m, b):
        fmt = self.ask("vTTF_sOTF", "导出为可变/静态？", ["可变", "静态"])
        if fmt == "静态":
            self.ask("vTTF_sOTF2", "TTF/OTF？", ["TTF", "OTF"])
            return self._do_merge(variable_to_static(m), b)
        return self._do_merge(m, b)
    def _vTTF_sTTF(self, m, b):
        fmt = self.ask("vTTF_sTTF", "导出为可变/静态？", ["可变", "静态"])
        if fmt == "静态": return self._do_merge(variable_to_static(m), b)
        return self._do_merge(m, b)

    # ---- 可变+可变 ----
    def _vOTF_vOTF(self, m, b):
        m = self._axis_union(m, b)
        return self._do_merge(m, variable_to_static(b))
    def _vOTF_vTTF(self, m, b):
        self.ask("vOTF_vTTF", "OTF/TTF？", ["OTF", "TTF"])
        m = self._axis_union(m, b)
        return self._do_merge(m, variable_to_static(b))
    def _vTTF_vOTF(self, m, b):
        self.ask("vTTF_vOTF", "TTF/OTF？", ["TTF", "OTF"])
        m = self._axis_union(m, b)
        return self._do_merge(m, variable_to_static(b))
    def _vTTF_vTTF(self, m, b):
        m = self._axis_union(m, b)
        return self._do_merge(m, variable_to_static(b))

    @staticmethod
    def _axis_union(m, b):
        """主 VF 轴空间与打底 VF 轴空间取并集 (在原始 VF 上操作)"""
        if is_variable(m) and is_variable(b):
            from ..format.vf_axes import union_axes
            union_axes(m, b)
        return m


def _merge_base_layout_once(result, base_font, to_add):
    """在最终合并结果上统一做一次打底 OT 特性合并 (避免分块重复追加)"""
    try:
        from ..tables.ot_merge import merge_ot_features
        merge_ot_features(result, base_font, list(to_add))
    except Exception as e:
        print(f"  [OT合并] 跳过打底布局合并: {e}")
