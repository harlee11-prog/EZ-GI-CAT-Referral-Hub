import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import streamlit.components.v1 as components

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

        # ── MAP RULE NAMES TO NODES ──
        rule_to_node = {
            "Pediatric Exclusion":                       "testing",
            "Testing Indications":                       "testing",
            "Box 1 – Testing Indications":               "testing",
            "Test Result":                               "test_result",
            "Box 2 – Alarm Features":                    "alarm",
            "Pregnancy Screen":                          "pregnancy",
            "Washout / Test Preparation":                "washout",
            "Box 4 – First Line":                        "treatment",
            "Box 4 – First Line (Penicillin Allergy)":   "treatment",
            "Box 4 – Second Line":                       "treatment",
            "Box 4 – Second Line (Penicillin Allergy)":  "treatment",
            "Box 4 – Third Line":                        "treatment",
            "Box 4 – Third Line (Penicillin Allergy)":   "treatment",
            "Box 6 – Treatment Failure / Fourth Line":   "treatment",
            "Eradication Confirmation":                  "followup",
        }

        visited_nodes = {"start"}
        for step in engine.tracker.steps:
            node = rule_to_node.get(step.rule)
            if node:
                visited_nodes.add(node)

         # Infer nodes that have no tracker.log based on engine flow order
        # Flow: testing → test_result → alarm → pregnancy → washout → treatment → followup
        # If treatment was reached, all steps before it were also visited
        if "treatment" in visited_nodes or "followup" in visited_nodes:
            visited_nodes.add("washout")
            visited_nodes.add("pregnancy")
            visited_nodes.add("alarm")
        # If pregnancy was logged (pregnant patient — engine stopped there),
        # alarm was still checked before pregnancy
        elif "pregnancy" in visited_nodes:
            visited_nodes.add("alarm")
        # If test_result was visited and engine proceeded past it,
        # alarm was checked next
        elif "test_result" in visited_nodes and hp_map[hp_positive] is True:
            visited_nodes.add("alarm")

        # Also add testing if any testing indication was checked
        # (fallback in case em dash mismatch in rule name)
        if any([dyspepsia, ulcer_hx, family_gastric, immigrant_prev]):
            visited_nodes.add("testing")

        # ── BUILD SVG ──
        all_nodes = [
            ("start",       "Patient\nPresents"),
            ("testing",     "Testing\nIndication?"),
            ("test_result", "H. Pylori\nTest Result"),
            ("alarm",       "Alarm\nFeatures?"),
            ("pregnancy",   "Pregnancy\nScreen"),
            ("washout",     "Washout\nReady?"),
            ("treatment",   "Treatment\nSelection"),
            ("followup",    "Eradication\nConfirm"),
        ]

        edges = [
            ("start","testing"), ("testing","test_result"), ("test_result","alarm"),
            ("alarm","pregnancy"), ("pregnancy","washout"), ("washout","treatment"),
            ("treatment","followup")
        ]

        n       = len(all_nodes)
        node_w  = 100
        node_h  = 60
        gap     = 30
        pad     = 40
        total_w = pad + n * node_w + (n - 1) * gap + pad

        positions = {}
        for i, (nid, _) in enumerate(all_nodes):
            positions[nid] = (pad + i * (node_w + gap), 30)

        svg_lines = [
            f'<svg id="pathway-svg" width="100%" viewBox="0 0 {total_w} 160" '
            f'xmlns="http://www.w3.org/2000/svg" '
            f'style="background:#0e0e0e; border-radius:14px;">',
            '<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            '<path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" '
            'stroke-width="1.5" stroke-linecap="round"/></marker></defs>',
        ]

        for a, b in edges:
            ax, ay = positions[a]
            bx, by = positions[b]
            svg_lines.append(
                f'<line class="edge" data-from="{a}" data-to="{b}" '
                f'x1="{ax + node_w}" y1="{ay + node_h//2}" '
                f'x2="{bx}" y2="{by + node_h//2}" '
                f'stroke="#333333" stroke-width="2" marker-end="url(#arr)"/>'
            )

        for nid, title in all_nodes:
            x, y = positions[nid]
            lines = title.split("\n")
            svg_lines.append(
                f'<rect data-node="{nid}" x="{x}" y="{y}" '
                f'width="{node_w}" height="{node_h}" rx="8" '
                f'fill="#1e1e1e" stroke="#3a3a3a" stroke-width="1.5" '
                f'style="transition: fill 0.5s, stroke 0.5s"/>'
            )
            for li, line in enumerate(lines):
                ty = y + 22 + li * 16
                svg_lines.append(
                    f'<text x="{x + node_w//2}" y="{ty}" '
                    f'text-anchor="middle" font-size="11" font-weight="700" '
                    f'fill="#666666" font-family="Arial" '
                    f'data-label="{nid}" style="transition: fill 0.5s">{line}</text>'
                )

        svg_lines.append(
            f'<rect x="{pad}" y="110" width="12" height="12" rx="2" '
            f'fill="#1a5c30" stroke="#21c55d" stroke-width="1.5"/>'
            f'<text x="{pad+18}" y="121" font-size="10" fill="#888888" font-family="Arial">Followed</text>'
            f'<rect x="{pad+90}" y="110" width="12" height="12" rx="2" '
            f'fill="#1e1e1e" stroke="#3a3a3a" stroke-width="1.5"/>'
            f'<text x="{pad+108}" y="121" font-size="10" fill="#888888" font-family="Arial">Not reached</text>'
        )
        svg_lines.append("</svg>")
        svg_str = "\n".join(svg_lines)

        visited_list = list(visited_nodes)
        node_order   = [nid for nid, _ in all_nodes]

        animated_html = f"""
        {svg_str}
        <script>
        const visited = {visited_list};
        const nodeOrder = {node_order};

        function animateNodes() {{
            let i = 0;
            function step() {{
                if (i >= nodeOrder.length) return;
                const nid = nodeOrder[i];
                const rect = document.querySelector('rect[data-node="' + nid + '"]');
                const labels = document.querySelectorAll('text[data-label="' + nid + '"]');
                if (visited.includes(nid)) {{
                    if (rect) {{
                        rect.style.fill = '#1a5c30';
                        rect.style.stroke = '#21c55d';
                    }}
                    labels.forEach(l => l.style.fill = '#ffffff');
                    const edge = document.querySelector('line[data-to="' + nid + '"]');
                    if (edge) {{
                        edge.style.transition = 'stroke 0.5s';
                        edge.setAttribute('stroke', '#21c55d');
                    }}
                }}
                i++;
                setTimeout(step, 450);
            }}
            step();
        }}
        setTimeout(animateNodes, 200);
        </script>
        """

        st.subheader("🗺 Pathway Followed")
        components.html(animated_html, height=180, scrolling=False)

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
