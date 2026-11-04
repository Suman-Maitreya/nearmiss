"""Generate a grounded 'AI Pattern Insight' narrative across the critical
near-miss events, for the Cockpit UI.

Honesty design (important -- read before changing):
  All statistics (counts, medians, vehicle-type breakdown, flag themes) are
  computed in PLAIN PYTHON from the real database, not by the model. Muse
  Spark is given those already-computed numbers plus the real stored
  `spark_observation` text per event, and is told explicitly not to invent
  any new number. Its only job is to turn real, pre-computed facts into
  readable prose + 3 grounded bullets. We then sanity-check every number
  that appears in its output against the numbers we actually gave it, and
  flag (not silently drop) anything that doesn't match, so a human reviews
  before it ships.

Safe to rerun -- it always regenerates runs/critical_insight.json fresh
from current DB state (cheap, no images, single text-only API call).

Run from the repo root in your activated venv (same one with MODEL_API_KEY set):
    python scripts\\generate_critical_insight.py
"""
import os, re, json, sqlite3, datetime, statistics, collections
import pandas as pd
from openai import OpenAI

DB = r"D:\META\nearmiss\nearmiss.db"
OUT_PATH = r"D:\META\nearmiss\runs\critical_insight.json"

client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])

con = sqlite3.connect(DB)
df = pd.read_sql_query("""
    SELECT event_id, scene, ped_id, veh_id, our_pet_s, vehicle_type,
           spark_status, spark_flags, spark_observation, human_review_status
    FROM events WHERE severity='critical'
    ORDER BY our_pet_s
""", con)
con.close()

if len(df) == 0:
    raise SystemExit("No critical events found -- nothing to summarize.")

n = len(df)
pets = df["our_pet_s"].dropna().tolist()
vehicle_counts = collections.Counter(df["vehicle_type"].fillna("unknown"))
spark_status_counts = collections.Counter(df["spark_status"].fillna("not_yet_reviewed"))
review_status_counts = collections.Counter(df["human_review_status"].fillna("pending"))

flag_counter = collections.Counter()
for raw in df["spark_flags"].dropna():
    try:
        flags = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        continue
    for f in flags:
        flag_counter[f] += 1

stats = {
    "n_critical_events": n,
    "pet_median_s": round(statistics.median(pets), 2) if pets else None,
    "pet_min_s": round(min(pets), 2) if pets else None,
    "pet_max_s": round(max(pets), 2) if pets else None,
    "vehicle_type_counts": dict(vehicle_counts),
    "spark_status_counts": dict(spark_status_counts),
    "human_review_status_counts": dict(review_status_counts),
    "common_flag_themes": dict(flag_counter),
}

per_event_lines = []
for _, r in df.iterrows():
    obs = (r["spark_observation"] or "").strip()
    per_event_lines.append(
        f"- {r['event_id']} | PET={r['our_pet_s']}s | vehicle={r['vehicle_type']} | "
        f"spark_status={r['spark_status']} | human_review={r['human_review_status']} | "
        f"observation: {obs if obs else '(none recorded)'}"
    )
per_event_block = "\n".join(per_event_lines)

PROMPT = f"""You are writing a short analyst note synthesizing patterns across the {n} CRITICAL
pedestrian-vehicle near-miss events from a drone-footage pilot dataset.

Every number below was already computed deterministically from the database. Do not
recompute, round differently, or invent ANY new number, percentage, distance, speed, or
count that is not explicitly given below. If you want to say something quantitative,
you must use one of the numbers given here verbatim.

PRE-COMPUTED STATS (trust these exactly, do not alter):
{json.dumps(stats, indent=2)}

PER-EVENT REAL DATA (Spark's actual stored visual-review text, do not alter):
{per_event_block}

TASK:
1. Write a 3-4 sentence narrative synthesis of real patterns across these {n} events,
   grounded strictly in the stats and observations above (e.g. which vehicle type
   dominates, how tight the PET distribution is, what the flagged/escalated events
   have in common).
2. Write exactly 3 bullet "named patterns", each one sentence, each citing a real
   number from the stats above OR directly paraphrasing a real observation (with its
   event_id) -- never a new number.

Reply as strict JSON, no prose outside the JSON:
{{"summary": "string", "patterns": ["string", "string", "string"]}}"""

resp = client.chat.completions.create(
    model="muse-spark-1.3",
    messages=[{"role": "user", "content": PROMPT}],
    response_format={"type": "json_object"},
)
result = json.loads(resp.choices[0].message.content)

# --- fabrication guard: flag any number in the output we didn't give it ---
given_numbers = set(re.findall(r"\d+\.?\d*", json.dumps(stats)))
given_numbers |= set(re.findall(r"\d+\.?\d*", per_event_block))
output_text = result.get("summary", "") + " " + " ".join(result.get("patterns", []))
output_numbers = set(re.findall(r"\d+\.?\d*", output_text))
suspicious = sorted(output_numbers - given_numbers)

payload = {
    "generated_at": datetime.datetime.utcnow().isoformat(),
    "model": "muse-spark-1.3",
    "scope": "critical_events",
    "n_events": n,
    "stats": stats,
    "summary": result.get("summary", ""),
    "patterns": result.get("patterns", []),
    "suspicious_numbers_not_in_source_data": suspicious,
}

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)

print(f"Wrote {OUT_PATH}")
print("\n--- SUMMARY ---")
print(payload["summary"])
print("\n--- PATTERNS ---")
for p in payload["patterns"]:
    print("-", p)
if suspicious:
    print(f"\n*** WARNING: these numbers appear in the output but NOT in the source "
          f"data given to the model -- review before shipping: {suspicious}")
else:
    print("\n[check] every number in the output traces back to the source data given. Good to ship.")
