"""Hotel Energy Command Board - prototipe MVP (F1-F12).

Jalankan:  streamlit run app.py
"""
import pandas as pd
import streamlit as st

from core import ui

st.set_page_config(page_title="Hotel Energy Command Board", page_icon=":material/bolt:", layout="wide")

PAGES = {
    "exec": st.Page("views/executive.py", title="Executive Command Center", icon=":material/space_dashboard:", default=True),
    "dq": st.Page("views/data_quality.py", title="Data Quality", icon=":material/verified:"),
    "cons": st.Page("views/consumption_cost.py", title="Consumption & Cost", icon=":material/show_chart:"),
    "tariff": st.Page("views/tariff_reactive.py", title="Tariff & Reactive Energy", icon=":material/electric_meter:"),
    "zone": st.Page("views/zone.py", title="Zone Analysis", icon=":material/grid_view:"),
    "fc": st.Page("views/forecasting.py", title="Forecasting", icon=":material/insights:"),
    "anom": st.Page("views/anomaly_reco.py", title="Anomaly & Recommendation", icon=":material/notification_important:"),
    "report": st.Page("views/report_decision.py", title="Report & Decision Note", icon=":material/assignment:"),
}
ACCESS = {  # role-based view (Bab 3.3 - Pengguna dan Peran)
    "Facility Manager": list(PAGES),
    "Analis Data": list(PAGES),
    "Staf Teknis": ["exec", "cons", "tariff", "zone", "anom", "report"],
    "Finance": ["exec", "cons", "tariff", "report"],
    "Manajemen": ["exec", "report"],
}

with st.sidebar:
    st.markdown("### :material/bolt: Hotel Energy Command Board")
    st.selectbox("Peran pengguna", ui.ROLES, key="role",
                 help="Menentukan halaman dan aksi yang tersedia (role-based view).")

res = ui.result()
dates = res.clean["DATE"]
if "replay_date" not in st.session_state:
    st.session_state["replay_date"] = dates.max().date()

with st.sidebar:
    st.date_input("Replay tanggal (\"hari ini\")", key="replay_date",
                  min_value=dates.min().date(), max_value=dates.max().date(),
                  help="Prototipe memutar ulang data historis seolah-olah tersedia setiap hari (Bab 3.4).")
    d = pd.Timestamp(st.session_state["replay_date"])
    if res.scored is not None:
        row = res.clean.set_index("DATE").loc[d]
        st.caption(f"Status data hari ini: **{row['day_status']}** · trust {row['day_trust']:.0f}")
    st.divider()
    st.caption("Human-in-the-loop: sistem hanya merekomendasikan pemeriksaan. "
               "Tidak ada kontrol BAS/HVAC, data real-time, okupansi, maupun cuaca.")

nav = st.navigation([PAGES[k] for k in ACCESS[ui.role()]])
nav.run()
