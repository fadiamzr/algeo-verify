"""Quick test script for the normalization engine."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from app.services.normalization import normalize

test_cases = [
    ("French noise removal", "  wilaya de   Oran ,  commune de   Bir El Djir  31000 "),
    ("Arabic wilaya \u2192 French", "\u0648\u0647\u0631\u0627\u0646"),  # وهران
    ("Arabic Alger", "\u0627\u0644\u062c\u0632\u0627\u0626\u0631"),  # الجزائر
    ("Arabic Annaba", "\u0639\u0646\u0627\u0628\u0629"),  # عنابة
    ("Arabic Constantine", "\u0642\u0633\u0646\u0637\u064a\u0646\u0629"),  # قسنطينة
    ("Arabic Tlemcen", "\u062a\u0644\u0645\u0633\u0627\u0646"),  # تلمسان
    ("Uppercase French", "COMMUNE DE CONSTANTINE, WILAYA DE CONSTANTINE"),
    ("Duplicate punctuation", "123  rue des freres bouadou ,, blida  09000"),
    ("Space before comma", "Oran , Blida"),
    ("Empty string", ""),
    ("Whitespace only", "   "),
    ("Garbage input", "$$$$"),
    ("Mixed AR+FR", "\u0642\u0633\u0646\u0637\u064a\u0646\u0629 , daira de EL KHROUB"),
]

print("=" * 70)
print("  Normalization Engine \u2014 Test Results")
print("=" * 70)

for label, raw in test_cases:
    result = normalize(raw)
    print(f"\n  [{label}]")
    print(f"    IN : {raw!r}")
    print(f"    OUT: {result!r}")

print("\n" + "=" * 70)
print("  Done \u2014 all test cases processed.")
print("=" * 70)
