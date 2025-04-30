import streamlit as st
import pandas as pd
import os
import time
from datetime import date

# ─── Config & Data Loading ─────────────────────────────────────────────────────
st.set_page_config(page_title="Gym Assistant", layout="centered")
DATA_PATH = "data/workout_log.csv"
os.makedirs("data", exist_ok=True)

def load_data():
    """Load (or init) CSV; coerce Date, drop stray idx cols, ensure Cycle col."""
    if os.path.exists(DATA_PATH) and os.path.getsize(DATA_PATH) > 0:
        df = pd.read_csv(DATA_PATH, parse_dates=["Date"])
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        for c in ("Unnamed: 0", "index"):
            if c in df.columns:
                df.drop(columns=[c], inplace=True)
        if "Cycle" not in df.columns:
            df["Cycle"] = None
        return df
    return pd.DataFrame(columns=[
        "Date","Session","Cycle","Exercise","Set",
        "Reps","Weight","RPE","Notes"
    ])

log = load_data()

# ─── Exercises & Defaults ──────────────────────────────────────────────────────
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
    "Abs + Arms":[f"Exercice {i}" for i in range(1,7)],
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
    "Cycle 2": {i: {"sets":3,"reps":[10]*3,"rpe":7} for i in range(1,7)},
    "Cycle 3": {i: {"sets":4,"reps":[6]*4, "rpe":8} for i in range(1,7)},
    "Cycle 4": {i: {"sets":5,"reps":[5]*5, "rpe":9} for i in range(1,7)},
}
cycle_list = list(defaults.keys())

# ─── Sidebar Navigation ────────────────────────────────────────────────────────
page = st.sidebar.selectbox("🔖 Go to", ["Home","Enter New Session"])


# ─── PAGE: HOME ─────────────────────────────────────────────────────────────────
if page == "Home":
    st.title("🏠 Gym Assistant — Home")
    if log.empty:
        st.info("No sessions logged yet.")
        st.stop()

    # Summary metrics
    n_sessions  = log["Date"].dt.date.nunique()
    n_entries   = len(log)
    n_exercises = log["Exercise"].nunique()
    c1,c2,c3 = st.columns(3)
    c1.metric("🗓️ Sessions"    , n_sessions)
    c2.metric("📋 Total Entries", n_entries)
    c3.metric("🏋️ Exercises"   , n_exercises)

    st.markdown("#### Sessions by Type")
    st.bar_chart(log["Session"].value_counts())

    # Weekly Volume & Avg RPE
    dfw = log.copy()
    dfw["week"]   = dfw["Date"].dt.to_period("W").apply(lambda r: r.start_time)
    dfw["volume"] = dfw["Weight"] * dfw["Reps"]
    weekly = dfw.groupby("week").agg(
        total_volume=("volume","sum"),
        avg_rpe=("RPE","mean")
    ).sort_index()
    st.markdown("#### Weekly Volume & Avg RPE")
    st.line_chart(weekly)

    st.markdown("#### 🏆 Personal Bests")
    pr = (
        log.groupby("Exercise")["Weight"].max()
           .reset_index()
           .merge(log, on=["Exercise","Weight"])
           .loc[:,["Exercise","Weight","Date"]]
           .drop_duplicates("Exercise")
           .sort_values(by="Exercise", ascending=True)
    )
    pr["Date"] = pr["Date"].dt.date
    st.table(pr.rename(columns={"Weight":"Max Weight (kg)"}))


# ─── PAGE: ENTER NEW SESSION ────────────────────────────────────────────────────
else:
    st.title("➕ Enter New Session")

    # Session header
    raw_date     = st.date_input("📅 Date", value=date.today())
    date_str     = raw_date.strftime("%Y-%m-%d")
    session_type = st.selectbox("💪 Session Type", list(exercise_dict.keys()))
    exercises    = exercise_dict[session_type]
    cycle        = st.selectbox("🔄 Cycle (week)", cycle_list)
    safe_cycle   = cycle.replace(" ", "_")

    # Tabs per exercise (mobile swipe)
    tabs    = st.tabs([f"{i}. {ex}" for i,ex in enumerate(exercises,1)])
    entries = []

    for idx, tab in enumerate(tabs, start=1):
        ex = exercises[idx-1]
        with tab:
            st.markdown(f"### 🏋️ Exercise {idx}: {ex}")

            # History pop-up
            with st.expander("📖 History (last 5)"):
                hist = (
                    log[log["Exercise"] == ex]
                    .sort_values(by="Date", ascending=False)
                    .head(5)
                )
                if hist.empty:
                    st.write("No history")
                else:
                    disp = hist.copy()
                    disp["Date"] = disp["Date"].dt.date
                    st.table(disp[["Date","Weight","Reps","RPE"]])

            # Defaults
            cfg       = defaults[cycle][idx]
            def_sets  = cfg["sets"]
            def_reps  = cfg["reps"]
            def_rpe   = cfg["rpe"]

            # Number of sets
            sets = st.number_input(
                f"Sets for {ex}", 1, 10, def_sets,
                key=f"sets_{safe_cycle}_{idx}"
            )

            # Prev-cycle max weight
            weight_default = 0.0
            ci = cycle_list.index(cycle)
            if ci > 0:
                prev = cycle_list[ci-1]
                mask = (log["Cycle"] == prev) & (log["Exercise"] == ex)
                if not log[mask].empty:
                    weight_default = float(log.loc[mask,"Weight"].max())

            # Per-set inputs + live countdown
            for s in range(1, sets+1):
                st.markdown(f"**Set {s}**")
                c1,c2,c3,c4,c5,c6 = st.columns([2,1,1,2,1,1])

                weight = c1.number_input(
                    "Weight (kg)", 0.0, 500.0, weight_default, 0.5,
                    key=f"weight_{safe_cycle}_{idx}_{s}"
                )
                rep0 = def_reps[s-1] if s-1 < len(def_reps) else def_reps[-1]
                reps = c2.number_input(
                    "Reps", 1, 50, rep0, 1,
                    key=f"reps_{safe_cycle}_{idx}_{s}"
                )
                rpe = c3.number_input(
                    "RPE", 6, 10, def_rpe, 1,
                    key=f"rpe_{safe_cycle}_{idx}_{s}"
                )
                notes = c4.text_input("Notes", key=f"note_{safe_cycle}_{idx}_{s}")

                rest_dur = c5.number_input(
                    "Rest (s)", 10, 300, 60, 10,
                    key=f"restdur_{safe_cycle}_{idx}_{s}"
                )

                # Start + countdown in placeholder c6
                ph      = c6.empty()
                btn_key = f"btn_rest_{safe_cycle}_{idx}_{s}"
                if c6.button("▶️", key=btn_key):
                    for rem in range(rest_dur, -1, -1):
                        ph.markdown(f"⏱ {rem}s")
                        time.sleep(1)
                    ph.markdown("✅ Done")

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

    # Save session
    confirm = st.checkbox("✅ Confirm all exercises/sets entered")
    if st.button("Save Session", disabled=not confirm):
        if entries:
            df_new = pd.DataFrame(entries)
            df_new["Date"] = pd.to_datetime(df_new["Date"])
            df_new.to_csv(
                DATA_PATH,
                mode="a",
                header=not os.path.exists(DATA_PATH),
                index=False,
                date_format="%Y-%m-%d"
            )
            st.success("Session saved! 🎉")
            log = load_data()
        else:
            st.warning("No data to save.")

    # Recent entries preview
    st.divider()
    st.subheader("📄 Recent Workout Entries")
    if not log.empty:
        disp = log.copy()
        disp["Date"] = disp["Date"].dt.date
        cols = ["Date","Cycle","Session","Exercise","Set","Weight","Reps","RPE","Notes"]
        dfp = (
            disp[cols]
            .sort_values(by=["Date","Cycle"], ascending=[False,True])
            .reset_index(drop=True)
        )
        dfp.index = dfp.index + 1
        dfp.index.name = "No."
        st.dataframe(dfp, use_container_width=True)
    else:
        st.info("No sessions logged yet.")
