# FontMerger/format - 格式处理模块
from .converter import glyf_to_cff, cff_to_glyf, convert_font_format
from .subsetter import create_glyph_subset
from .static_extract import variable_to_static
from .webfont import unwrap_webfont
