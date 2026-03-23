import streamlit as st
from chronic_diarrhea_engine import run_chronic_diarrhea_pathway

st.set_page_config(page_title="Chronic Diarrhea Pathway", layout="wide")
st.title("Chronic Diarrhea Pathway Assessment")

if "patient_data" not in st.session_state:
    st.session_state.patient_data = {}

st.sidebar.button("Reset Assessment", on_click=lambda: st.session_state.patient_data.clear())

outputs, logs, overrides = run_chronic_diarrhea_pathway(st.session_state.patient_data)

def render_action(action):
    if action.urgency == "urgent":
        st.error(f"**{action.code}**: {action.label}")
    else:
        st.write(f"**{action.code}**: {action.label}")
    if action.details:
        with st.expander("View Details"):
            st.json(action.details)

def render_input_field(field_name):
    display_name = field_name.replace("_", " ").title()
    current_value = st.session_state.patient_data.get(field_name, None)

    if any(keyword in field_name for keyword in ["percent", "per_week", "per_day", "duration", "days"]):
        val = st.number_input(display_name, value=current_value if isinstance(current_value, (int, float)) else 0.0)
        st.session_state.patient_data[field_name] = val
    elif any(keyword in field_name for keyword in ["ug_g", "hemoglobin", "ferritin"]):
        val = st.number_input(display_name, value=current_value if isinstance(current_value, (int, float)) else 0.0, format="%.2f")
        st.session_state.patient_data[field_name] = val
    else:
        val = st.selectbox(
            display_name,
            options=[None, True, False],
            format_func=lambda x: "Select..." if x is None else str(x),
            index=0 if current_value is None else (1 if current_value else 2),
            key=field_name
        )
        if val is not None:
            st.session_state.patient_data[field_name] = val

data_requests = [o for o in outputs if type(o).__name__ == "DataRequest"]
stops = [o for o in outputs if type(o).__name__ == "Stop"]
actions = [o for o in outputs if type(o).__name__ == "Action"]

if actions:
    st.subheader("Current Actions & Advisories")
    for action in actions:
        render_action(action)

if data_requests:
    st.subheader("Required Information")
    with st.form(key="data_request_form"):
        for dr in data_requests:
            st.info(dr.message)
            for field in dr.missing_fields:
                render_input_field(field)
        if st.form_submit_button(label="Submit Data"):
            st.rerun()

elif stops:
    st.subheader("Pathway Complete / Terminal Decision")
    for stop in stops:
        if stop.urgency == "urgent":
            st.error(f"**Decision:** {stop.reason}")
        elif stop.urgency == "semi_urgent":
            st.warning(f"**Decision:** {stop.reason}")
        else:
            st.success(f"**Decision:** {stop.reason}")
        for action in stop.actions:
            render_action(action)
