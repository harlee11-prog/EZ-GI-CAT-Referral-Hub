import streamlit as st
from chronic_diarrhea_engine import run_chronic_diarrhea_pathway

st.set_page_config(page_title="Chronic Diarrhea", layout="wide")

# Inject Custom CSS
st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .card-urgent {
        background-color: #3b1111 !important;
        border-left: 5px solid #ff4b4b;
        border-radius: 8px; padding: 16px 20px; margin-bottom: 12px;
    }
    .card-semi-urgent {
        background-color: #4a3a11 !important;
        border-left: 5px solid #ffb34b;
        border-radius: 8px; padding: 16px 20px; margin-bottom: 12px;
    }
    .card-routine {
        background-color: #113b1c !important;
        border-left: 5px solid #21c55d;
        border-radius: 8px; padding: 16px 20px; margin-bottom: 12px;
    }
    .card-info {
        background-color: #11263b !important;
        border-left: 5px solid #4b9eff;
        border-radius: 8px; padding: 16px 20px; margin-bottom: 12px;
    }
    .card-title { font-size: 1.1em; font-weight: 600; margin-bottom: 8px; color: white;}
    .card-detail { font-size: 0.95em; margin-bottom: 4px; color: #e0e0e0;}
    .badge-urgent { background: #ff4b4b; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; margin-right: 8px; }
    .badge-semi-urgent { background: #ffb34b; color: black; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; margin-right: 8px; }
    .badge-routine { background: #21c55d; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; margin-right: 8px; }
    .badge-info { background: #4b9eff; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; margin-right: 8px; }
    .section-header { font-size: 1.3em; font-weight: 600; margin-top: 24px; margin-bottom: 16px; border-bottom: 1px solid #333; padding-bottom: 8px;}
    </style>
""", unsafe_allow_html=True)

st.title(" Chronic Diarrhea Pathway")
st.markdown("---")

if "patient_data" not in st.session_state:
    st.session_state.patient_data = {}

st.sidebar.button("Reset Assessment", on_click=lambda: st.session_state.patient_data.clear(), use_container_width=True)

# Run Engine
outputs, logs, overrides = run_chronic_diarrhea_pathway(st.session_state.patient_data)

data_requests = [o for o in outputs if type(o).__name__ == "DataRequest"]
stops = [o for o in outputs if type(o).__name__ == "Stop"]
actions = [o for o in outputs if type(o).__name__ == "Action"]

def render_input_field(field_name):
    display_name = field_name.replace("_", " ").title()
    current_value = st.session_state.patient_data.get(field_name, None)

    if any(keyword in field_name for keyword in ["percent", "per_week", "per_day", "duration", "days", "months", "ago"]):
        st.number_input(display_name, value=current_value if isinstance(current_value, (int, float)) else None, key=field_name)
    elif any(keyword in field_name for keyword in ["ug_g", "hemoglobin", "ferritin", "cutoff"]):
        st.number_input(display_name, value=current_value if isinstance(current_value, (int, float)) else None, format="%.2f", key=field_name)
    elif field_name == "sex":
        st.selectbox(display_name, options=[None, "male", "female"], index=0 if current_value is None else (1 if current_value == "male" else 2), key=field_name)
    else:
        st.selectbox(
            display_name,
            options=[None, True, False],
            format_func=lambda x: "Select..." if x is None else str(x),
            index=0 if current_value is None else (1 if current_value else 2),
            key=field_name
        )

def render_html_card(action_or_stop, is_stop=False):
    urgency = getattr(action_or_stop, 'urgency', 'info') or 'info'
    urgency = urgency.lower()
    
    if urgency == "urgent":
        card_class = "card-urgent"
        badge = '<span class="badge-urgent">🔴 URGENT</span>'
    elif urgency == "semi_urgent":
        card_class = "card-semi-urgent"
        badge = '<span class="badge-semi-urgent">🟠 SEMI-URGENT</span>'
    elif urgency == "routine":
        card_class = "card-routine"
        badge = '<span class="badge-routine">🟢 ROUTINE</span>'
    else:
        card_class = "card-info"
        badge = '<span class="badge-info">🔵 INFO</span>'

    if is_stop:
        title = f"Terminal Decision: {action_or_stop.reason}"
        details_html = ""
        if hasattr(action_or_stop, 'actions'):
             details_html = "".join(f'<div class="card-detail">• {a.label}</div>' for a in action_or_stop.actions)
    else:
        title = f"{action_or_stop.code}: {action_or_stop.label}"
        details_html = ""
        if hasattr(action_or_stop, 'details') and action_or_stop.details:
            details_html = "".join(f'<div class="card-detail">• {k}: {v}</div>' for k, v in action_or_stop.details.items())

    st.markdown(f"""
    <div class="{card_class}">
        <div class="card-title">{badge} {title}</div>
        {details_html}
    </div>
    """, unsafe_allow_html=True)

# Layout Setup
left, right = st.columns([1, 1.4])

# LEFT COLUMN: Inputs & Data Requests
with left:
    st.subheader("Patient Information")
    
    if data_requests:
        with st.form(key="data_request_form", border=True):
            active_fields = []
            for dr in data_requests:
                st.info(dr.message)
                for field in dr.missing_fields:
                    if field not in active_fields:
                        render_input_field(field)
                        active_fields.append(field)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button(label="Submit Data", use_container_width=True):
                for field in active_fields:
                    val = st.session_state.get(field)
                    if val is not None:
                        st.session_state.patient_data[field] = val
                st.rerun()
    elif stops:
        st.success("Pathway assessment complete. No further data required.")

# RIGHT COLUMN: Outputs & Logs
with right:
    st.markdown('<div class="section-header">Recommended Actions</div>', unsafe_allow_html=True)
    
    if not actions and not stops:
        st.info("Fill in patient information to generate recommendations.")
    
    for action in actions:
        render_html_card(action, is_stop=False)
        
    if stops:
        for stop in stops:
            render_html_card(stop, is_stop=True)

    # Audit Log Integration
    if logs:
        with st.expander("📋 Decision Audit Log"):
            for step in logs:
                node = step.get("node", "Unknown")
                rule = step.get("rule", "Executed")
                st.markdown(f"**Node: {node}**")
                st.caption(f"→ {rule}")
