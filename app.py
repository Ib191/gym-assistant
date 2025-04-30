import streamlit as st
import pandas as pd
import os
from datetime import date

# ─── Configuration ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Gym Assistant", layout="centered")
DATA_PATH = "data/workout_log.csv"
os.makedirs("data", exist_ok=True)

def load_data():
    """
    Load (or initialize) the workout log.
    Ensures 'Date' is datetime64 and that 'Cycle' column always exists.
    """
    if os.path.exists(DATA_PATH) and os.path.getsize(DATA_PATH) > 0:
        df = pd.read_csv(DATA_PATH, parse_dates=["Date"])
        # coerce any stray strings → Timestamps
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        # if the CSV was written before 'Cycle' existed, add the column
        if "Cycle" not in df.columns:
            df["Cycle"] = None
        return df
    # fresh log, include Cycle column from the start
    return pd.DataFrame(columns=[
        "Date","Session","Cycle","Exercise",
        "Set","Reps","Weight","RPE","Notes"
    ])

log = load_data()


# ─── Exercises & Cycle Defaults ────────────────────────────────────────────────
exercise_dict = {
    "Push": [
        "Développé couché semi-incliné",
        "Dips à la machine légère",
        "Développé décliné à la barre",
        "Écarté incliné poulie",
        "Élévation latérale penché sur le côté à la poulie basse",
        "Barre au front allongé à la poulie basse",
    ],
    "Pull":   [f"Exercice {i}" for i in range(1,7)],
    "Legs":   [f"Exercice {i}" for i in range(1,7)],
    "Abs + Arms": [f"Exercice {i}" for i in range(1,7)],
}

defaults = {
    "Cycle 1": {
        1: {"sets":4, "reps":[12,12,12,10], "rpe":7},
        2: {"sets":3, "reps":[12,12,12],    "rpe":7},
        3: {"sets":3, "reps":[11,11,11],    "rpe":7},
        4: {"sets":3, "reps":[10,10,10],    "rpe":8},
        5: {"sets":3, "reps":[12,12,12],    "rpe":8},
        6: {"sets":3, "reps":[12,12,12],    "rpe":8},
    },
    "Cycle 2": {i: {"sets":3, "reps":[10]*3, "rpe":7} for i in range(1,7)},
    "Cycle 3": {i: {"sets":4, "reps":[6]*4,  "rpe":8} for i in range(1,7)},
    "Cycle 4": {i: {"sets":5, "reps":[5]*5,  "rpe":9} for i in range(1,7)},
}
cycle_list = list(defaults.keys())


# ─── UI – Header ──────────────────────────────────────────────────────────────
st.title("🏋️ Gym Assistant")
st.markdown("Log your sets per exercise in a simple, mobile-optimized way.")

# 1) Date
raw_date = st.date_input("📅 Date", value=date.today())
date_str = raw_date.strftime("%Y-%m-%d")

# 2) Session Type
session_type = st.selectbox("💪 Session Type", list(exercise_dict.keys()))
selected_exercises = exercise_dict[session_type]

# 3) Cycle
cycle = st.selectbox("🔄 Cycle (week)", cycle_list)
# safe fragment for widget keys
safe_cycle = cycle.replace(" ", "_")


# ─── Dynamic Inputs ────────────────────────────────────────────────────────────
entries = []

for idx, ex in enumerate(selected_exercises, start=1):
    st.markdown(f"### 🏋️ Exercise {idx}: {ex}")

    cfg = defaults[cycle][idx]
    def_sets = cfg["sets"]
    def_reps = cfg["reps"]
    def_rpe  = cfg["rpe"]

    # number of sets
    sets = st.number_input(
        f"How many sets for {ex}?",
        min_value=1, max_value=10, step=1,
        value=def_sets,
        key=f"sets_{safe_cycle}_{idx}"
    )

    # previous-cycle max weight
    weight_default = 0.0
    ci = cycle_list.index(cycle)
    if ci > 0:
        prev = cycle_list[ci-1]
        mask = (log["Cycle"] == prev) & (log["Exercise"] == ex)
        if not log[mask].empty:
            weight_default = float(log.loc[mask, "Weight"].max())

    for s in range(1, sets+1):
        st.markdown(f"**Set {s}**")
        c1, c2, c3, c4 = st.columns([2,1,2,3])

        weight = c1.number_input(
            "Weight (kg)",
            min_value=0.0, step=0.5,
            value=weight_default,
            key=f"weight_{safe_cycle}_{idx}_{s}"
        )
        rep_def = def_reps[s-1] if s-1 < len(def_reps) else def_reps[-1]
        reps = c2.number_input(
            "Reps",
            min_value=1, max_value=50, step=1,
            value=rep_def,
            key=f"reps_{safe_cycle}_{idx}_{s}"
        )
        rpe = c3.number_input(
            "RPE",
            min_value=6, max_value=10, step=1,
            value=def_rpe,
            key=f"rpe_{safe_cycle}_{idx}_{s}"
        )
        notes = c4.text_input(
            "Notes (optional)",
            key=f"note_{safe_cycle}_{idx}_{s}"
        )

        entries.append({
            "Date":     date_str,
            "Session":  session_type,
            "Cycle":    cycle,
            "Exercise": ex,
            "Set":      s,
            "Weight":   weight,
            "Reps":     reps,
            "RPE":      rpe,
            "Notes":    notes
        })


# ─── Save & Persist ────────────────────────────────────────────────────────────
if st.button("✅ Save Session"):
    if entries:
        df_new = pd.DataFrame(entries)
        df_new["Date"] = pd.to_datetime(df_new["Date"])
        combined = pd.concat([log, df_new], ignore_index=True)
        combined.to_csv(DATA_PATH, index=False, date_format="%Y-%m-%d")
        st.success("Workout session saved successfully! 💪")
        log = load_data()  # reload with new rows
    else:
        st.warning("No sets to save — fill out at least one set.")


# ─── Recent Workout Entries ────────────────────────────────────────────────────
st.divider()
st.subheader("📄 Recent Workout Entries")

if not log.empty:
    disp = log.copy()
    disp["Date"] = disp["Date"].dt.date

    sort_cols = ["Date", "Cycle"] if "Cycle" in disp.columns else ["Date"]
    st.dataframe(
        disp.sort_values(sort_cols, ascending=[False, True]).head(30),
        use_container_width=True
    )
else:
    st.info("No sessions logged yet.")
