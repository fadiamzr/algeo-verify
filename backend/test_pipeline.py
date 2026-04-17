"""
Algeo Verify — Pipeline Test (Clean Output)
Run: py test_pipeline.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.normalization import normalize
from app.services.detection import detectEntities
from app.services.scoring import ScoringEngine
from app.services.geocoding import geocode_address
from app.config import get_settings

settings = get_settings()
scorer = ScoringEngine()

ai_available = False
try:
    if settings.AI_ENABLED and settings.GEMINI_API_KEY:
        from app.services.ai_preprocessor import preprocess_address, build_clean_address
        ai_available = True
except:
    pass

test_cases = [
    # Level 1 — Clean
    ("Clean FR", "123 Rue Didouche Mourad, Constantine 25000"),
    ("Clean FR", "45 Boulevard Zighoud Youcef, Setif 19000"),
    ("Clean AR", "شارع العربي بن مهيدي وهران 31000"),
    ("Clean AR", "عنابة 23000"),
    # Level 2 — Mixed
    ("Mixed", "حي 500 مسكن، باب الواد، الجزائر 16001"),
    ("Mixed", "Cité 1000 logements, Bir El Djir, Oran"),
    ("Mixed", "BLIDA, BOUFARIK 09001"),
    # Level 3 — Informal
    ("Informal", "en face lycée Lotfi, hai es salam, Batna"),
    ("Informal", "derriere la poste centrale, hai el nasr setif"),
    ("Informal", "a coté du stade 5 juillet belouizdad"),
    # Level 4 — Darja
    ("Darja", "hdart l'hopital 3la lissr dour limine wahran"),
    ("Darja", "3and boucherie lhadjj derb sidi el houari wahran"),
    ("Darja", "wust l bled b3id 3la superette yamina tlemcen"),
    ("Darja", "3la trig l'aeroport gbal station naftal chlef"),
]

print("=" * 78)
print("  ALGEO VERIFY — PIPELINE TEST")
print(f"  AI: {'ON' if ai_available else 'OFF'}  |  Geocoding: {'ON' if settings.GEOCODING_ENABLED else 'OFF'}")
print("=" * 78)
print(f"  {'#':<3} {'Level':<10} {'Score':>5}  {'AI':>3}  {'W':>1} {'C':>1} {'P':>1} {'S':>1}  {'Geo':<5}  Input → Normalized")
print(f"  {'─'*3} {'─'*10} {'─'*5}  {'─'*3}  {'─'*1} {'─'*1} {'─'*1} {'─'*1}  {'─'*5}  {'─'*40}")

results = []

for i, (level, addr) in enumerate(test_cases, 1):
    # AI
    ai_used = False
    feed = addr
    if ai_available:
        try:
            ai_result = preprocess_address(addr)
            if ai_result:
                clean = build_clean_address(ai_result)
                if clean:
                    feed = clean
                    ai_used = True
        except:
            pass

    # Normalize + Detect + Score
    normed = normalize(feed)
    entities = detectEntities(normed)
    score, flags = scorer.computeScore(entities)

    # Geocode
    geo_status = "—"
    if settings.GEOCODING_ENABLED:
        geo = geocode_address(normed, wilaya=entities.wilaya, commune=entities.commune)
        geo_status = geo.get("status", "fail")[:5]

    w = "✓" if entities.wilaya else "✗"
    c = "✓" if entities.commune else "✗"
    p = "✓" if entities.postalCode else "✗"
    s = "✓" if entities.street else "✗"
    ai_mark = "✓" if ai_used else "—"
    score_pct = f"{score*100:.0f}%"

    short_input = addr[:30] + "…" if len(addr) > 30 else addr
    short_norm = normed[:30] + "…" if len(normed) > 30 else normed

    print(f"  {i:<3} {level:<10} {score_pct:>5}  {ai_mark:>3}  {w} {c} {p} {s}  {geo_status:<5}  {short_input} → {short_norm}")

    results.append({"score": score, "ai": ai_used, "geo": geo_status not in ("fail", "—"), "flags": [f.label for f in flags]})

    time.sleep(4.5 if ai_available else 1.2)

# Summary
scores = [r["score"] for r in results]
avg = sum(scores) / len(scores)
ai_scores = [r["score"] for r in results if r["ai"]]
no_ai_scores = [r["score"] for r in results if not r["ai"]]
geocoded = sum(1 for r in results if r["geo"])

print(f"\n{'=' * 78}")
print(f"  SUMMARY")
print(f"{'=' * 78}")
print(f"  Addresses tested:  {len(results)}")
print(f"  Average score:     {avg*100:.1f}%")
print(f"  Perfect (100%):    {sum(1 for s in scores if s >= 1.0)}")
print(f"  High (75-99%):     {sum(1 for s in scores if 0.75 <= s < 1.0)}")
print(f"  Medium (45-74%):   {sum(1 for s in scores if 0.45 <= s < 0.75)}")
print(f"  Low (<45%):        {sum(1 for s in scores if s < 0.45)}")
print(f"  Geocoded:          {geocoded}/{len(results)}")

if ai_scores and no_ai_scores:
    ai_avg = sum(ai_scores) / len(ai_scores)
    no_ai_avg = sum(no_ai_scores) / len(no_ai_scores)
    print(f"\n  AI IMPACT:")
    print(f"    With AI:     {ai_avg*100:.1f}% avg  ({len(ai_scores)} addresses)")
    print(f"    Without AI:  {no_ai_avg*100:.1f}% avg  ({len(no_ai_scores)} addresses)")
    print(f"    Improvement: {(ai_avg - no_ai_avg)*100:+.1f}%")

low_scores = [(i+1, r) for i, r in enumerate(results) if r["score"] < 0.45]
if low_scores:
    print(f"\n  ⚠️  LOW SCORES:")
    for idx, r in low_scores:
        print(f"    #{idx}: {r['score']*100:.0f}% — {', '.join(r['flags'])}")
else:
    print(f"\n  ✅ All addresses scored 45% or above!")

print(f"\n{'=' * 78}")