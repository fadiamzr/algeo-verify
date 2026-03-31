r"""
Final test suite for normalization + detection engines.
Run from backend/:
    C:\Users\User\Desktop\algeo_verify\.venv\Scripts\python.exe test_services.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from app.services.normalization import normalize
from app.services.detection import detectEntities, DetectedEntities

passed = 0
failed = 0


def check(label, actual, expected):
    global passed, failed
    if actual == expected:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}")
        print(f"        expected: {expected!r}")
        print(f"        got:      {actual!r}")


# ================================================================
#   NORMALIZATION TESTS
# ================================================================
print("=" * 64)
print("  NORMALIZATION TESTS")
print("=" * 64)

# 1 - Whitespace + punctuation cleanup (space before comma removed)
check("strip whitespace + comma fix",
      normalize("  Oran ,  Bir El Djir  "),
      "Oran, Bir el Djir")

# 2 - Arabic comma normalized
check("arabic comma",
      normalize("Oran\u060c Blida"),
      "Oran, Blida")

# 3 - Duplicate punctuation + space before comma
check("duplicate commas",
      normalize("Oran ,, Blida"),
      "Oran, Blida")

# 4 - Arabic wilaya to French (all 5 major ones)
check("AR->FR: \u0648\u0647\u0631\u0627\u0646 -> Oran",
      normalize("\u0648\u0647\u0631\u0627\u0646"),
      "Oran")

check("AR->FR: \u0627\u0644\u062c\u0632\u0627\u0626\u0631 -> Alger",
      normalize("\u0627\u0644\u062c\u0632\u0627\u0626\u0631"),
      "Alger")

check("AR->FR: \u0639\u0646\u0627\u0628\u0629 -> Annaba",
      normalize("\u0639\u0646\u0627\u0628\u0629"),
      "Annaba")

check("AR->FR: \u0642\u0633\u0646\u0637\u064a\u0646\u0629 -> Constantine",
      normalize("\u0642\u0633\u0646\u0637\u064a\u0646\u0629"),
      "Constantine")

check("AR->FR: \u062a\u0644\u0645\u0633\u0627\u0646 -> Tlemcen",
      normalize("\u062a\u0644\u0645\u0633\u0627\u0646"),
      "Tlemcen")

# 5 - Noise removal
check("remove 'wilaya de'",
      normalize("wilaya de Oran"),
      "Oran")

check("remove 'commune de'",
      normalize("commune de Constantine"),
      "Constantine")

check("remove 'daira de'",
      normalize("da\u00efra de El Khroub"),
      "El Khroub")

# 6 - Title case
check("title case UPPERCASE",
      normalize("CONSTANTINE"),
      "Constantine")

check("title case preserves particles",
      normalize("BIR EL DJIR"),
      "Bir el Djir")

# 7 - Empty / whitespace
check("empty string",
      normalize(""),
      "")

check("whitespace only",
      normalize("   "),
      "")

# 8 - Garbage input
check("garbage input",
      normalize("$$$$"),
      "$$$$")

check("digits only",
      normalize("12345"),
      "12345")

print()

# ================================================================
#   DETECTION TESTS
# ================================================================
print("=" * 64)
print("  DETECTION TESTS")
print("=" * 64)

# Test 1 - Good address: Didouche Mourad must NOT be commune
r = detectEntities(normalize("123 rue Didouche Mourad, Constantine 25000"))
check("good addr: wilaya",    r.wilaya,     "Constantine")
check("good addr: commune",   r.commune,    "Constantine")
check("good addr: postal",    r.postalCode, "25000")
check("good addr: street",    r.street,     "123 Rue Didouche Mourad")

# Test 2 - Missing wilaya name, only postal code
r = detectEntities(normalize("16000"))
check("postal only: wilaya",  r.wilaya,     "Alger")
check("postal only: postal",  r.postalCode, "16000")

# Test 3 - Arabic input
r = detectEntities(normalize("\u0639\u0646\u0627\u0628\u0629 23000"))
check("arabic addr: wilaya",  r.wilaya,     "Annaba")
check("arabic addr: postal",  r.postalCode, "23000")

# Test 4 - Commune detection with wilaya
r = detectEntities(normalize("Oran, Bir El Djir 31003"))
check("commune: wilaya",      r.wilaya,     "Oran")
check("commune: commune",     r.commune,    "Bir El Djir")
check("commune: postal",      r.postalCode, "31003")

# Test 5 - Bab El Oued should NOT match wilaya El Oued
r = detectEntities(normalize("Bab El Oued, Alger 16001"))
check("bab el oued: wilaya",  r.wilaya,     "Alger")
check("bab el oued: commune", r.commune,    "Bab El Oued")
check("bab el oued: postal",  r.postalCode, "16001")

# Test 6 - Two commune names, prefer non-wilaya one
r = detectEntities(normalize("\u062a\u0644\u0645\u0633\u0627\u0646 , Maghnia"))
check("prefer commune: wilaya",  r.wilaya,  "Tlemcen")
check("prefer commune: commune", r.commune, "Maghnia")

# Test 7 - Blida / Boufarik
r = detectEntities(normalize("BLIDA, BOUFARIK 09001"))
check("blida: wilaya",        r.wilaya,     "Blida")
check("blida: commune",       r.commune,    "Boufarik")
check("blida: postal",        r.postalCode, "09001")

# Test 8 - Empty input
r = detectEntities(normalize(""))
check("empty: wilaya",        r.wilaya,     None)
check("empty: commune",       r.commune,    None)
check("empty: postal",        r.postalCode, None)
check("empty: street",        r.street,     None)

# Test 9 - None-like / garbage input
r = detectEntities("")
check("empty str direct: wilaya", r.wilaya, None)

r = detectEntities("$$$$")
check("garbage: wilaya",      r.wilaya,     None)
check("garbage: commune",     r.commune,    None)
check("garbage: postal",      r.postalCode, None)

# Test 10 - Mixed Arabic + French
r = detectEntities(normalize("\u0642\u0633\u0646\u0637\u064a\u0646\u0629, El Khroub"))
check("mixed ar+fr: wilaya",  r.wilaya,     "Constantine")
check("mixed ar+fr: commune", r.commune,    "El Khroub")

# Test 11 - S\u00e9tif with street
r = detectEntities(normalize("45 boulevard de l'ALN, S\u00e9tif 19000"))
check("setif: wilaya",        r.wilaya,     "S\u00e9tif")
check("setif: postal",        r.postalCode, "19000")
check("setif: street",        r.street,     "45 Boulevard de L'Aln")

# Test 12 - DetectedEntities structure
check("DetectedEntities is dataclass",
      hasattr(DetectedEntities, "__dataclass_fields__"), True)

check("DetectedEntities has 4 fields",
      len(DetectedEntities.__dataclass_fields__), 4)

# ================================================================
#   SUMMARY
# ================================================================
print()
print("=" * 64)
if failed == 0:
    print(f"  ALL {passed} TESTS PASSED  --  ready to push!")
else:
    print(f"  {passed} passed, {failed} FAILED  --  fix before pushing")
print("=" * 64)

sys.exit(0 if failed == 0 else 1)
