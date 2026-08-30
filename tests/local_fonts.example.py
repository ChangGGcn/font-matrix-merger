# -*- coding: utf-8 -*-
"""本地授权字体映射（仅本地开发机存在，已 gitignore，不入库）。

仓库不随附任何字体文件；测试用商业授权字体的真实文件名/路径只出现在
本文件中，提交到公开仓库时会被 .gitignore 排除。
OFL 公开字体的路径直接写在各测试脚本内（可自由分发）。

覆盖的角色缺省情况：未配置时对应测试用例自动 SKIP。
复制本文件为 local_fonts.py，并为下列角色填入你本地的字体相对路径
（相对 tests/../test 目录）即可启用。
"""

LOCAL_FONTS = {
    # 商业授权静态 CJK OTF 主/打底字体
    # "cjk_static_otf": "OpenType/<your_cjk_otf>.otf",
    # 商业授权静态 CJK TTF 主/打底字体
    # "cjk_static_ttf": "TrueType/<your_cjk_ttf>.ttf",
    # 商业授权静态 CJK TTF（混合格式样例用）
    # "cjk_ttf_hanyi": "TrueType/<your_cjk_ttf2>.ttf",
    # 符号字体（VF 实例化合并样例用）
    # "symbols_otf": "otf_variable_fonts/<your_symbols>.otf",
    # 商业授权可变 TTF（拉丁 VF 样例用）
    # "vf_ttf_helvetica": "ttf_variable_fonts/<your_vf_ttf>.ttf",
}
