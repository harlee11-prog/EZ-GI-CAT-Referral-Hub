import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import streamlit.components.v1 as components
from h_pylori_engine import (
    Patient, HPyloriPathwayEngine, TreatmentLine, LastRegimen
)

st.set_page_config(page_title="H. Pylori", page_icon="🦠", layout="wide")

# ── Global CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* sidebar */
[data-testid="stSidebar"] { background: #0f172a; }

/* patient context card */
.ctx-card {
    background: #1e3a5f;
    border: 1px solid #2e5c8a;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 14px;
    font-size: 14px;
    color: #e2e8f0;
}
.ctx-card b { color: #93c5fd; }

/* action cards */
.action-card {
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 12px;
    font-size: 13.5px;
    line-height: 1.6;
}
.action-card.urgent  { background:#3b0a0a; border-left: 5px solid #ef4444; color:#fecaca; }
.action-card.routine { background:#052e16; border-left: 5px solid #22c55e; color:#bbf7d0; }
.action-card.info    { background:#0c1a2e; border-left: 5px solid #3b82f6; color:#bfdbfe; }
.action-card h4      { margin: 0 0 6px 0; font-size: 14px; }
.action-card ul      { margin: 6px 0 0 16px; padding: 0; }
.action-card li      { margin-bottom: 3px; }
.badge {
    display: inline-block;
    font-size: 11px;
    font-weight: bold;
    padding: 2px 8px;
    border-radius: 20px;
    margin-right: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge.urgent  { background:#ef4444; color:#fff; }
.badge.routine { background:#22c55e; color:#fff; }
.badge.info    { background:#3b82f6; color:#fff; }
</style>
""", unsafe_allow_html=True)

st.title("🦠 H. Pylori Pathway")
st.markdown("---")

left, right = st.columns([1, 1.5])

# ── LEFT PANEL: Patient Inputs ──────────────────────────────────────────────
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
    off_abx    = st.checkbox("Off antibiotics ≥4 weeks", value=True)
    off_ppi    = st.checkbox("Off PPIs ≥2 weeks",        value=True)
    off_bismuth= st.checkbox("Off bismuth ≥2 weeks",     value=True)

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
        "Treatment Naive":  TreatmentLine.NAIVE,
        "Second Line":      TreatmentLine.SECOND_LINE,
        "Third Line":       TreatmentLine.THIRD_LINE,
        "Fourth Line":      TreatmentLine.FOURTH_LINE,
    }
    last_reg = st.selectbox("Last regimen", ["None","PAMC","PBMT"])
    reg_map = {"None": LastRegimen.NONE, "PAMC": LastRegimen.PAMC, "PBMT": LastRegimen.PBMT}

    run = st.button("▶ Run Pathway", type="primary", use_container_width=True)

# ── RIGHT PANEL ─────────────────────────────────────────────────────────────
with right:
    if run:
        patient = Patient(
            age=age,
            sex=sex,
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

        # ── PATH STATE FLAGS ───────────────────────────────────────────────
        action_categories = [a.category for a in actions]
        action_urgencies  = [a.urgency  for a in actions]

        no_indication  = not patient.has_testing_indication and patient.h_pylori_test_positive is None
        test_negative  = patient.h_pylori_test_positive is False
        has_alarm      = patient.has_alarm_features
        is_pregnant    = bool(patient.pregnant_or_nursing)
        is_positive    = patient.h_pylori_test_positive is True
        went_to_tx     = "TREATMENT" in action_categories or "REFERRAL" in action_categories
        urgent_ref     = "URGENT" in action_urgencies
        has_followup   = "FOLLOW_UP" in action_categories
        is_pediatric   = patient.age is not None and patient.age < 18

        # ── AHS-STYLE SVG FLOWCHART ────────────────────────────────────────
        C_MAIN    = "#16a34a"
        C_UNVISIT = "#475569"
        C_DIAMOND = "#1d4ed8"
        C_URGENT  = "#dc2626"
        C_EXIT    = "#d97706"
        C_TEXT    = "#ffffff"
        C_DIM     = "#94a3b8"
        C_BG      = "#0f172a"

        def nc(visited, urgent=False, is_exit=False):
            if not visited: return C_UNVISIT
            if urgent:      return C_URGENT
            if is_exit:     return C_EXIT
            return C_MAIN

        def dc(visited):
            return C_DIAMOND if visited else C_UNVISIT

        def tc(visited):
            return C_TEXT if visited else C_DIM

        svg = []
        W, H = 680, 900

        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">')

        # Arrow markers
        svg.append('''<defs>
  <marker id="a"  markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>
  <marker id="ag" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>
  <marker id="ar" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>
  <marker id="ao" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>
</defs>''')

        def rect(x, y, w, h, color, lines, sub="", rx=8):
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            col = C_TEXT if color not in (C_UNVISIT,) else C_DIM
            n = len(lines) + (1 if sub else 0)
            base = y + h/2 - (n-1)*8
            for i, ln in enumerate(lines):
                svg.append(f'<text x="{x+w/2}" y="{base+i*17}" text-anchor="middle" fill="{col}" font-size="12" font-weight="bold">{ln}</text>')
            if sub:
                svg.append(f'<text x="{x+w/2}" y="{base+len(lines)*17}" text-anchor="middle" fill="{col}99" font-size="10">{sub}</text>')

        def diamond(cx, cy, w, h, color, lines):
            hw, hh = w/2, h/2
            pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
            svg.append(f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            col = C_TEXT if color != C_UNVISIT else C_DIM
            n = len(lines)
            base = cy - (n-1)*7
            for i, ln in enumerate(lines):
                svg.append(f'<text x="{cx}" y="{base+i*15}" text-anchor="middle" fill="{col}" font-size="11" font-weight="bold">{ln}</text>')

        def arr(x1,y1,x2,y2, mid="a", label="", lx=6, ly=-5, dash=False):
            d = 'stroke-dasharray="5,3"' if dash else ""
            svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#64748b" stroke-width="2" {d} marker-end="url(#{mid})"/>')
            if label:
                mx,my = (x1+x2)/2+lx,(y1+y2)/2+ly
                c = {"ag":"#16a34a","ar":"#dc2626","ao":"#d97706"}.get(mid,"#94a3b8")
                svg.append(f'<text x="{mx}" y="{my}" fill="{c}" font-size="10" font-weight="bold">{label}</text>')

        def elbow(x1,y1, x2,y2, mid="a", label="", dash=False):
            d = 'stroke-dasharray="5,3"' if dash else ""
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="#64748b" stroke-width="2" {d} marker-end="url(#{mid})"/>')
            if label:
                c = {"ag":"#16a34a","ar":"#dc2626","ao":"#d97706"}.get(mid,"#94a3b8")
                mx = (x1+x2)/2
                svg.append(f'<text x="{mx}" y="{y1-4}" fill="{c}" font-size="10" font-weight="bold" text-anchor="middle">{label}</text>')

        CX = 340
        NW,NH = 160,44
        DW,DH = 172,54
        EW,EH = 126,38

        # Row Y positions
        Ys = {
            "present":  20,
            "d_test":   100,
            "order":    195,
            "d_result": 280,
            "d_alarm":  375,
            "d_preg":   465,
            "washout":  560,
            "treat":    640,
            "d_erad":   730,
            "complete": 825,
        }

        # 0 — Patient Presents
        y = Ys["present"]
        rect(CX-NW/2, y, NW, NH, nc(True), ["👤 Patient Presents"])

        # 1 — Testing Indication? (diamond)
        y = Ys["d_test"]
        v = not is_pediatric
        arr(CX, Ys["present"]+NH, CX, y, "ag" if v else "a")
        diamond(CX, y+DH/2, DW, DH, dc(v), ["1. Testing","Indication?"])

        # Exit right: Pediatric
        rect(W-20-EW, y+8, EW, EH, nc(is_pediatric,urgent=True), ["👶 Refer Peds GI"], sub="Age < 18")
        elbow(CX+DW/2, y+DH/2, W-20-EW, y+8+EH/2, "ar" if is_pediatric else "a",
              "Age<18", dash=not is_pediatric)

        # Exit left: No indication
        rect(20, y+8, EW, EH, nc(no_indication,is_exit=True), ["No Indication"], sub="Reassess")
        elbow(CX-DW/2, y+DH/2, 20+EW, y+8+EH/2, "ao" if no_indication else "a",
              "No", dash=not no_indication)

        # 2 — Order Test
        y2_top = Ys["order"]
        v2 = not no_indication and not is_pediatric
        arr(CX, Ys["d_test"]+DH, CX, y2_top, "ag" if v2 else "a", "Yes", lx=6, ly=-4)
        rect(CX-NW/2, y2_top, NW, NH, nc(v2), ["🧪 Order HpSAT", "or UBT"], sub="Pre-test washout req.")

        # 3 — Test Result? (diamond)
        y = Ys["d_result"]
        v_res = patient.h_pylori_test_positive is not None
        arr(CX, y2_top+NH, CX, y, "ag" if v_res else "a")
        diamond(CX, y+DH/2, DW, DH, dc(v_res), ["3. H. pylori","Test Result?"])

        # Exit left: Negative
        rect(20, y+8, EW, EH, nc(test_negative,is_exit=True), ["Negative ➜","Dyspepsia Path"])
        elbow(CX-DW/2, y+DH/2, 20+EW, y+8+EH/2, "ao" if test_negative else "a",
              "−", dash=not test_negative)

        # 4 — Alarm Features? (diamond)
        y = Ys["d_alarm"]
        v3 = is_positive
        arr(CX, Ys["d_result"]+DH, CX, y, "ag" if v3 else "a", "+", lx=6, ly=-4)
        diamond(CX, y+DH/2, DW, DH, dc(v3), ["2. Alarm","Features?"])

        # Exit right: Urgent referral
        rect(W-20-EW, y+8, EW, EH, nc(has_alarm and is_positive, urgent=True),
             ["⚠ Urgent Refer"], sub="GI / Endoscopy")
        elbow(CX+DW/2, y+DH/2, W-20-EW, y+8+EH/2,
              "ar" if (has_alarm and is_positive) else "a",
              "Yes", dash=not (has_alarm and is_positive))

        # 5 — Pregnancy Screen (diamond)
        y = Ys["d_preg"]
        v4 = is_positive and not has_alarm
        arr(CX, Ys["d_alarm"]+DH, CX, y, "ag" if v4 else "a", "No", lx=6, ly=-4)
        diamond(CX, y+DH/2, DW, DH, dc(v4), ["Pregnancy /","Nursing?"])

        # Exit right: Pregnant
        rect(W-20-EW, y+8, EW, EH, nc(is_pregnant and is_positive, urgent=True),
             ["🚫 Do Not Treat"], sub="Reassess postpartum")
        elbow(CX+DW/2, y+DH/2, W-20-EW, y+8+EH/2,
              "ar" if (is_pregnant and is_positive) else "a",
              "Yes", dash=not (is_pregnant and is_positive))

        # 6 — Washout Verified
        y = Ys["washout"]
        v5 = v4 and not is_pregnant
        arr(CX, Ys["d_preg"]+DH, CX, y, "ag" if v5 else "a", "No", lx=6, ly=-4)
        rect(CX-NW/2, y, NW, NH, nc(v5), ["✅ Washout", "Verified"], sub="Abx / PPI / Bismuth")

        # 7 — Treatment Selection
        y = Ys["treat"]
        v6 = went_to_tx
        arr(CX, Ys["washout"]+NH, CX, y, "ag" if v6 else "a")
        rect(CX-NW/2, y, NW, NH, nc(v6), ["4. Treatment", "Selection"], sub="1st / 2nd / 3rd / 4th Line")

        # 8 — Eradication Confirmed? (diamond)
        y = Ys["d_erad"]
        v7 = has_followup
        arr(CX, Ys["treat"]+NH, CX, y, "ag" if v7 else "a")
        diamond(CX, y+DH/2, DW, DH, dc(v7), ["5. Eradication","Confirmed?"])

        # Exit right: Failure / next line
        rect(W-20-EW, y+8, EW, EH, nc(urgent_ref, urgent=urgent_ref, is_exit=not urgent_ref),
             ["❌ Failure"], sub="→ Next Line / Refer GI")
        elbow(CX+DW/2, y+DH/2, W-20-EW, y+8+EH/2,
              "ar" if urgent_ref else "ao",
              "No", dash=not urgent_ref)

        # 9 — Pathway Complete
        y = Ys["complete"]
        v8 = has_followup and not urgent_ref
        arr(CX, Ys["d_erad"]+DH, CX, y, "ag" if v8 else "a", "Yes", lx=6, ly=-4)
        rect(CX-NW/2, y, NW, NH, nc(v8, is_exit=v8), ["✅ Pathway", "Complete"], sub="Re-infection <2%")

        # Legend
        legend_y = H - 28
        items = [
            (C_MAIN,    "Visited"),
            (C_DIAMOND, "Decision"),
            (C_URGENT,  "Urgent"),
            (C_EXIT,    "Exit/Off-ramp"),
            (C_UNVISIT, "Not reached"),
        ]
        lx = 20
        for col, label in items:
            svg.append(f'<rect x="{lx}" y="{legend_y}" width="12" height="12" rx="2" fill="{col}"/>')
            svg.append(f'<text x="{lx+16}" y="{legend_y+10}" fill="#94a3b8" font-size="10">{label}</text>')
            lx += 90

        svg.append("</svg>")
        svg_str = "\n".join(svg)

        # ── RENDER FLOWCHART ───────────────────────────────────────────────
        st.subheader("🗺️ Pathway Followed")
        components.html(
            f'<div style="background:#0f172a;padding:12px;border-radius:14px">{svg_str}</div>',
            height=930, scrolling=True
        )

        # ── CLINICAL RECOMMENDATIONS ───────────────────────────────────────
        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # Patient context card
        test_str = {None: "Not yet tested", True: "✅ Positive", False: "❌ Negative"}[patient.h_pylori_test_positive]
        alarm_str = ", ".join(patient.active_alarms) if patient.has_alarm_features else "None"
        line_labels = {
            TreatmentLine.NAIVE:       "Treatment Naive",
            TreatmentLine.SECOND_LINE: "Second Line",
            TreatmentLine.THIRD_LINE:  "Third Line",
            TreatmentLine.FOURTH_LINE: "Fourth Line",
        }
        st.markdown(f"""
<div class="ctx-card">
  <b>🧑 Age / Sex:</b> {patient.age} / {(patient.sex or "").capitalize()}&nbsp;&nbsp;
  <b>🦠 H. Pylori Test:</b> {test_str}&nbsp;&nbsp;
  <b>💊 Treatment Line:</b> {line_labels[patient.treatment_line]}<br>
  <b>⚠ Alarm Features:</b> {alarm_str}
</div>
""", unsafe_allow_html=True)

        # Action cards
        urgency_label = {"URGENT":"urgent","ROUTINE":"routine","INFO":"info","NONE":"info"}
        cat_icon = {
            "TREATMENT":    "💊",
            "REFERRAL":     "📋",
            "TESTING":      "🧪",
            "FOLLOW_UP":    "🔁",
            "CLINICAL_NOTE":"📝",
            "CONTRAINDICATION": "🚫",
            "EXCLUSION":    "🚫",
            "ROUTING":      "↪️",
        }
        st.markdown('<div style="margin-top:4px">', unsafe_allow_html=True)
        for action in actions:
            cls    = urgency_label.get(action.urgency, "info")
            icon   = cat_icon.get(action.category, "📌")
            badge  = f'<span class="badge {cls}">{action.urgency}</span>' if action.urgency != "INFO" else f'<span class="badge info">{action.category}</span>'
            detail_html = ""
            if action.details:
                items_html = "".join(f"<li>{d}</li>" for d in action.details if d.strip())
                detail_html = f"<ul>{items_html}</ul>"
            st.markdown(f"""
<div class="action-card {cls}">
  <h4>{badge}{icon} {action.category}: {action.description}</h4>
  {detail_html}
</div>
""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Decision audit log (collapsible)
        with st.expander("📋 Decision Audit Log"):
            from datetime import datetime
            for step in engine.tracker.steps:
                try:
                    ts = datetime.fromisoformat(step.timestamp).strftime("%H:%M:%S")
                except Exception:
                    ts = "—"
                st.markdown(f"**[{ts}] {step.rule}**  →  _{step.decision}_")
                if step.inputs:
                    st.caption("  ".join(f"`{k}={v}`" for k,v in step.inputs.items()))
    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
