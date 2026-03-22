import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import graphviz
import time

from h_pylori_engine import (
    Patient, HPyloriPathwayEngine, generate_clinical_report,
    TreatmentLine, LastRegimen
)

st.set_page_config(page_title="H. Pylori", page_icon="🦠", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .card-urgent {
        background-color: #7a1a1a !important;
        border-left: 5px solid #ff4b4b;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .card-routine {
        background-color: #1a5c30 !important;
        border-left: 5px solid #21c55d;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .card-info {
        background-color: #1a3a5c !important;
        border-left: 5px solid #4b9eff;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .card-title {
        font-size: 15px;
        font-weight: 700;
        margin-bottom: 6px;
        color: white;
    }
    .card-detail {
        font-size: 13px;
        color: #cccccc;
        margin: 2px 0;
    }
    .badge-urgent {
        background-color: #ff4b4b;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 700;
        margin-right: 8px;
    }
    .badge-routine {
        background-color: #21c55d;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 700;
        margin-right: 8px;
    }
    .badge-info {
        background-color: #4b9eff;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 700;
        margin-right: 8px;
    }
    .section-header {
        font-size: 13px;
        font-weight: 600;
        color: #888888;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin: 20px 0 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🦠 H. Pylori Pathway")
st.markdown("---")

left, right = st.columns([1, 1.4])

with left:
    st.subheader("Patient Information")
    age  = st.number_input("Age", 1, 120, 52)
    sex  = st.selectbox("Sex", ["male", "female"])
    pregnant = st.checkbox("Pregnant or nursing")

    st.markdown("**Testing Indication**")
    dyspepsia      = st.checkbox("Dyspepsia symptoms")
    ulcer_hx       = st.checkbox("History of ulcer or GI bleed")
    family_gastric = st.checkbox("Personal/family history of gastric cancer")
    immigrant_prev = st.checkbox("Immigrant from high-prevalence region")

    st.markdown("**H. Pylori Test Result**")
    hp_positive = st.selectbox("Result", ["Not tested", "Positive", "Negative"])
    hp_map = {"Not tested": None, "Positive": True, "Negative": False}

    st.markdown("**Washout Status**")
    off_abx     = st.checkbox("Off antibiotics ≥4 weeks", value=True)
    off_ppi     = st.checkbox("Off PPIs ≥2 weeks", value=True)
    off_bismuth = st.checkbox("Off bismuth ≥2 weeks", value=True)

    st.markdown("**Alarm Features**")
    al_family_cancer = st.checkbox("Family hx esophageal/gastric cancer")
    al_ulcer_hx      = st.checkbox("Personal history of peptic ulcer")
    al_age_symptoms  = st.checkbox("Age >60 with new persistent symptoms")
    al_weight_loss   = st.checkbox("Unintended weight loss >5%")
    al_dysphagia     = st.checkbox("Progressive dysphagia")
    al_vomiting      = st.checkbox("Persistent vomiting")
    al_black_stool   = st.checkbox("Black stool")
    al_blood_vomit   = st.checkbox("Blood in vomit")
    al_ida           = st.checkbox("Iron deficiency anemia")

    st.markdown("**Treatment History**")
    penicillin_allergy = st.checkbox("Penicillin allergy")
    tx_line = st.selectbox("Treatment line",
        ["Treatment Naive","Second Line","Third Line","Fourth Line"])
    tx_map = {
        "Treatment Naive": TreatmentLine.NAIVE,
        "Second Line":     TreatmentLine.SECOND_LINE,
        "Third Line":      TreatmentLine.THIRD_LINE,
        "Fourth Line":     TreatmentLine.FOURTH_LINE,
    }
    last_reg = st.selectbox("Last regimen", ["None","PAMC","PBMT"])
    reg_map = {"None": LastRegimen.NONE, "PAMC": LastRegimen.PAMC, "PBMT": LastRegimen.PBMT}

    run = st.button("▶ Run Pathway", type="primary", use_container_width=True)

with right:
    if run:
        patient = Patient(
            age=age, sex=sex,
            pregnant_or_nursing=pregnant or None,
            dyspepsia_symptoms=dyspepsia or None,
            history_ulcer_or_gi_bleed=ulcer_hx or None,
            personal_or_family_hx_gastric_cancer=family_gastric or None,
            immigrant_high_prevalence=immigrant_prev or None,
            h_pylori_test_positive=hp_map[hp_positive],
            off_antibiotics_4_weeks=off_abx,
            off_ppis_2_weeks=off_ppi,
            off_bismuth_2_weeks=off_bismuth,
            penicillin_allergy=penicillin_allergy or None,
            treatment_line=tx_map[tx_line],
            last_regimen_used=reg_map[last_reg],
            alarm_family_hx_esophageal_gastric_cancer=al_family_cancer or None,
            alarm_personal_ulcer_history=al_ulcer_hx or None,
            alarm_age_over_60_new_persistent_symptoms=al_age_symptoms or None,
            alarm_unintended_weight_loss=al_weight_loss or None,
            alarm_progressive_dysphagia=al_dysphagia or None,
            alarm_persistent_vomiting=al_vomiting or None,
            alarm_black_stool=al_black_stool or None,
            alarm_blood_in_vomit=al_blood_vomit or None,
            alarm_iron_deficiency_anemia=al_ida or None,
        )

        engine  = HPyloriPathwayEngine()
        actions = engine.evaluate(patient)

        # ── Get visited nodes from audit log ──
        visited = [step.rule for step in engine.tracker.steps]
        decisions = {step.rule: step.decision for step in engine.tracker.steps}

        # ── ANIMATED PATHWAY DIAGRAM ──
        st.subheader("🗺 Pathway Followed")

        def build_diagram(highlight_up_to):
            # All pathway nodes in order
            all_nodes = [
                ("start",        "Patient\nPresents"),
                ("testing",      "Testing\nIndication?"),
                ("test_result",  "H. Pylori\nTest Result"),
                ("alarm",        "Alarm\nFeatures?"),
                ("pregnancy",    "Pregnancy\nScreen"),
                ("washout",      "Washout\nReady?"),
                ("treatment",    "Treatment\nSelection"),
                ("followup",     "Eradication\nConfirmation"),
            ]

            # Map audit log rule names to diagram nodes
            rule_to_node = {
                "Testing Indications":               "testing",
                "Test Result":                       "test_result",
                "Alarm Features":                    "alarm",
                "Pregnancy Screen":                  "pregnancy",
                "Washout / Test Preparation":        "washout",
                "Box 4 – First Line":                "treatment",
                "Box 4 – First Line (Penicillin Allergy)": "treatment",
                "Box 4 – Second Line":               "treatment",
                "Box 4 – Second Line (Penicillin Allergy)": "treatment",
                "Box 4 – Third Line":                "treatment",
                "Box 4 – Third Line (Penicillin Allergy)": "treatment",
                "Box 4 – Fourth Line":               "treatment",
                "Eradication Confirmation":          "followup",
                "Pediatric Exclusion":               "testing",
            }

            visited_nodes = set()
            for rule in visited[:highlight_up_to]:
                node = rule_to_node.get(rule)
                if node:
                    visited_nodes.add(node)

            last_node = None
            if highlight_up_to > 0 and highlight_up_to <= len(visited):
                last_rule = visited[highlight_up_to - 1]
                last_node = rule_to_node.get(last_rule)

            g = graphviz.Digraph()
            g.attr(rankdir="TB", bgcolor="transparent")
            g.attr("node", shape="roundedbox", style="filled",
                   fontname="Arial", fontsize="11", margin="0.2")

            for node_id, label in all_nodes:
                if node_id == last_node:
                    # Last visited — highlight as endpoint
                    g.node(node_id, label,
                           fillcolor="#1a5c30", fontcolor="white",
                           color="#21c55d", penwidth="3")
                elif node_id in visited_nodes:
                    # Visited — green
                    g.node(node_id, label,
                           fillcolor="#1a5c30", fontcolor="white",
                           color="#21c55d", penwidth="2")
                else:
                    # Not visited — grey
                    g.node(node_id, label,
                           fillcolor="#2a2a2a", fontcolor="#888888",
                           color="#444444", penwidth="1")

            # Edges
            edges = [
                ("start",    "testing"),
                ("testing",  "test_result"),
                ("test_result", "alarm"),
                ("alarm",    "pregnancy"),
                ("pregnancy","washout"),
                ("washout",  "treatment"),
                ("treatment","followup"),
            ]
            for a, b in edges:
                if a in visited_nodes and b in visited_nodes:
                    g.edge(a, b, color="#21c55d", penwidth="2")
                else:
                    g.edge(a, b, color="#444444", penwidth="1")

            return g

        # Animate — show nodes lighting up one by one
        diagram_placeholder = st.empty()
        for i in range(1, len(visited) + 1):
            diagram_placeholder.graphviz_chart(build_diagram(i))
            time.sleep(0.4)

        # ── Patient Context ──
        st.markdown("---")
        st.subheader("Clinical Recommendations")
        st.markdown('<div class="section-header">Patient Context</div>',
                    unsafe_allow_html=True)
        st.markdown(f"""
        <div class="card-info">
            <div class="card-detail">👤 <b>Age / Sex:</b> {age} / {sex.capitalize()}</div>
            <div class="card-detail">🧬 <b>H. Pylori Test:</b> {hp_positive}</div>
            <div class="card-detail">💊 <b>Treatment Line:</b> {tx_line}</div>
            <div class="card-detail">⚠️ <b>Alarm Features:</b> {"Yes" if patient.has_alarm_features else "None"}</div>
        </div>
        """, unsafe_allow_html=True)

        # ── Actions ──
        st.markdown('<div class="section-header">Recommended Actions</div>',
                    unsafe_allow_html=True)

        for action in actions:
            urgency = action.urgency.upper() if action.urgency else "INFO"
            if urgency == "URGENT":
                card_class, badge = "card-urgent", '<span class="badge-urgent">🔴 URGENT</span>'
            elif urgency == "ROUTINE":
                card_class, badge = "card-routine", '<span class="badge-routine">🟢 ROUTINE</span>'
            else:
                card_class, badge = "card-info", '<span class="badge-info">🔵 INFO</span>'

            details_html = "".join(
                f'<div class="card-detail">• {d}</div>' for d in action.details)

            st.markdown(f"""
            <div class="{card_class}">
                <div class="card-title">{badge}{action.category}: {action.description}</div>
                {details_html}
            </div>
            """, unsafe_allow_html=True)

        # ── Audit Log ──
        with st.expander("📋 Decision Audit Log"):
            for step in engine.tracker.steps:
                st.markdown(f"**[{step.timestamp[11:19]}] {step.rule}**")
                st.caption(f"→ {step.decision}")

    else:
        st.info("Fill in details on the left and click ▶ Run Pathway")
