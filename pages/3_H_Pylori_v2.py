h pylori v2


import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import streamlit.components.v1 as components
from h_pylori_engine_v2 import run_h_pylori_pathway, Action, DataRequest, Stop, Override
from datetime import datetime

st.set_page_config(page_title="H. Pylori", page_icon="🦠", layout="wide")

# ── GLOBAL CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
.ctx-card {
    background: #1e3a5f; border: 1px solid #2e5c8a;
    border-radius: 10px; padding: 14px 18px;
    margin-bottom: 14px; font-size: 14px; color: #e2e8f0;
}
.ctx-card b { color: #93c5fd; }
.section-label {
    font-size: 11px; font-weight: 700; letter-spacing: 1.2px;
    color: #94a3b8; margin-bottom: 6px; margin-top: 18px;
}
.action-card { border-radius: 10px; padding: 14px 18px; margin-bottom: 12px; font-size: 13.5px; line-height: 1.6; }
.action-card.urgent  { background:#3b0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.action-card.routine { background:#052e16; border-left:5px solid #22c55e; color:#bbf7d0; }
.action-card.info    { background:#0c1a2e; border-left:5px solid #3b82f6; color:#bfdbfe; }
.action-card.warning { background:#2d1a00; border-left:5px solid #f59e0b; color:#fde68a; }
.action-card.stop    { background:#2d0a0a; border-left:5px solid #ef4444; color:#fecaca; }
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
.badge.warning { background:#f59e0b; color:#000; }
.badge.stop    { background:#ef4444; color:#fff; }
.override-card {
    background:#1a1a2e; border:1px dashed #6366f1;
    border-radius:8px; padding:10px 14px; margin-top:8px; font-size:13px; color:#c7d2fe;
}
</style>
""", unsafe_allow_html=True)

st.title("🦠 H. Pylori Pathway")
st.markdown("---")

# ── SESSION STATE for overrides ──────────────────────────────────────────────
if "hp_overrides" not in st.session_state:
    st.session_state.hp_overrides = []

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 52)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**Pregnancy / Nursing**")
    pregnant     = st.checkbox("Pregnant")
    breastfeeding = st.checkbox("Breastfeeding / Nursing")

    st.markdown("**Testing Indication**")
    dyspepsia      = st.checkbox("Dyspepsia symptoms")
    ulcer_hx       = st.checkbox("History of ulcer or GI bleed")
    family_gastric = st.checkbox("Personal/family history of gastric cancer")
    immigrant_prev = st.checkbox("Immigrant from high-prevalence region")

    st.markdown("**H. Pylori Test**")
    hp_result_sel = st.selectbox("Result", ["Not tested", "Positive", "Negative"])
    hp_result_map = {"Not tested": None, "Positive": "positive", "Negative": "negative"}
    hp_test_type  = st.selectbox("Test type", ["HpSAT", "UBT", "Other"])

    st.markdown("**Washout Status**")
    off_abx     = st.checkbox("Off antibiotics ≥4 weeks", value=True)
    off_ppi     = st.checkbox("Off PPIs ≥2 weeks",        value=True)
    off_bismuth = st.checkbox("Off bismuth ≥2 weeks",     value=True)

    st.markdown("**Alarm Features**")
    al_family_cancer  = st.checkbox("Family hx esophageal/gastric cancer")
    al_ulcer_hx       = st.checkbox("Personal history of peptic ulcer")
    al_age_symptoms   = st.checkbox("Age >60 with new persistent symptoms")
    al_weight_loss    = st.checkbox("Unintended weight loss >5%")
    al_dysphagia      = st.checkbox("Progressive dysphagia")
    al_vomiting       = st.checkbox("Persistent vomiting")
    al_gi_bleed       = st.checkbox("Black stool or blood in vomit")
    al_ida            = st.checkbox("Iron deficiency anemia")
    al_concern        = st.checkbox("Clinician concern — serious pathology")

    st.markdown("**Treatment History**")
    penicillin_allergy = st.checkbox("Penicillin allergy")
    tx_line_sel = st.selectbox("Treatment line",
        ["1 – Naive (no prior treatment)",
         "2 – Second line (1 prior failure)",
         "3 – Third line (2 prior failures)",
         "4 – Fourth line (3 prior failures)"])
    tx_map = {
        "1 – Naive (no prior treatment)":       1,
        "2 – Second line (1 prior failure)":    2,
        "3 – Third line (2 prior failures)":    3,
        "4 – Fourth line (3 prior failures)":   4,
    }
    bubble_pack = st.checkbox("Bubble/blister pack NOT being used", value=False)
    nonadherence = st.checkbox("Non-adherence suspected")

    # Eradication follow-up (shown if test was done)
    if hp_result_map[hp_result_sel] is not None:
        st.markdown("**Eradication Follow-up** *(post-treatment)*")
        erad_result_sel = st.selectbox("Eradication test result",
            ["Not done", "Negative (eradicated)", "Positive (failed)"])
        erad_map = {"Not done": None, "Negative (eradicated)": "negative", "Positive (failed)": "positive"}
        symptoms_persist = st.selectbox("Symptoms still persisting?", ["Unknown", "Yes", "No"])
        sp_map = {"Unknown": None, "Yes": True, "No": False}
    else:
        erad_map = {"Not done": None}
        erad_result_sel = "Not done"
        sp_map = {"Unknown": None}
        symptoms_persist = "Unknown"

    run = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.hp_overrides = []
        st.rerun()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if run:
        patient_data = {
            "age":                       age,
            "sex":                       sex,
            "pregnant":                  pregnant or None,
            "breastfeeding":             breastfeeding or None,
            "dyspepsia_symptoms":        dyspepsia or None,
            "current_or_past_gastric_or_duodenal_ulcer_or_upper_gi_bleed": ulcer_hx or None,
            "personal_or_first_degree_relative_history_gastric_cancer":     family_gastric or None,
            "first_generation_immigrant_high_prevalence_region":            immigrant_prev or None,
            "hp_test_type":              hp_test_type if hp_result_map[hp_result_sel] else None,
            "hp_test_result":            hp_result_map[hp_result_sel],
            "off_antibiotics_4_weeks_before_test": off_abx,
            "off_ppi_2_weeks_before_test":         off_ppi,
            "off_bismuth_2_weeks_before_test":     off_bismuth,
            "penicillin_allergy":        penicillin_allergy or None,
            "treatment_line":            tx_map[tx_line_sel],
            "bubble_pack_used":          not bubble_pack,
            "nonadherence_suspected":    nonadherence or None,
            "family_history_esophageal_or_gastric_cancer_first_degree": al_family_cancer or None,
            "personal_history_peptic_ulcer_disease":                    al_ulcer_hx or None,
            "age_over_60_new_persistent_symptoms_over_3_months":        al_age_symptoms or None,
            "unintended_weight_loss":    al_weight_loss or None,
            "progressive_dysphagia":     al_dysphagia or None,
            "persistent_vomiting_not_cannabis_related": al_vomiting or None,
            "black_stool_or_blood_in_vomit": al_gi_bleed or None,
            "iron_deficiency_anemia_present": al_ida or None,
            "clinician_concern_serious_pathology": al_concern or None,
            "eradication_test_result":   erad_map.get(erad_result_sel),
            "symptoms_persist":          sp_map.get(symptoms_persist),
            "off_antibiotics_4_weeks_before_retest": off_abx,
            "off_ppi_2_weeks_before_retest": off_ppi,
        }

        outputs, logs, applied_overrides = run_h_pylori_pathway(
            patient_data, overrides=st.session_state.hp_overrides
        )

        # ── PATH STATE FLAGS for flowchart ────────────────────────────────
        is_positive    = patient_data.get("hp_test_result") == "positive"
        test_negative  = patient_data.get("hp_test_result") == "negative"
        no_indication  = not any([dyspepsia, ulcer_hx, family_gastric, immigrant_prev])                          and patient_data.get("hp_test_result") is None
        has_alarm      = any(isinstance(o, Stop) and "alarm" in o.reason.lower() for o in outputs)
        is_pregnant    = bool(pregnant or breastfeeding)
        went_to_tx     = any(isinstance(o, Action) and "TREAT" in o.code for o in outputs)
        has_followup   = any(isinstance(o, Action) and "RETEST" in o.code for o in outputs)
        urgent_ref     = any(isinstance(o, Stop) and getattr(o, "urgency", "") == "urgent" for o in outputs)
        is_pediatric   = age < 18
        has_dr         = any(isinstance(o, DataRequest) for o in outputs)

        # ── SVG FLOWCHART (identical visual style) ────────────────────────
        C_MAIN    = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT  = "#dc2626"; C_EXIT    = "#d97706"; C_TEXT    = "#ffffff"
        C_DIM     = "#94a3b8"; C_BG      = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis:  return C_UNVISIT
            if urgent:   return C_URGENT
            if exit_:    return C_EXIT
            return C_MAIN
        def dc(vis): return C_DIAMOND if vis else C_UNVISIT

        svg = []
        W, H = 700, 950
        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" viewBox="0 0 {W} {H}" style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">')
        svg.append("""<defs>
  <marker id="ma" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>
  <marker id="mg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>
  <marker id="mr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>
  <marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>
</defs>""")

        def mid(vis, urgent=False, exit_=False):
            if not vis: return "ma"
            if urgent:  return "mr"
            if exit_:   return "mo"
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
            if sub: svgt(x+w/2, y+h-8, sub, tc+"99", 9)

        def diamond_node(cx, cy, w, h, color, line1, line2=""):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            hw, hh = w/2, h/2
            pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
            svg.append(f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(cx, cy-7, line1, tc, 10, True)
                svgt(cx, cy+8, line2, tc, 10, True)
            else:
                svgt(cx, cy+4, line1, tc, 10, True)

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
            if label: svgt(x+6, (y1+y2)/2-3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg":"#16a34a","mr":"#dc2626","mo":"#d97706"}.get(m,"#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt((x1+x2)/2, y1-5, label, stroke, 10, True)

        CX = 350; NW, NH = 170, 50; DW, DH = 180, 58; EW, EH = 140, 46
        LEXT = 30; REXT = W - 30 - EW
        Y = {"present":18,"d_test":100,"order":202,"d_result":295,"d_alarm":398,
             "d_preg":498,"washout":598,"treat":688,"d_erad":778,"complete":878}

        rect_node(CX-NW/2, Y["present"], NW, NH, nc(True), "Patient Presents")
        vline(CX, Y["present"]+NH, Y["d_test"], True)
        diamond_node(CX, Y["d_test"]+DH/2, DW, DH, dc(not is_pediatric), "1. Testing", "Indication?")
        exit_node(REXT, Y["d_test"]+(DH-EH)/2, EW, EH, nc(is_pediatric, urgent=True), "Refer Peds GI", "Age < 18")
        elbow_line(CX+DW/2, Y["d_test"]+DH/2, REXT, Y["d_test"]+(DH-EH)/2+EH/2, is_pediatric, urgent=True, label="Age<18")
        exit_node(LEXT, Y["d_test"]+(DH-EH)/2, EW, EH, nc(no_indication, exit_=True), "No Indication", "Reassess")
        elbow_line(CX-DW/2, Y["d_test"]+DH/2, LEXT+EW, Y["d_test"]+(DH-EH)/2+EH/2, no_indication, exit_=True, label="No")

        v2 = not no_indication and not is_pediatric
        vline(CX, Y["d_test"]+DH, Y["order"], v2, label="Yes")
        rect_node(CX-NW/2, Y["order"], NW, NH, nc(v2), "Order HpSAT / UBT", sub="Pre-test washout req.")

        v_res = patient_data.get("hp_test_result") is not None
        vline(CX, Y["order"]+NH, Y["d_result"], v_res)
        diamond_node(CX, Y["d_result"]+DH/2, DW, DH, dc(v_res), "3. H. pylori", "Test Result?")
        exit_node(LEXT, Y["d_result"]+(DH-EH)/2, EW, EH, nc(test_negative, exit_=True), "Negative", "→ Dyspepsia Path")
        elbow_line(CX-DW/2, Y["d_result"]+DH/2, LEXT+EW, Y["d_result"]+(DH-EH)/2+EH/2, test_negative, exit_=True, label="−")

        vline(CX, Y["d_result"]+DH, Y["d_alarm"], is_positive, label="+")
        diamond_node(CX, Y["d_alarm"]+DH/2, DW, DH, dc(is_positive), "2. Alarm", "Features?")
        exit_node(REXT, Y["d_alarm"]+(DH-EH)/2, EW, EH, nc(has_alarm and is_positive, urgent=True), "⚠ Urgent Refer", "GI / Endoscopy")
        elbow_line(CX+DW/2, Y["d_alarm"]+DH/2, REXT, Y["d_alarm"]+(DH-EH)/2+EH/2, has_alarm and is_positive, urgent=True, label="Yes")

        v4 = is_positive and not has_alarm
        vline(CX, Y["d_alarm"]+DH, Y["d_preg"], v4, label="No")
        diamond_node(CX, Y["d_preg"]+DH/2, DW, DH, dc(v4), "Pregnancy /", "Nursing?")
        v_preg = is_pregnant and is_positive
        exit_node(REXT, Y["d_preg"]+(DH-EH)/2, EW, EH, nc(v_preg, urgent=True), "Do Not Treat", "Reassess postpartum")
        elbow_line(CX+DW/2, Y["d_preg"]+DH/2, REXT, Y["d_preg"]+(DH-EH)/2+EH/2, v_preg, urgent=True, label="Yes")

        v5 = v4 and not is_pregnant
        vline(CX, Y["d_preg"]+DH, Y["washout"], v5, label="No")
        rect_node(CX-NW/2, Y["washout"], NW, NH, nc(v5), "Washout Verified", sub="Abx / PPI / Bismuth")
        vline(CX, Y["washout"]+NH, Y["treat"], went_to_tx)
        rect_node(CX-NW/2, Y["treat"], NW, NH, nc(went_to_tx), "4. Treatment", "Selection", sub="1st/2nd/3rd/4th Line")
        vline(CX, Y["treat"]+NH, Y["d_erad"], has_followup)
        diamond_node(CX, Y["d_erad"]+DH/2, DW, DH, dc(has_followup), "5. Eradication", "Confirmed?")
        exit_node(REXT, Y["d_erad"]+(DH-EH)/2, EW, EH,
                  nc(urgent_ref, urgent=True, exit_=not urgent_ref), "Failure", "→ Next Line / Refer GI")
        elbow_line(CX+DW/2, Y["d_erad"]+DH/2, REXT, Y["d_erad"]+(DH-EH)/2+EH/2,
                   urgent_ref or has_followup, urgent=urgent_ref, exit_=not urgent_ref, label="No")
        v8 = has_followup and not urgent_ref
        vline(CX, Y["d_erad"]+DH, Y["complete"], v8, exit_=v8, label="Yes")
        rect_node(CX-NW/2, Y["complete"], NW, NH, nc(v8, exit_=v8), "Pathway Complete", sub="Re-infection < 2%")

        ly = H - 22
        lx = 18
        for col, lbl in [(C_MAIN,"Visited"),(C_DIAMOND,"Decision"),(C_URGENT,"Urgent"),(C_EXIT,"Exit/Off-ramp"),(C_UNVISIT,"Not reached")]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 110
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            f'<div style="background:{C_BG};padding:10px;border-radius:14px;overflow-x:auto">{"".join(svg)}</div>',
            height=980, scrolling=True
        )

        # ── CLINICAL RECOMMENDATIONS ──────────────────────────────────────
        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # Patient context
        hp_disp = {"positive":"✅ Positive","negative":"❌ Negative",None:"Not yet tested"}
        test_str  = hp_disp.get(patient_data.get("hp_test_result"), "—")
        tx_labels = {1:"Treatment Naive",2:"Second Line",3:"Third Line",4:"Fourth Line"}
        alarm_fields = [
            ("family_history_esophageal_or_gastric_cancer_first_degree","Family hx cancer"),
            ("personal_history_peptic_ulcer_disease","Peptic ulcer hx"),
            ("age_over_60_new_persistent_symptoms_over_3_months","Age>60 new symptoms"),
            ("unintended_weight_loss","Weight loss"),
            ("progressive_dysphagia","Dysphagia"),
            ("persistent_vomiting_not_cannabis_related","Persistent vomiting"),
            ("black_stool_or_blood_in_vomit","GI bleed signs"),
            ("iron_deficiency_anemia_present","IDA"),
            ("clinician_concern_serious_pathology","Clinician concern"),
        ]
        active_alarms = [label for key, label in alarm_fields if patient_data.get(key)]
        alarm_str = ", ".join(active_alarms) if active_alarms else "None"

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(f"""
<div class="ctx-card">
  <span>🧑 <b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>
  <span>🦠 <b>H. Pylori Test:</b> {test_str}</span><br>
  <span>💊 <b>Treatment Line:</b> {tx_labels.get(tx_map[tx_line_sel],"—")}</span><br>
  <span>⚠️ <b>Alarm Features:</b> {alarm_str}</span>
</div>""", unsafe_allow_html=True)

        # Render outputs
        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        override_candidates = []   # collect actions that support overrides

        def render_action(a: Action, extra_cls=""):
            urgency_to_cls = {"urgent":"urgent","warning":"warning",None:"routine","":"routine"}
            cls = urgency_to_cls.get(a.urgency or "", "routine")
            if extra_cls: cls = extra_cls
            badge_label = (a.urgency or "info").upper()
            detail_items = ""
            if isinstance(a.details, dict):
                detail_items = "".join(
                    f"<li><b>{k}:</b> {v}</li>"
                    for k, v in a.details.items()
                    if k not in ("supported_by",) and v not in (None, False, "")
                )
            elif isinstance(a.details, list):
                detail_items = "".join(f"<li>{d}</li>" for d in a.details if str(d).strip())
            detail_html = f"<ul>{detail_items}</ul>" if detail_items else ""
            st.markdown(f"""
<div class="action-card {cls}">
  <h4><span class="badge {cls}">{badge_label}</span> {a.label}</h4>
  {detail_html}
</div>""", unsafe_allow_html=True)
            if a.override_options:
                override_candidates.append(a)

        for output in outputs:
            if isinstance(output, Action):
                render_action(output)

            elif isinstance(output, DataRequest):
                missing_str = ", ".join(f"`{f}`" for f in output.missing_fields)
                st.markdown(f"""
<div class="action-card warning">
  <h4><span class="badge warning">DATA NEEDED</span> ⏳ {output.message}</h4>
  <ul><li>Missing fields: {missing_str}</li></ul>
</div>""", unsafe_allow_html=True)
                for sa in output.suggested_actions:
                    render_action(sa, extra_cls="info")

            elif isinstance(output, Stop):
                st.markdown(f"""
<div class="action-card stop">
  <h4><span class="badge stop">STOP</span> 🛑 {output.reason}</h4>
</div>""", unsafe_allow_html=True)
                for a in output.actions:
                    render_action(a)

        # ── CLINICIAN OVERRIDE PANEL ───────────────────────────────────────
        if override_candidates:
            st.markdown("---")
            st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
            st.caption("Override engine decisions where clinical judgement differs. A reason is required for each override.")

            for a in override_candidates:
                opt = a.override_options
                node  = opt["node"]
                field = opt["field"]
                allowed = opt.get("allowed", [True, False])

                with st.expander(f"⚙️ Override: **{node}** → `{field}`"):
                    st.markdown(f'<div class="override-card">Engine decision based on: <b>{a.label}</b></div>', unsafe_allow_html=True)

                    # Check if already overridden
                    existing = next(
                        (o for o in st.session_state.hp_overrides
                         if o.target_node == node and o.field == field), None
                    )
                    current_val = existing.new_value if existing else None

                    new_val = st.radio(
                        f"Set `{field}` to:",
                        options=allowed,
                        index=allowed.index(current_val) if current_val in allowed else 0,
                        key=f"ov_val_{node}_{field}",
                        horizontal=True,
                    )
                    reason = st.text_input(
                        "Reason (required):",
                        value=existing.reason if existing else "",
                        key=f"ov_reason_{node}_{field}",
                        placeholder="Document clinical rationale..."
                    )

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ Apply Override", key=f"ov_apply_{node}_{field}"):
                            if not reason.strip():
                                st.error("A reason is required to apply an override.")
                            else:
                                # Remove existing override for same node+field
                                st.session_state.hp_overrides = [
                                    o for o in st.session_state.hp_overrides
                                    if not (o.target_node == node and o.field == field)
                                ]
                                st.session_state.hp_overrides.append(Override(
                                    target_node=node,
                                    field=field,
                                    old_value=None,
                                    new_value=new_val,
                                    reason=reason.strip(),
                                ))
                                st.success(f"Override applied. Click **▶ Run Pathway** to re-evaluate.")

                    with col2:
                        if existing and st.button(f"🗑 Remove Override", key=f"ov_remove_{node}_{field}"):
                            st.session_state.hp_overrides = [
                                o for o in st.session_state.hp_overrides
                                if not (o.target_node == node and o.field == field)
                            ]
                            st.success("Override removed.")

            # Show active overrides summary
            if st.session_state.hp_overrides:
                st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                for o in st.session_state.hp_overrides:
                    st.markdown(f"""
<div class="override-card">
  🔧 <b>{o.target_node}</b> → <code>{o.field}</code> set to <b>{o.new_value}</b><br>
  <span style="color:#a5b4fc">Reason: {o.reason}</span><br>
  <span style="color:#64748b;font-size:11px">Applied: {o.created_at.strftime("%H:%M:%S")}</span>
</div>""", unsafe_allow_html=True)

        # ── DECISION AUDIT LOG ─────────────────────────────────────────────
        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try:    ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except: ts = "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if log.used_inputs:
                    st.caption("  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None))

    else:
        st.info("👈 Fill in patient details on the left, then click **▶ Run Pathway**.")
