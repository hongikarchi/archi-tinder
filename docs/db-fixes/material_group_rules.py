"""material_visual (free text) -> material_group (12 controlled values).

Source of truth for the material grouping proposed in docs/db-data-quality-handoff.md §3.
material_group_map.csv is generated from this file; regenerate it rather than editing it.
One free-text value may map to several groups ("glass and steel" -> glass, metal) or to none
("unspecified", "painted surfaces"). Word-boundary regexes avoid substring false matches
(tile/textile, earth/hearth, glass/fiberglass).

Regenerate the map from the live distinct values (one value per line on stdin):
    psql "$DSN" -Atc "SELECT DISTINCT e FROM canonical_v2_buildings, unnest(material_visual) e" \
      | python material_group_rules.py > material_group_map.csv
"""
import csv
import re
import sys

GROUPS = ["wood", "metal", "concrete", "stone", "brick", "plaster", "tile",
          "earth", "glass", "fabric", "plastic", "other"]

_W = lambda *alts: re.compile(r"\b(?:" + "|".join(alts) + r")\b")

RULES = {
    "wood": _W(r"wood(?:en|s|work)?", r"\w*wood", r"timbers?", r"plywood", r"oak", r"bamboo", r"larch",
               r"pine", r"birch", r"cedar", r"walnut", r"teak", r"ash (?:wood|timber|veneer)", r"beech",
               r"maple", r"spruce", r"fir", r"chestnut", r"cypress", r"mahogany", r"hardwood", r"softwood",
               r"parquet", r"glulam", r"clt", r"cross[- ]laminated", r"osb", r"mdf", r"veneers?",
               r"decking", r"joinery", r"millwork", r"carpentry", r"rattan", r"wicker", r"lumber"),
    "metal": _W(r"metals?", r"metallic", r"\w*steel", r"alumin(?:i)?um", r"iron", r"brass", r"copper",
                r"bronze", r"zinc", r"cor-?ten", r"titanium", r"gold", r"chrome", r"rebar",
                r"shipping containers?", r"tin"),
    "concrete": _W(r"concrete", r"\w*cement", r"shotcrete", r"cinder ?blocks?", r"breeze ?blocks?",
                   r"precast"),
    "stone": _W(r"\w*stones?", r"marble", r"granite", r"travertine", r"slate", r"basalt", r"rocks?",
                r"gravel", r"cobbles?", r"pebbles?", r"quartzite", r"onyx", r"porphyry", r"tuff",
                r"lava", r"flint"),
    "brick": _W(r"brick\w*", r"masonry", r"terra-?cotta", r"clinker"),
    "plaster": _W(r"plaster\w*", r"stucco", r"render(?:ed)?", r"drywall", r"gypsum", r"lime(?:wash)?"),
    "tile": _W(r"til(?:e|es|ed|ing)", r"ceramics?", r"terrazzo", r"mosaics?", r"porcelain", r"majolica",
               r"azulejos?", r"stoneware", r"faience", r"zellige"),
    "earth": _W(r"earth(?:en)?", r"adobe", r"clay", r"mud", r"cob"),
    "glass": _W(r"glass", r"glazing", r"curtain[- ]walls?", r"mirror(?:s|ed)?"),
    "fabric": _W(r"fabrics?", r"textiles?", r"curtains?(?![- ]walls?)", r"canvas", r"linen", r"velvet", r"felt",
                 r"upholstery", r"carpet(?:s|ing)?", r"rugs?", r"cotton", r"(?<!wood )wool", r"silk(?!-?screen)", r"ropes?"),
    "plastic": _W(r"plastics?", r"polycarbonate", r"acrylic", r"resin", r"fib(?:er|re)glass", r"rubber",
                  r"linoleum", r"vinyl", r"pvc", r"corian", r"epoxy", r"polyethylene", r"etfe",
                  r"perspex", r"plexiglass?"),
    "other": _W(r"paper", r"cardboard", r"thatch(?:ed)?", r"straw", r"reeds?", r"leather", r"cork",
                r"asphalt", r"composites?"),
}

# Whole value is not a material even if a keyword appears ("pine trees", "urban fabric").
NOT_MATERIAL = _W(r"trees?", r"forest", r"grove",
                  r"(?:urban|historic\w*|building|existing|city|mill|factory|bathroom|architectural|"
                  r"heritage|original|old)\b[\w\s-]*\bfabric")
# "glass" inside fiberglass/plexiglass is plastic, not glass.
_FAKE_GLASS = _W(r"fib(?:er|re)glass", r"plexiglass?")


def classify(value: str) -> list[str]:
    v = value.lower().strip()
    if NOT_MATERIAL.search(v):
        return []
    hit = [g for g in GROUPS if RULES[g].search(v)]
    if "glass" in hit and _FAKE_GLASS.search(v) and not re.search(r"\bglass\b", _FAKE_GLASS.sub("", v)):
        hit.remove("glass")
    if "stone" in hit and re.search(r"\bstoneware\b", v) and not re.search(r"\bstones?\b", v):
        hit.remove("stone")
    if "brick" in hit and "glass" in hit and re.search(r"\bglass (?:bricks?|blocks?)\b", v):
        hit.remove("brick")
    # "stone masonry" is stone, not brick; "clay tile"/"clay brick" is tile/brick, not raw earth.
    if "brick" in hit and "stone" in hit and not re.search(r"brick|terra-?cotta|clinker", v):
        hit.remove("brick")
    if "earth" in hit and ("tile" in hit or "brick" in hit) and not re.search(r"earth|adobe|mud|cob\b", v):
        hit.remove("earth")
    return hit


def main() -> None:
    """stdin: one material_visual value per line -> stdout: CSV (material_value, material_group)."""
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", newline="")
    values = sorted({line.rstrip("\r\n") for line in sys.stdin if line.strip()})
    w = csv.writer(sys.stdout, lineterminator="\r\n")
    w.writerow(["material_value", "material_group"])
    for v in values:
        for g in classify(v):
            w.writerow([v, g])


if __name__ == "__main__":
    main()
