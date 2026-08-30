"""WOFF/WOFF2 解包"""
from fontTools.ttLib import TTFont


def unwrap_webfont(path):
    font = TTFont(path)
    font.flavor = None
    return font
