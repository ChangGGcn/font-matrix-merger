"""逐级保持 TrueType 指令与全局解释器的一致性。

仅处理实际并入的 glyf 字形；主字体及前一级已保留字形永不换解释器。
无法证明兼容时仅剥离新字形指令，明确告警，不改变输入字体。
"""
import copy

from fontTools.ttLib.tables.ttProgram import Program

from ..tables.maxp import (_GLOBAL_HINT_TABLES, _hint_axis_space,
                           _merge_hint_resources,
                           _program_bytes, _same_hint_environment)


def _strip_programs(font, names):
    """就地清理指定新字形的指令，不碰旧字形。"""
    for name in names:
        glyph = font["glyf"][name]
        if hasattr(glyph, "program"):
            program = Program()
            program.fromBytecode([])
            glyph.program = program


def apply_hinting_policy(result, main, base, added):
    """注入后就地协调 hinting；added 必须是实际字形差集（含组件）。

    Args:
        result: 已复制轮廓的 TTFont；只修改此对象。
        main: 本级注入前主字体，包含前一级已保留的字形/解释器。
        base: 本级实际复制字形的打底字体（已改名、缩放、实例化）。
        added: result 与 main 的实际字形差集，不是候选 to_add。
    Returns:
        None；兼容时资源取最大，不明安全性时剥离新字形指令。
    """
    if "glyf" not in result or "glyf" not in base:
        return
    old_names = set(main.getGlyphOrder())
    names = (set(added) & set(result.getGlyphOrder()) &
             set(base.getGlyphOrder())) - old_names
    if not names:
        return
    hinted = list(names)
    adopted = []
    try:
        hinted = [name for name in names if _program_bytes(result, name)]
        if not hinted:
            return
        compatible = _same_hint_environment(result, base)
        has_old_hints = any(_program_bytes(result, name)
                            for name in old_names)
        has_old_globals = any(tag in result for tag in
                              _GLOBAL_HINT_TABLES + ("cvar",))
        can_adopt = not has_old_hints and not has_old_globals
        if compatible:
            _merge_hint_resources(result, [main, base])
            print("  [指令] %d 个新增字形使用兼容全局程序，资源取最大" %
                  len(hinted))
        elif (can_adopt and "cvar" not in base and
              _hint_axis_space(result) == _hint_axis_space(base)):
            # 只有旧字体连 prep 都没有，才能排除其对新增指令的影响。
            bundle = {tag: copy.deepcopy(base[tag])
                      for tag in _GLOBAL_HINT_TABLES if tag in base}
            for tag, table in bundle.items():
                result[tag] = table
                adopted.append(tag)
            _merge_hint_resources(result, [main, base])
            print("  [指令警告] 旧字体无全局程序及字形指令，整体采用打底程序；"
                  "其 prep 可能改变旧字形栅格状态")
        else:
            _strip_programs(result, hinted)
            print("  [指令警告] 全局环境不兼容或安全性未知，保留主程序，"
                  "剥离 %d 个新增字形的指令" % len(hinted))
    except Exception as error:
        for tag in adopted:
            del result[tag]
        _strip_programs(result, hinted)
        print("  [指令警告] 环境核验失败，剥离 %d 个新增字形指令: %s" %
              (len(hinted), error))
    if "gasp" in result and "gasp" in base:
        if result["gasp"].gaspRange != base["gasp"].gaspRange:
            print("  [指令警告] gasp 策略不同，保留主字体渲染设置")
