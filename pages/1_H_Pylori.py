import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import streamlit.components.v1 as components

from h_pylori_engine import (
    Patient, HPyloriPathwayEngine,
    TreatmentLine, LastRegimen
)

st.set_page_config(page_title="H. Pylori Pathway", page_icon="🦠", layout="wide")

# CSS for clinical UI components
st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .card-urgent { background-color: #7a1a1a !important; border-left: 5px solid #ff4b4b; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
    .card-routine { background-color: #1a5c30 !important; border-left: 5px solid #21c55d; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
    .card-info { background-color: #1a3a5c !important; border-left: 5px solid #4b9eff; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
    .card-title { font-size: 15px; font-weight: 700; margin-bottom: 6px; color: white; }
    .card-detail { font-size: 13px; color: #cccccc; margin: 2px 0; }
    .badge-urgent { background-color: #ff4b4b; color: white; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-right: 8px; }
    .badge-routine { background-color: #21c55d; color: white; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-right: 8px; }
    .badge-info { background-color: #4b9eff; color: white; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-right: 8px; }
    .section-header { font-size: 13px; font-weight: 600; color: #888888; text-transform: uppercase; letter-spacing: 1px; margin: 20px 0 10px 0; }
    </style>
""", unsafe_allow_html=True)

st.title("🦠 H. Pylori Primary Care Pathway")
st.markdown("---")

left, right = st.columns([1, 1.4])

with left:
    st.subheader("Patient Information")
    age      = st.number_input("Age", 1, 120, 52)
    sex      = st.selectbox("Sex", ["male", "female"])
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
    tx_line = st.selectbox("Treatment line", ["Treatment Naive","Second Line","Third Line","Fourth Line"])
    tx_map = {
        "Treatment Naive": TreatmentLine.NAIVE,
        "Second Line":     TreatmentLine.SECOND_LINE,
        "Third Line":      TreatmentLine.THIRD_LINE,
        "Fourth Line":     TreatmentLine.FOURTH_LINE,
    }
    last_reg = st.selectbox("Last regimen", ["None","PAMC","PBMT"])
    reg_map  = {"None": LastRegimen.NONE, "PAMC": LastRegimen.PAMC, "PBMT": LastRegimen.PBMT}

    run = st.button("▶ Run Pathway", type="primary", use_container_width=True)

with right:
    if run:
        patient = Patient(
            age=age, sex=sex, pregnant_or_nursing=pregnant or None,
            dyspepsia_symptoms=dyspepsia or None, history_ulcer_or_gi_bleed=ulcer_hx or None,
            personal_or_family_hx_gastric_cancer=family_gastric or None, immigrant_high_prevalence=immigrant_prev or None,
            h_pylori_test_positive=hp_map[hp_positive], off_antibiotics_4_weeks=off_abx, off_ppis_2_weeks=off_ppi, off_bismuth_2_weeks=off_bismuth,
            penicillin_allergy=penicillin_allergy or None, treatment_line=tx_map[tx_line], last_regimen_used=reg_map[last_reg],
            alarm_family_hx_esophageal_gastric_cancer=al_family_cancer or None, alarm_personal_ulcer_history=al_ulcer_hx or None,
            alarm_age_over_60_new_persistent_symptoms=al_age_symptoms or None, alarm_unintended_weight_loss=al_weight_loss or None,
            alarm_progressive_dysphagia=al_dysphagia or None, alarm_persistent_vomiting=al_vomiting or None,
            alarm_black_stool=al_black_stool or None, alarm_blood_in_vomit=al_blood_vomit or None, alarm_iron_deficiency_anemia=al_ida or None,
        )

        engine  = HPyloriPathwayEngine()
        actions = engine.evaluate(patient)

        # Mapping engine rules to AHS PDF Boxes
        rule_to_node = {
            "Box 1 – Testing Indications":               "box1",
            "Box 2 – Alarm Features":                    "box2",
            "Test Result":                               "box3",
            "Box 4 – First Line":                        "box4",
            "Box 4 – First Line (Penicillin Allergy)":   "box4",
            "Box 4 – Second Line":                       "box4",
            "Box 4 – Second Line (Penicillin Allergy)":  "box4",
            "Box 4 – Third Line":                        "box4",
            "Box 4 – Third Line (Penicillin Allergy)":   "box4",
            "Eradication Confirmation":                  "box5",
            "Box 6 – Treatment Failure / Fourth Line":   "box6",
        }

        visited_nodes = {"box1"}
        for step in engine.tracker.steps:
            node = rule_to_node.get(step.rule)
            if node: visited_nodes.add(node)
        
        for action in actions:
            if action.category == "REFERRAL":
                visited_nodes.add("box7")
            if "Dyspepsia" in action.description:
                visited_nodes.add("dysp")

        # -- REVISED VERTICAL FLOWCHART SVG --
        canvas_w, canvas_h = 600, 650
        node_w, node_h = 140, 60
        mid_x = canvas_w // 2 - node_w // 2

        # Define vertical structure matching PDF Layout [cite: 1]
        nodes = [
            ("box1", "1. Who to test?", mid_x, 20),
            ("box2", "2. Alarm Features", mid_x, 120),
            ("box7", "7. Referral / GI", 40, 120),
            ("box3", "3. Diagnosis", mid_x, 220),
            ("dysp", "Dyspepsia Path", 420, 220),
            ("box4", "4. Treatment", mid_x, 320),
            ("box5", "5. Confirm Erad.", mid_x, 420),
            ("box6", "6. Tx Failure", mid_x, 520),
        ]

        edges = [
            ("box1", "box2", "", "straight"),
            ("box2", "box7", "Yes", "horizontal"),
            ("box2", "box3", "No", "straight"),
            ("box3", "box4", "Positive", "straight"),
            ("box3", "dysp", "Negative", "horizontal"),
            ("box4", "box5", "", "straight"),
            ("box5", "box6", "No", "straight"),
            ("box6", "box4", "Retry", "curve")
        ]

        svg = [
            f'<svg width="100%" viewBox="0 0 {canvas_w} {canvas_h}" xmlns="http://www.w3.org/2000/svg" style="background:#0e0e0e; border-radius:14px;">',
            '<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            '<path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round"/></marker></defs>'
        ]

        # Render paths with differentiated styles
        for a, b, label, style in edges:
            ax, ay = next(n[2:] for n in nodes if n[0] == a)
            bx, by = next(n[2:] for n in nodes if n[0] == b)
            x1, y1, x2, y2 = ax + node_w/2, ay + node_h/2, bx + node_w/2, by + node_h/2
            
            if style == "straight":
                d = f"M {x1} {ay+node_h} L {x2} {by}"
            elif style == "horizontal":
                # Lateral movement to/from side boxes
                side_x1 = ax if x1 > x2 else ax + node_w
                side_x2 = bx + node_w if x1 > x2 else bx
                d = f"M {side_x1} {y1} L {side_x2} {y2}"
            elif style == "curve":
                # Looping back for treatment retries 
                d = f"M {ax} {y1} C {ax-60} {y1}, {bx-60} {y2}, {bx} {y2}"

            svg.append(f'<path d="{d}" stroke="#333" stroke-width="2" fill="none" marker-end="url(#arr)" data-from="{a}" data-to="{b}" style="transition:0.5s"/>')
            if label:
                lx = (side_x1 + side_x2)/2 if style=="horizontal" else x1
                ly = (y1 + y2)/2 - 10
                svg.append(f'<text x="{lx}" y="{ly}" fill="#888" font-size="12" text-anchor="middle" font-family="Arial">{label}</text>')

        # Render Clinical Boxes
        for nid, title, x, y in nodes:
            svg.append(f'<rect data-node="{nid}" x="{x}" y="{y}" width="{node_w}" height="{node_h}" rx="6" fill="#1e1e1e" stroke="#3a3a3a" stroke-width="1.5" style="transition:0.5s"/>')
            svg.append(f'<text data-label="{nid}" x="{x+node_w/2}" y="{y+node_h/2+5}" text-anchor="middle" font-size="12" fill="#666" font-family="Arial" font-weight="700">{title}</text>')
        
        svg.append("</svg>")
        
        # Animate visited nodes based on clinical findings
        animated_html = f'{"".join(svg)}<script>' + f'const visited={list(visited_nodes)};' + """
            visited.forEach(id => {
                const r = document.querySelector(`rect[data-node="${id}"]`);
                const t = document.querySelector(`text[data-label="${id}"]`);
                const edges = document.querySelectorAll(`path[data-to="${id}"]`);
                if(r) { r.style.fill="#1a5c30"; r.style.stroke="#21c55d"; }
                if(t) t.style.fill="#fff";
                edges.forEach(e => e.style.stroke = "#21c55d");
            });</script>"""

        st.subheader("🗺 Pathway Navigation")
        components.html(animated_html, height=600)

        # -- CLINICAL RECOMMENDATIONS --
        st.markdown('<div class="section-header">Patient Context</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card-info"><div class="card-detail">👤 <b>Age/Sex:</b> {age}/{sex.capitalize()} | 🧪 <b>Result:</b> {hp_positive} | ⚠️ <b>Alarms:</b> {"Yes" if patient.has_alarm_features else "None"}</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="section-header">Recommended Actions</div>', unsafe_allow_html=True)
        for action in actions:
            urgency = action.urgency.upper()
            card_class = "card-urgent" if urgency == "URGENT" else "card-routine" if urgency == "ROUTINE" else "card-info"
            badge = f'<span class="badge-{"urgent" if urgency=="URGENT" else "routine" if urgency=="ROUTINE" else "info"}">{urgency}</span>'
            details = "".join(f'<div class="card-detail">• {d}</div>' for d in action.details)
            st.markdown(f'<div class="{card_class}"><div class="card-title">{badge}{action.category}: {action.description}</div>{details}</div>', unsafe_allow_html=True)

    else:
        st.info("Input clinical details and click ▶ Run Pathway")
