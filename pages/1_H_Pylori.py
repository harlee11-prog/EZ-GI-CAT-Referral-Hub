import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import streamlit.components.v1 as components
from h_pylori_engine import (
    Patient, HPyloriPathwayEngine, TreatmentLine, LastRegimen
)

st.set_page_config(page_title="H. Pylori", page_icon="🦠", layout="wide")

# ── GLOBAL CSS ───────────────────────────────────────────────────────────────
# FIX 1: Sidebar — do NOT override background so it inherits the app theme.
#         Only style the nav links to be readable.
# FIX 2: All flowchart text is clipped inside foreignObject — we use pure SVG
#         text elements with explicit wrapping instead.
st.markdown("""
<style>
/* ── Patient context card ── */
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

/* ── Action cards ── */
.action-card {
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 12px;
    font-size: 13.5px;
    line-height: 1.6;
}
.action-card.urgent  { background:#3b0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.action-card.routine { background:#052e16; border-left:5px solid #22c55e; color:#bbf7d0; }
.action-card.info    { background:#0c1a2e; border-left:5px solid #3b82f6; color:#bfdbfe; }
.action-card h4 { margin:0 0 6px 0; font-size:14px; }
.action-card ul { margin:6px 0 0 16px; padding:0; }
.action-card li { margin-bottom:3px; }
.badge {
    display:inline-block; font-size:11px; font-weight:bold;
    padding:2px 8px; border-radius:20px; margin-right:6px;
    text-transform:uppercase; letter-spacing:0.5px;
}
.badge.urgent  { background:#ef4444; color:#fff; }
.badge.routine { background:#22c55e; color:#fff; }
.badge.info    { background:#3b82f6; color:#fff; }
</style>
""", unsafe_allow_html=True)

st.title("🦠 H. Pylori Pathway")
st.markdown("---")

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
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
    off_ppi     = st.checkbox("Off PPIs ≥2 weeks",        value=True)
    off_bismuth = st.checkbox("Off bismuth ≥2 weeks",     value=True)

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

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
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

        # ── PATH STATE FLAGS ──────────────────────────────────────────────
        action_categories = [a.category for a in actions]
        action_urgencies  = [a.urgency  for a in actions]
        no_indication = not patient.has_testing_indication and patient.h_pylori_test_positive is None
        test_negative = patient.h_pylori_test_positive is False
        has_alarm     = patient.has_alarm_features
        is_pregnant   = bool(patient.pregnant_or_nursing)
        is_positive   = patient.h_pylori_test_positive is True
        went_to_tx    = "TREATMENT" in action_categories or "REFERRAL" in action_categories
        urgent_ref    = "URGENT" in action_urgencies
        has_followup  = "FOLLOW_UP" in action_categories
        is_pediatric  = patient.age is not None and patient.age < 18

        # ── COLOUR PALETTE ────────────────────────────────────────────────
        C_MAIN    = "#16a34a"
        C_UNVISIT = "#475569"
        C_DIAMOND = "#1d4ed8"
        C_URGENT  = "#dc2626"
        C_EXIT    = "#d97706"
        C_TEXT    = "#ffffff"
        C_DIM     = "#94a3b8"
        C_BG      = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis:   return C_UNVISIT
            if urgent:    return C_URGENT
            if exit_:     return C_EXIT
            return C_MAIN

        def dc(vis): return C_DIAMOND if vis else C_UNVISIT

        # ── SVG HELPERS ───────────────────────────────────────────────────
        # FIX 2: All text is rendered with explicit SVG <text> / <tspan>
        # inside node boundaries. Node sizes are generous so text never clips.

        svg = []
        W, H = 700, 950

        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" viewBox="0 0 {W} {H}" style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">')

        # Arrow markers
        svg.append("""<defs>
  <marker id="ma"  markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>
  <marker id="mg"  markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>
  <marker id="mr"  markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>
  <marker id="mo"  markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>
</defs>""")

        # marker ids by state
        def mid(vis, urgent=False, exit_=False):
            if not vis:  return "ma"
            if urgent:   return "mr"
            if exit_:    return "mo"
            return "mg"

        def svgt(x, y, text, fill, size=11, bold=False, anchor="middle"):
            w = "bold" if bold else "normal"
            svg.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{fill}" font-size="{size}" font-weight="{w}">{text}</text>')

        def rect_node(x, y, w, h, color, line1, line2="", sub="", rx=8):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(x+w/2, y+h/2-8,  line1, tc, 11, True)
                svgt(x+w/2, y+h/2+7,  line2, tc, 11, True)
            else:
                svgt(x+w/2, y+h/2+4,  line1, tc, 11, True)
            if sub:
                svgt(x+w/2, y+h-8, sub, tc+"99", 9)

        def diamond_node(cx, cy, w, h, color, line1, line2=""):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            hw, hh = w/2, h/2
            pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
            svg.append(f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(cx, cy-7,  line1, tc, 10, True)
                svgt(cx, cy+8,  line2, tc, 10, True)
            else:
                svgt(cx, cy+4,  line1, tc, 10, True)

        def exit_node(x, y, w, h, color, line1, line2="", rx=7):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(x+w/2, y+h/2-7, line1, tc, 10, True)
                svgt(x+w/2, y+h/2+7, line2, tc, 9)
            else:
                svgt(x+w/2, y+h/2+4, line1, tc, 10, True)

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg":"#16a34a","mr":"#dc2626","mo":"#d97706"}.get(m,"#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt(x+6, (y1+y2)/2-3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg":"#16a34a","mr":"#dc2626","mo":"#d97706"}.get(m,"#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                mx = (x1+x2)/2
                svgt(mx, y1-5, label, stroke, 10, True)

        # ── LAYOUT CONSTANTS ─────────────────────────────────────────────
        CX   = 350        # centre x of main column
        NW, NH  = 170, 50  # rect node
        DW, DH  = 180, 58  # diamond node
        EW, EH  = 140, 46  # exit node
        LEXT = 30          # left exit x
        REXT = W - 30 - EW # right exit x

        # Row Y values (top of each row's element)
        Y = {
            "present":  18,
            "d_test":   100,
            "order":    202,
            "d_result": 295,
            "d_alarm":  398,
            "d_preg":   498,
            "washout":  598,
            "treat":    688,
            "d_erad":   778,
            "complete": 878,
        }

        # ── DRAW NODES + ARROWS ───────────────────────────────────────────

        # 0. Patient Presents
        rect_node(CX-NW/2, Y["present"], NW, NH, nc(True), "Patient Presents")

        # 1. Testing Indication? (diamond)
        vline(CX, Y["present"]+NH, Y["d_test"], True)
        diamond_node(CX, Y["d_test"]+DH/2, DW, DH, dc(not is_pediatric),
                     "1. Testing", "Indication?")

        # Exit RIGHT: Pediatric
        exit_node(REXT, Y["d_test"]+(DH-EH)/2, EW, EH,
                  nc(is_pediatric, urgent=True), "Refer Peds GI", "Age < 18")
        elbow_line(CX+DW/2, Y["d_test"]+DH/2, REXT, Y["d_test"]+(DH-EH)/2+EH/2,
                   is_pediatric, urgent=True, label="Age<18")

        # Exit LEFT: No Indication
        exit_node(LEXT, Y["d_test"]+(DH-EH)/2, EW, EH,
                  nc(no_indication, exit_=True), "No Indication", "Reassess")
        elbow_line(CX-DW/2, Y["d_test"]+DH/2, LEXT+EW, Y["d_test"]+(DH-EH)/2+EH/2,
                   no_indication, exit_=True, label="No")

        # 2. Order Test
        v2 = not no_indication and not is_pediatric
        vline(CX, Y["d_test"]+DH, Y["order"], v2, label="Yes")
        rect_node(CX-NW/2, Y["order"], NW, NH, nc(v2),
                  "Order HpSAT / UBT", sub="Pre-test washout req.")

        # 3. Test Result? (diamond)
        v_res = patient.h_pylori_test_positive is not None
        vline(CX, Y["order"]+NH, Y["d_result"], v_res)
        diamond_node(CX, Y["d_result"]+DH/2, DW, DH, dc(v_res),
                     "3. H. pylori", "Test Result?")

        # Exit LEFT: Negative
        exit_node(LEXT, Y["d_result"]+(DH-EH)/2, EW, EH,
                  nc(test_negative, exit_=True), "Negative", "→ Dyspepsia Path")
        elbow_line(CX-DW/2, Y["d_result"]+DH/2, LEXT+EW, Y["d_result"]+(DH-EH)/2+EH/2,
                   test_negative, exit_=True, label="−")

        # 4. Alarm Features? (diamond)
        vline(CX, Y["d_result"]+DH, Y["d_alarm"], is_positive, label="+")
        diamond_node(CX, Y["d_alarm"]+DH/2, DW, DH, dc(is_positive),
                     "2. Alarm", "Features?")

        # Exit RIGHT: Urgent Refer
        v_alarm = has_alarm and is_positive
        exit_node(REXT, Y["d_alarm"]+(DH-EH)/2, EW, EH,
                  nc(v_alarm, urgent=True), "⚠ Urgent Refer", "GI / Endoscopy")
        elbow_line(CX+DW/2, Y["d_alarm"]+DH/2, REXT, Y["d_alarm"]+(DH-EH)/2+EH/2,
                   v_alarm, urgent=True, label="Yes")

        # 5. Pregnancy? (diamond)
        v4 = is_positive and not has_alarm
        vline(CX, Y["d_alarm"]+DH, Y["d_preg"], v4, label="No")
        diamond_node(CX, Y["d_preg"]+DH/2, DW, DH, dc(v4),
                     "Pregnancy /", "Nursing?")

        # Exit RIGHT: Pregnant
        v_preg = is_pregnant and is_positive
        exit_node(REXT, Y["d_preg"]+(DH-EH)/2, EW, EH,
                  nc(v_preg, urgent=True), "Do Not Treat", "Reassess postpartum")
        elbow_line(CX+DW/2, Y["d_preg"]+DH/2, REXT, Y["d_preg"]+(DH-EH)/2+EH/2,
                   v_preg, urgent=True, label="Yes")

        # 6. Washout Verified
        v5 = v4 and not is_pregnant
        vline(CX, Y["d_preg"]+DH, Y["washout"], v5, label="No")
        rect_node(CX-NW/2, Y["washout"], NW, NH, nc(v5),
                  "Washout Verified", sub="Abx / PPI / Bismuth")

        # 7. Treatment Selection
        vline(CX, Y["washout"]+NH, Y["treat"], went_to_tx)
        rect_node(CX-NW/2, Y["treat"], NW, NH, nc(went_to_tx),
                  "4. Treatment", "Selection", sub="1st/2nd/3rd/4th Line")

        # 8. Eradication Confirmed? (diamond)
        vline(CX, Y["treat"]+NH, Y["d_erad"], has_followup)
        diamond_node(CX, Y["d_erad"]+DH/2, DW, DH, dc(has_followup),
                     "5. Eradication", "Confirmed?")

        # Exit RIGHT: Failure
        exit_node(REXT, Y["d_erad"]+(DH-EH)/2, EW, EH,
                  nc(urgent_ref, urgent=True, exit_=not urgent_ref),
                  "Failure", "→ Next Line / Refer GI")
        elbow_line(CX+DW/2, Y["d_erad"]+DH/2, REXT, Y["d_erad"]+(DH-EH)/2+EH/2,
                   urgent_ref or has_followup, urgent=urgent_ref, exit_=not urgent_ref, label="No")

        # 9. Pathway Complete
        v8 = has_followup and not urgent_ref
        vline(CX, Y["d_erad"]+DH, Y["complete"], v8, exit_=v8, label="Yes")
        rect_node(CX-NW/2, Y["complete"], NW, NH, nc(v8, exit_=v8),
                  "Pathway Complete", sub="Re-infection < 2%")

        # Legend bar
        ly = H - 22
        items = [(C_MAIN,"Visited"),(C_DIAMOND,"Decision"),(C_URGENT,"Urgent"),
                 (C_EXIT,"Exit/Off-ramp"),(C_UNVISIT,"Not reached")]
        lx = 18
        for col, label in items:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, label, "#94a3b8", 10, anchor="start")
            lx += 110

        svg.append("</svg>")
        svg_str = "\n".join(svg)

        st.subheader("🗺️ Pathway Followed")
        components.html(
            f'<div style="background:{C_BG};padding:10px;border-radius:14px;overflow-x:auto">{svg_str}</div>',
            height=980, scrolling=True
        )

        # ── CLINICAL RECOMMENDATIONS ──────────────────────────────────────
        st.markdown("---")
        st.subheader("Clinical Recommendations")

        test_str = {None:"Not yet tested", True:"✅ Positive", False:"❌ Negative"}[patient.h_pylori_test_positive]
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
</div>""", unsafe_allow_html=True)

        cat_icon = {
            "TREATMENT":"💊","REFERRAL":"📋","TESTING":"🧪",
            "FOLLOW_UP":"🔁","CLINICAL_NOTE":"📝",
            "CONTRAINDICATION":"🚫","EXCLUSION":"🚫","ROUTING":"↪️",
        }
        urgency_cls = {"URGENT":"urgent","ROUTINE":"routine","INFO":"info","NONE":"info"}

        for action in actions:
            cls  = urgency_cls.get(action.urgency, "info")
            icon = cat_icon.get(action.category, "📌")
            badge = f'<span class="badge {cls}">{action.urgency if action.urgency!="INFO" else action.category}</span>'
            items_html = "".join(f"<li>{d}</li>" for d in action.details if d.strip()) if action.details else ""
            detail_html = f"<ul>{items_html}</ul>" if items_html else ""
            st.markdown(f"""
<div class="action-card {cls}">
  <h4>{badge}{icon} {action.category}: {action.description}</h4>
  {detail_html}
</div>""", unsafe_allow_html=True)

        with st.expander("📋 Decision Audit Log"):
            from datetime import datetime
            for step in engine.tracker.steps:
                try:    ts = datetime.fromisoformat(step.timestamp).strftime("%H:%M:%S")
                except: ts = "—"
                st.markdown(f"**[{ts}] {step.rule}** → _{step.decision}_")
                if step.inputs:
                    st.caption("  ".join(f"`{k}={v}`" for k,v in step.inputs.items()))
    else:
        st.info("👈 Fill in patient details on the left, then click **▶ Run Pathway**.")
