import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import streamlit.components.v1 as components
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

        # ── VISITED NODES ──
        rule_to_node = {
            "Testing Indications":                      "testing",
            "Pediatric Exclusion":                      "testing",
            "Test Result":                              "test_result",
            "Alarm Features":                           "alarm",
            "Pregnancy Screen":                         "pregnancy",
            "Washout / Test Preparation":               "washout",
            "Box 4 – First Line":                       "treatment",
            "Box 4 – First Line (Penicillin Allergy)":  "treatment",
            "Box 4 – Second Line":                      "treatment",
            "Box 4 – Second Line (Penicillin Allergy)": "treatment",
            "Box 4 – Third Line":                       "treatment",
            "Box 4 – Third Line (Penicillin Allergy)":  "treatment",
            "Box 4 – Fourth Line":                      "treatment",
            "Eradication Confirmation":                 "followup",
        }

        visited_nodes = set()
        for step in engine.tracker.steps:
            node = rule_to_node.get(step.rule)
            if node:
                visited_nodes.add(node)
        visited_nodes.add("start")

        # ── BUILD DIAGRAM ──
        all_nodes = [
            ("start",       "Patient\nPresents",      ""),
            ("testing",     "Testing\nIndication?",   ""),
            ("test_result", "H. Pylori\nTest Result", ""),
            ("alarm",       "Alarm\nFeatures?",       ""),
            ("pregnancy",   "Pregnancy\nScreen",      ""),
            ("washout",     "Washout\nReady?",        ""),
            ("treatment",   "Treatment\nSelection",   ""),
            ("followup",    "Eradication\nConfirm",   ""),
        ]

        edges = [
            ("start","testing"), ("testing","test_result"), ("test_result","alarm"),
            ("alarm","pregnancy"), ("pregnancy","washout"), ("washout","treatment"),
            ("treatment","followup")
        ]

        n = len(all_nodes)
        node_w = 90
        node_h = 60
        gap = 36
        total_w = n * node_w + (n - 1) * gap + 80
        cy = 80

        positions = {}
        for i, (nid, _, _) in enumerate(all_nodes):
            positions[nid] = (40 + i * (node_w + gap), cy)

        def node_style(nid):
            if nid in visited_nodes:
                return "#1a5c30", "#21c55d", "#ffffff", "#aaddbb"
            return "#1e1e1e", "#3a3a3a", "#666666", "#444444"

        def edge_col(a, b):
            return "#21c55d" if a in visited_nodes and b in visited_nodes else "#333333"

        svg_parts = [f'''<svg width="100%" viewBox="0 0 {total_w} 180"
             xmlns="http://www.w3.org/2000/svg"
             style="background:#0e0e0e; border-radius:14px; padding:10px">
          <defs>
            <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5"
                    markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke"
                    stroke-width="1.5" stroke-linecap="round"/>
            </marker>
          </defs>''']

        # Edges
        for a, b in edges:
            ax, ay = positions[a]
            bx, by = positions[b]
            col = edge_col(a, b)
            svg_parts.append(
                f'<line x1="{ax + node_w}" y1="{ay + node_h//2}" '
                f'x2="{bx}" y2="{by + node_h//2}" '
                f'stroke="{col}" stroke-width="2" marker-end="url(#arr)"/>'
            )

        # Nodes
        for nid, title, _ in all_nodes:
            x, y = positions[nid]
            bg, border, tc, _ = node_style(nid)
            lines = title.split("\n")
            svg_parts.append(
                f'<rect x="{x}" y="{y}" width="{node_w}" height="{node_h}" rx="8" '
                f'fill="{bg}" stroke="{border}" stroke-width="1.5"/>'
            )
            if len(lines) == 2:
                svg_parts.append(
                    f'<text x="{x + node_w//2}" y="{y + 22}" text-anchor="middle" '
                    f'font-size="11" font-weight="700" fill="{tc}" font-family="Arial">{lines[0]}</text>'
                )
                svg_parts.append(
                    f'<text x="{x + node_w//2}" y="{y + 38}" text-anchor="middle" '
                    f'font-size="11" font-weight="700" fill="{tc}" font-family="Arial">{lines[1]}</text>'
                )
            else:
                svg_parts.append(
                    f'<text x="{x + node_w//2}" y="{y + 34}" text-anchor="middle" '
                    f'font-size="11" font-weight="700" fill="{tc}" font-family="Arial">{title}</text>'
                )

        # Legend
        svg_parts.append(f'''
        <rect x="40" y="155" width="12" height="12" rx="2"
              fill="#1a5c30" stroke="#21c55d" stroke-width="1.5"/>
        <text x="58" y="165" font-size="10" fill="#888888" font-family="Arial">Followed</text>
        <rect x="130" y="155" width="12" height="12" rx="2"
              fill="#1e1e1e" stroke="#3a3a3a" stroke-width="1.5"/>
        <text x="148" y="165" font-size="10" fill="#888888" font-family="Arial">Not reached</text>
        ''')

        svg_parts.append("</svg>")
        svg_html = "\n".join(svg_parts)

        st.subheader("🗺 Pathway Followed")
        components.html(svg_html, height=200, scrolling=False)


        # ── CLINICAL RECOMMENDATIONS ──
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

        st.markdown('<div class="section-header">Recommended Actions</div>',
                    unsafe_allow_html=True)

        for action in actions:
            urgency = action.urgency.upper() if action.urgency else "INFO"
            if urgency == "URGENT":
                card_class = "card-urgent"
                badge = '<span class="badge-urgent">🔴 URGENT</span>'
            elif urgency == "ROUTINE":
                card_class = "card-routine"
                badge = '<span class="badge-routine">🟢 ROUTINE</span>'
            else:
                card_class = "card-info"
                badge = '<span class="badge-info">🔵 INFO</span>'

            details_html = "".join(
                f'<div class="card-detail">• {d}</div>' for d in action.details)

            st.markdown(f"""
            <div class="{card_class}">
                <div class="card-title">{badge}{action.category}: {action.description}</div>
                {details_html}
            </div>
            """, unsafe_allow_html=True)

        with st.expander("📋 Decision Audit Log"):
            for step in engine.tracker.steps:
                st.markdown(f"**[{step.timestamp[11:19]}] {step.rule}**")
                st.caption(f"→ {step.decision}")

    else:
        st.info("Fill in details on the left and click ▶ Run Pathway")
