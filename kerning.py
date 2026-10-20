"""Ajuste entre pares de letras (kerning) leído de la tabla GPOS de la fuente.

Pillow sin libraqm no aplica el kerning GPOS, y en fuentes cursivas condensadas se nota
(por ejemplo "FIL TRADO"). Aquí se lee la tabla una vez y se consulta por par de caracteres.
"""
from __future__ import annotations

from functools import lru_cache

from fontTools.ttLib import TTFont


class _Kerner:
    def __init__(self, path: str):
        font = TTFont(path, lazy=True)
        self.upm = font["head"].unitsPerEm
        self.cmap = font.getBestCmap()
        self.subtables = []
        if "GPOS" in font:
            for lookup in font["GPOS"].table.LookupList.Lookup:
                for st in lookup.SubTable:
                    if lookup.LookupType == 9:  # extensión: la subtabla real va dentro
                        if st.ExtensionLookupType != 2:
                            continue
                        st = st.ExtSubTable
                    elif lookup.LookupType != 2:
                        continue
                    self.subtables.append(st)

    @lru_cache(maxsize=4096)
    def units(self, a: str, b: str) -> int:
        ga, gb = self.cmap.get(ord(a)), self.cmap.get(ord(b))
        if not ga or not gb:
            return 0
        for st in self.subtables:
            if ga not in st.Coverage.glyphs:
                continue
            if st.Format == 1:
                idx = st.Coverage.glyphs.index(ga)
                for rec in st.PairSet[idx].PairValueRecord:
                    if rec.SecondGlyph == gb:
                        return getattr(rec.Value1, "XAdvance", 0) or 0
            elif st.Format == 2:
                c1 = st.ClassDef1.classDefs.get(ga, 0)
                c2 = st.ClassDef2.classDefs.get(gb, 0)
                value = st.Class1Record[c1].Class2Record[c2].Value1
                adv = getattr(value, "XAdvance", 0) or 0
                if adv:
                    return adv
        return 0


@lru_cache(maxsize=None)
def _kerner(path: str) -> _Kerner:
    return _Kerner(path)


def kern(path: str, size_px: float, a: str, b: str) -> float:
    """Ajuste en píxeles entre los caracteres a y b para una fuente de size_px."""
    k = _kerner(path)
    return k.units(a, b) * size_px / k.upm
