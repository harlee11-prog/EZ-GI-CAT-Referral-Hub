import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from liver_mass_engine import (
    run_liver_mass_pathway,
    Action,
    DataRequest,
    Stop,
    Override,
)

st.set_page_config(page_title="Liver Mass", page_icon="🫀", layout="wide")


# ── HELPERS ───────────────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title()


def build_liver_mass_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Liver Mass Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    lines.append(
        f"- **Age / Sex:** {patient_data.get('age')} / "
        f"{str(patient_data.get('sex', '')).capitalize()}"
    )
    lines.append(f"- **Lesion Type:** {_safe_text(patient_data.get('lesion_type', 'Not specified'))}")
    lines.append(f"- **Lesion Size:** {patient_data.get('lesion_size_cm', 'Not specified')} cm")
    lines.append(f"- **Imaging Modality:** {_safe_text(patient_data.get('imaging_modality', 'Not specified'))}")
    
    high_risk = any([
        patient_data.get('history_cirrhosis'),
        patient_data.get('chronic_hepatitis_b'),
        patient_data.get('chronic_hepatitis_c'),
        patient_data.get('prior_malignancy_any_location'),
        patient_data.get('clinician_concern_malignancy')
    ])
    lines.append(f"- **High-Risk Factors Present:** {'Yes' if high_risk else 'No'}")
    
    red_flag = patient_data.get('episodic_epigastric_or_ruq_pain') and patient_data.get('hypotension')
    lines.append(f"- **Red Flag (Hemorrhage):** {'Yes' if red_flag else 'No'}")
    lines.append("")

    lines.append("## Clinical Recommendations")
    if not outputs:
        lines.append("- No recommendations generated.")
    else:
        for o in outputs:
            if isinstance(o, Action):
                urgency = (o.urgency or "info").upper()
                label = _safe_text(o.label)
                lines.append(f"- **[{urgency}]** {label}")
                if isinstance(o.details, dict):
                    for k, v in o.details.items():
                        if v not in (None, False, "", []):
                            lines.append(f"  - {_pretty(k)}: {_safe_text(str(v))}")
            elif isinstance(o, Stop):
                reason = _safe_text(o.reason)
                lines.append(f"- **[STOP]** {reason}")
                if getattr(o, "actions", None):
                    for a in o.actions:
                        lines.append(f"  - Follow-up: {_safe_text(a.label)}")
            elif isinstance(o, DataRequest):
                msg = _safe_text(o.message)
                missing = ", ".join(f for f in o.missing_fields)
                lines.append(f"- **[DATA NEEDED]** {msg}")
                lines.append(f"  - Missing fields: {missing}")
    lines.append("")
    lines.append("## Active Overrides")
    if overrides:
        for ov in overrides:
            lines.append(
                f"- **{_safe_text(ov.target_node)}."
                f"{_safe_text(ov.field)}** → "
                f"`{_safe_text(ov.new_value)}` "
                f"(Reason: {_safe_text(ov.reason)})"
            )
    else:
        lines.append("- No active overrides.")
    lines.append("")
    lines.append("## Clinician Notes")
    lines.append(
        notes.strip() if notes and notes.strip() else "No clinician notes entered."
    )
    lines.append("")
    return "\n".join(lines)


# ── GLOBAL CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
.ctx-card {
  background:#1e3a5f;border:1px solid #2e5c8a;
  border-radius:10px;padding:14px 18px;
  margin-bottom:14px;font-size:14px;color:#e2e8f0;
}
.ctx-card b { color:#93c5fd; }
.section-label {
  font-size:11px;font-weight:700;letter-spacing:1.2px;
  color:#94a3b8;margin-bottom:6px;margin-top:18px;
}
.action-card {
  border-radius:10px;padding:14px 18px;
  margin-bottom:12px;font-size:13.5px;line-height:1.6;
}
.action-card.urgent {background:#3b0a0a;border-left:5px solid #ef4444;color:#fecaca;}
.action-card.routine{background:#052e16;border-left:5px solid #22c55e;color:#bbf7d0;}
.action-card.info   {background:#0c1a2e;border-left:5px solid #3b82f6;color:#bfdbfe;}
.action-card.warning{background:#2d1a00;border-left:5px solid #f59e0b;color:#fde68a;}
.action-card.stop   {background:#2d0a0a;border-left:5px solid #ef4444;color:#fecaca;}
.badge{
  display:inline-block;font-size:11px;font-weight:bold;
  padding:2px 8px;border-radius:20px;margin-right:6px;
  text-transform:uppercase;letter-spacing:0.5px;
}
.badge.urgent{background:#ef4444;color:#fff;}
.badge.routine{background:#22c55e;color:#fff;}
.badge.info{background:#3b82f6;color:#fff;}
.badge.warning{background:#f59e0b;color:#000;}
.badge.stop{background:#ef4444;color:#fff;}
.override-card{
  background:#1a1a2e;border:1px dashed #6366f1;
  border-radius:8px;padding:10px 14px;margin-top:8px;
  font-size:13px;color:#c7d2fe;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("Liver Mass (Solid Lesion) Pathway")
st.markdown("---")


# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "lm_overrides" not in st.session_state:
    st.session_state.lm_overrides = []
if "lm_has_run" not in st.session_state:
    st.session_state.lm_has_run = False
if "lm_notes" not in st.session_state:
    st.session_state.lm_notes = ""

left, right = st.columns([1, 1.5])


# ═════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — INPUTS
# ═════════════════════════════════════════════════════════════════════════════
with left:
    st.subheader("Patient Information")

    age = st.number_input("Age", 18, 120, value=55)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**Imaging Detection**")
    liver_lesion_detected = st.checkbox("Liver lesion detected on imaging", value=True)

    MODALITY_OPTIONS = ["Not specified", "Ultrasound", "CT", "MRI", "Other"]
    modality_sel = st.selectbox("Imaging modality", MODALITY_OPTIONS)
    modality_map = {"Not specified": None, "Ultrasound": "ultrasound", "CT": "ct", "MRI": "mri", "Other": "other"}

    DETECTION_OPTIONS = ["Not specified", "Incidental finding", "Symptomatic presentation"]
    detection_sel = st.selectbox("How was the lesion found?", DETECTION_OPTIONS)
    detection_map = {"Not specified": None, "Incidental finding": "incidental", "Symptomatic presentation": "symptomatic"}

    st.markdown("**Lesion Classification**")
    LESION_OPTIONS = {
        "— Select —": None,
        "Simple cyst": "simple_cyst",
        "Complex cyst": "complex_cyst",
        "Hemangioma": "hemangioma",
        "Focal Nodular Hyperplasia (FNH)": "fnh",
        "Hepatocellular Adenoma": "adenoma",
        "Indeterminate / Suspicious solid": "indeterminate_suspicious",
        "Solid — unspecified": "solid_unspecified",
        "Metastatic disease suspected": "metastatic_disease",
    }
    lesion_type_sel = st.selectbox("Lesion type (from radiology)", list(LESION_OPTIONS.keys()))
    lesion_type = LESION_OPTIONS[lesion_type_sel]

    lesion_size = st.number_input("Lesion size (cm) — 0 if unknown", min_value=0.0, value=0.0, step=0.5)

    char_confident = st.selectbox(
        "Radiology characterization confidence",
        ["Confident", "Limited / Uncertain"],
    )
    radiology_followup = st.checkbox("Radiology recommends further follow-up or evaluation")

    # ── High Risk Factors ─────────────────────────────────────────────────────
    st.markdown("**High-Risk Factors for Malignancy**")
    history_cirrhosis = st.checkbox("History of cirrhosis")
    chronic_hep_b = st.checkbox("Chronic Hepatitis B infection")
    chronic_hep_c = st.checkbox("Chronic Hepatitis C infection")
    prior_malignancy = st.checkbox("Prior malignancy (any location)")
    clinician_concern = st.checkbox("Clinician concern for malignancy (other reason)")

    # ── Red Flag Symptoms ─────────────────────────────────────────────────────
    st.markdown("**🚨 Red Flag — Possible Hemorrhage**")
    epigastric_pain = st.checkbox("Episodic epigastric or RUQ pain")
    hypotension = st.checkbox("Hypotension")

    # ── Associated Symptoms ───────────────────────────────────────────────────
    st.markdown("**Associated Symptoms**")
    weight_loss = st.checkbox("Unintentional weight loss")
    persistent_pain = st.checkbox("Persistent abdominal pain")
    fever = st.checkbox("Fever")
    early_satiety = st.checkbox("Early satiety")

    # ── Sub-Type Details ──────────────────────────────────────────────────────
    is_cyst = lesion_type in {"simple_cyst", "complex_cyst"}
    cyst_features = False
    cyst_symptoms = False
    abnormal_enzymes = False
    possibly_symptomatic = False
    definitive_fnh = False
    fnh_uncertain = False
    pregnant = False
    ocp_use = False
    anabolic_use = False
    adenoma_confirmed = False

    if is_cyst:
        st.markdown("**Cyst Details**")
        cyst_features = st.checkbox("Complex cyst features present (wall thickening, septations, nodules, enhancement)")
        cyst_symptoms = st.checkbox("Symptoms attributable to cyst")
        abnormal_enzymes = st.checkbox("Elevated liver enzymes possibly related to cyst")

    if lesion_type == "hemangioma":
        st.markdown("**Hemangioma Details**")
        possibly_symptomatic = st.checkbox("Possibly symptomatic (e.g. pain)")

    if lesion_type == "fnh":
        st.markdown("**FNH Details**")
        definitive_fnh = st.checkbox("Definitively confirmed as FNH on imaging")
        fnh_uncertain = st.checkbox("FNH characterization uncertain — needs MRI")

    if lesion_type == "adenoma":
        st.markdown("**Adenoma Details**")
        pregnant = st.checkbox("Patient is pregnant")
        ocp_use = st.checkbox("Oral contraceptive use")
        anabolic_use = st.checkbox("Anabolic steroid use")
        adenoma_confirmed = st.checkbox("Adenoma diagnosis confirmed on imaging")

    # ── Workup & Labs ─────────────────────────────────────────────────────────
    with st.expander("Workup & Lab Status (Optional)"):
        advanced_imaging_done = st.checkbox("Advanced imaging (MRI/triphasic CT) already completed")
        biopsy_considered = st.checkbox("Biopsy has been considered / documented")
        referred_hepatology = st.checkbox("Hepatology referral already made")
        referred_surgery = st.checkbox("Hepatobiliary (HPB) surgery referral already made")
        urgent_referral = st.checkbox("Urgent referral requirement documented")
        metastatic_pattern = st.checkbox("Metastatic pattern present on imaging")
        repeat_imaging_planned = st.checkbox("Repeat imaging plan documented")

        col_l, col_r = st.columns(2)
        with col_l:
            alt_val = st.number_input("ALT (U/L)", min_value=0.0, value=0.0, step=1.0)
            ast_val = st.number_input("AST (U/L)", min_value=0.0, value=0.0, step=1.0)
            alp_val = st.number_input("ALP (U/L)", min_value=0.0, value=0.0, step=1.0)
        with col_r:
            bilirubin_val = st.number_input("Bilirubin (μmol/L)", min_value=0.0, value=0.0, step=1.0)
            afp_val = st.number_input("AFP (μg/L)", min_value=0.0, value=0.0, step=0.1)

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.lm_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.lm_overrides = []
        if "lm_saved_output" in st.session_state:
            del st.session_state["lm_saved_output"]

    override_panel = st.container()


# ═════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL
# ═════════════════════════════════════════════════════════════════════════════
with right:
    if not st.session_state.lm_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        patient_data = {
            "age": age,
            "sex": sex,
            "liver_lesion_detected": liver_lesion_detected,
            "imaging_modality": modality_map[modality_sel],
            "incidental_vs_symptomatic": detection_map[detection_sel],
            "lesion_type": lesion_type,
            "lesion_size_cm": lesion_size if lesion_size > 0 else None,
            "lesion_characterization_confident": char_confident == "Confident",
            "radiology_recommends_followup": radiology_followup or None,
            "history_cirrhosis": history_cirrhosis or None,
            "chronic_hepatitis_b": chronic_hep_b or None,
            "chronic_hepatitis_c": chronic_hep_c or None,
            "prior_malignancy_any_location": prior_malignancy or None,
            "clinician_concern_malignancy": clinician_concern or None,
            "episodic_epigastric_or_ruq_pain": epigastric_pain or None,
            "hypotension": hypotension or None,
            "unintentional_weight_loss": weight_loss or None,
            "persistent_abdominal_pain": persistent_pain or None,
            "fever": fever or None,
            "early_satiety": early_satiety or None,
            "cyst_size_cm": lesion_size if lesion_size > 0 else None,
            "cyst_complex_features_present": cyst_features or None,
            "symptoms_attributable_to_cyst": cyst_symptoms or None,
            "abnormal_liver_enzymes": abnormal_enzymes or None,
            "possibly_symptomatic": possibly_symptomatic or None,
            "definitive_fnh": definitive_fnh or None,
            "fnh_uncertain": fnh_uncertain or None,
            "pregnant": pregnant or None,
            "oral_contraceptive_use": ocp_use or None,
            "anabolic_steroid_use": anabolic_use or None,
            "adenoma_confirmed": adenoma_confirmed or None,
            "advanced_imaging_done": advanced_imaging_done or None,
            "biopsy_considered": biopsy_considered or None,
            "referred_to_hepatology": referred_hepatology or None,
            "referred_to_surgery": referred_surgery or None,
            "urgent_referral_required": urgent_referral or None,
            "metastatic_pattern_present": metastatic_pattern or None,
            "repeat_imaging_planned": repeat_imaging_planned or None,
            "alt": alt_val if alt_val > 0 else None,
            "ast": ast_val if ast_val > 0 else None,
            "alp": alp_val if alp_val > 0 else None,
            "bilirubin": bilirubin_val if bilirubin_val > 0 else None,
            "afp": afp_val if afp_val > 0 else None,
        }

        outputs, logs, applied_overrides = run_liver_mass_pathway(
            patient_data, overrides=st.session_state.lm_overrides
        )

        # ── SVG Context Variables ───────────────────────────────────────────
        has_lesion = bool(liver_lesion_detected)
        lesion_class = lesion_type is not None

        hem_flag = False
        high_risk = False

        for ov in st.session_state.lm_overrides:
            if ov.target_node == "Red_Flag_Hemorrhage" and ov.field == "hemorrhage_red_flag":
                hem_flag = ov.new_value
            if ov.target_node == "Solid_Lesion_Risk_Assessment" and ov.field == "high_risk_malignancy":
                high_risk = ov.new_value

        if not any(ov.target_node == "Red_Flag_Hemorrhage" for ov in st.session_state.lm_overrides):
            hem_flag = bool(
                lesion_type in {"hemangioma", "adenoma", "indeterminate_suspicious", "solid_unspecified", "metastatic_disease", "fnh"}
                and epigastric_pain and hypotension
            )

        is_cyst_branch = lesion_type in {"simple_cyst", "complex_cyst"}
        is_solid_branch = lesion_type in {"hemangioma", "fnh", "adenoma", "indeterminate_suspicious", "solid_unspecified", "metastatic_disease"}
        
        base_risk = any([history_cirrhosis, chronic_hep_b, chronic_hep_c, prior_malignancy, clinician_concern])
        if not any(ov.target_node == "Solid_Lesion_Risk_Assessment" for ov in st.session_state.lm_overrides):
            high_risk = base_risk

        named_benign = lesion_type in {"hemangioma", "fnh", "adenoma"}
        low_risk_branch = is_solid_branch and not hem_flag and (named_benign or not high_risk)
        high_risk_branch = is_solid_branch and not hem_flag and not named_benign and high_risk
        
        simple_cyst_branch = is_cyst_branch and not hem_flag and lesion_type == "simple_cyst"
        complex_cyst_branch = is_cyst_branch and not hem_flag and lesion_type == "complex_cyst"

        # ── SVG PATHWAY VISUAL ─────────────────────────────────────────────
        C_MAIN = "#16a34a"
        C_UNVISIT = "#475569"
        C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"
        C_EXIT = "#d97706"
        C_TEXT = "#ffffff"
        C_DIM = "#94a3b8"
        C_BG = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis: return C_UNVISIT
            if urgent: return C_URGENT
            if exit_: return C_EXIT
            return C_MAIN

        def dc(vis): return C_DIAMOND if vis else C_UNVISIT

        def mid(vis, urgent=False, exit_=False):
            if not vis: return "ma"
            if urgent: return "mr"
            if exit_: return "mo"
            return "mg"

        svg = []
        W, H = 700, 940
        svg.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" viewBox="0 0 {W} {H}" '
            f'style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">'
        )
        svg.append(
            "<defs>"
            '<marker id="ma" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>'
            '<marker id="mg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>'
            '<marker id="mr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>'
            '<marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>'
            "</defs>"
        )

        def svgt(x, y, text, fill, size=11, bold=False, anchor="middle"):
            w = "bold" if bold else "normal"
            svg.append(
                f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
                f'fill="{fill}" font-size="{size}" font-weight="{w}">{html.escape(str(text))}</text>'
            )

        def rect_node(x, y, w, h, color, line1, line2="", sub="", rx=8):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                f'fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(x+w/2, y+h/2-8, line1, tc, 11, True)
                svgt(x+w/2, y+h/2+7, line2, tc, 11, True)
            else:
                svgt(x+w/2, y+h/2+4, line1, tc, 11, True)
            if sub:
                svgt(x+w/2, y+h-8, sub, tc+"99", 9)

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

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label: svgt(x+6, (y1+y2)/2-3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" '
                f'fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label: svgt((x1+x2)/2, y1-5, label, stroke, 10, True)

        # SVG Layout Engine
        CX = 350; NW, NH = 200, 50; DW, DH = 180, 60; EW, EH = 130, 44
        LEXT = 20; REXT = W - 20 - EW

        Y = {
            "entry": 18,
            "d_hem": 100,
            "d_type": 195,
            "d_risk": 290,
            "c_complex": 385,
            "c_simple": 475,
            "l_mgt": 385,
            "h_mgt": 385,
            "l_detail": 475,
            "h_detail": 475,
        }

        # 1. Entry
        rect_node(CX-NW/2, Y["entry"], NW, NH, nc(has_lesion), "1. Liver Lesion Detected", sub="Incidental or Symptomatic")
        vline(CX, Y["entry"]+NH, Y["d_hem"], has_lesion and lesion_class)

        # 2. Hemorrhage
        diamond_node(CX, Y["d_hem"]+DH/2, DW, DH, dc(has_lesion and lesion_class), "Red Flag: Hemorrhage?", "")
        rect_node(REXT, Y["d_hem"]+(DH-EH)/2, EW, EH, nc(hem_flag, urgent=True), "EMERGENCY CARE", sub="ED / RAAPID", rx=7)
        elbow_line(CX+DW/2, Y["d_hem"]+DH/2, REXT, Y["d_hem"]+(DH-EH)/2+EH/2, hem_flag, urgent=True, label="Yes")

        v_proceed = has_lesion and lesion_class and not hem_flag
        vline(CX, Y["d_hem"]+DH, Y["d_type"], v_proceed, label="No")

        # 3. Type Fork
        diamond_node(CX, Y["d_type"]+DH/2, DW, DH, dc(v_proceed), "Lesion Category?", "")
        
        # Cysts
        cyst_cx = 80
        elbow_line(CX-DW/2, Y["d_type"]+DH/2, cyst_cx, Y["c_complex"], v_proceed and is_cyst_branch, exit_=True, label="Cysts")
        
        rect_node(cyst_cx-EW/2, Y["c_complex"], EW, NH, nc(complex_cyst_branch, exit_=True), "Complex Cyst", sub="MRI + HPB Refer", rx=7)
        vline(cyst_cx, Y["c_complex"]+NH, Y["c_simple"], simple_cyst_branch, exit_=True)
        rect_node(cyst_cx-EW/2, Y["c_simple"], EW, NH, nc(simple_cyst_branch, exit_=True), "Simple Cyst", sub="Benign - No F/U", rx=7)
        
        # Solids
        vline(CX, Y["d_type"]+DH, Y["d_risk"], v_proceed and is_solid_branch, label="Solid Lesion")

        # 4. Risk Diamond
        diamond_node(CX, Y["d_risk"]+DH/2, DW, DH, dc(v_proceed and is_solid_branch), "Risk Assessment?")
        
        # Low Risk Branch
        low_cx = 230
        elbow_line(CX-DW/2, Y["d_risk"]+DH/2, low_cx, Y["l_mgt"], low_risk_branch, exit_=True, label="Low Risk")
        rect_node(low_cx-EW/2, Y["l_mgt"], EW, NH, nc(low_risk_branch, exit_=True), "Low Risk Mgt")
        vline(low_cx, Y["l_mgt"]+NH, Y["l_detail"], low_risk_branch, exit_=True)
        
        lbl_sub = "Benign"
        if lesion_type == "hemangioma" and (radiology_followup or (lesion_size > 5 and possibly_symptomatic)): lbl_sub = "Refer HPB"
        elif lesion_type == "fnh" and not definitive_fnh: lbl_sub = "MRI Confirm"
        elif lesion_type == "adenoma": lbl_sub = "Refer Hepatology"
        elif lesion_type == "indeterminate_suspicious" or lesion_type == "solid_unspecified": lbl_sub = "MRI + Refer HPB"
        
        col_sub = C_EXIT if lbl_sub != "Benign" and low_risk_branch else C_MAIN
        rect_node(low_cx-EW/2, Y["l_detail"], EW, NH, col_sub if low_risk_branch else C_UNVISIT, lbl_sub)

        # High Risk Branch
        hi_cx = 470
        elbow_line(CX+DW/2, Y["d_risk"]+DH/2, hi_cx, Y["h_mgt"], high_risk_branch, urgent=True, label="High Risk")
        rect_node(hi_cx-EW/2, Y["h_mgt"], EW, NH, nc(high_risk_branch, urgent=True), "High Risk Mgt")
        vline(hi_cx, Y["h_mgt"]+NH, Y["h_detail"], high_risk_branch, urgent=True)
        
        h_sub = "Referrals Required"
        if prior_malignancy: h_sub = "Prior Oncology"
        elif history_cirrhosis or chronic_hep_b or chronic_hep_c: h_sub = "Hepatology"
        elif lesion_type == "metastatic_disease": h_sub = "Medical Oncology"
        
        rect_node(hi_cx-EW/2, Y["h_detail"], EW, NH, C_URGENT if high_risk_branch else C_UNVISIT, "Advanced Imaging", sub=h_sub)

        # Legend
        ly = H - 22; lx = 18
        for col, lbl in [(C_MAIN, "Visited"), (C_DIAMOND, "Decision"), (C_URGENT, "Urgent/High Risk"), (C_EXIT, "Exit/Branch"), (C_UNVISIT, "Not reached")]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 120
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>",
            height=960, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        risk_str = "Yes" if high_risk else "No"
        
        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Lesion Type:</b> {_pretty(str(lesion_type))} &nbsp;|&nbsp; <b>Size:</b> {lesion_size} cm</span><br>'
            f'<span><b>High-Risk for Malignancy:</b> {risk_str} &nbsp;|&nbsp; <b>Red Flag:</b> {"Yes" if hem_flag else "No"}</span><br>'
            f'<span><b>Modality:</b> {modality_sel} &nbsp;|&nbsp; <b>Detection:</b> {detection_sel}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Step grouping map ──────────────────────────────────────────────
        STEP_GROUPS = {
            "step1": {
                "label": "Step 1 — Initial Classification",
                "icon": "🔍",
                "cls": "routine",
                "codes": {"LESION_CLASSIFIED", "LESION_CHARACTERIZATION_UNCERTAIN", "RADIOLOGY_RECOMMENDS_FOLLOWUP", "NO_LIVER_LESION"},
            },
            "step2": {
                "label": "Step 2 — Hemorrhage Red Flag Check",
                "icon": "🚨",
                "cls": "urgent",
                "codes": {"NO_HEMORRHAGE_RED_FLAG", "EMERGENT_ED_OR_RAAPID"},
            },
            "step3": {
                "label": "Step 3 — Risk Assessment & Labs",
                "icon": "🩸",
                "cls": "info",
                "codes": {"SOLID_LESION_RISK_ASSESSED", "WEIGHT_LOSS_FLAG", "PERSISTENT_PAIN_FLAG", "FEVER_FLAG", "EARLY_SATIETY_FLAG", "ALT_RECORDED", "AST_RECORDED", "ALP_RECORDED", "BILIRUBIN_RECORDED", "AFP_RECORDED", "ORDER_HIGH_RISK_LIVER_LABS"},
            },
            "step4": {
                "label": "Step 4 — Diagnostic Imaging",
                "icon": "📸",
                "cls": "routine",
                "codes": {"ORDER_MRI_LIVER_COMPLEX_CYST", "ORDER_MRI_OR_TRIPHASIC_CT_HIGH_RISK", "ORDER_MRI_OR_CHEST_ABDO_PELVIS_CT_PRIOR_MALIGNANCY", "ORDER_MRI_LIVER_CLINICIAN_CONCERN", "ORDER_MRI_CONFIRM_FNH", "ORDER_MRI_LIVER_LOW_RISK_SOLID", "ADVANCED_IMAGING_ALREADY_DONE", "REPEAT_IMAGING_PLANNED_RECORDED"},
            },
            "step5": {
                "label": "Step 5 — Specialty Referrals & Management",
                "icon": "🏥",
                "cls": "warning",
                "codes": {"REFER_HPB_COMPLEX_CYST", "REFER_HPB_HIGH_RISK", "REFER_HEPATOLOGY_CIRRHOSIS_OR_HEPATITIS", "REFER_PRIOR_ONCOLOGY_TEAM", "CONTACT_ONCOLOGY_OR_HPB_METASTATIC_DISEASE", "REFER_HPB_CLINICIAN_CONCERN", "REFER_HPB_HEMANGIOMA_EXCEPTION", "REFER_HEPATOLOGY_ADENOMA", "TIMELY_REFERRAL_ADENOMA_PREGNANCY", "REFER_HPB_LOW_RISK_INDETERMINATE", "ADVICE_SERVICE_NOTE", "BIOPSY_CONSIDERED", "HEPATOLOGY_REFERRAL_ALREADY_MADE", "SURGICAL_REFERRAL_ALREADY_MADE", "URGENT_REFERRAL_FLAG"},
            },
            "step6": {
                "label": "Step 6 — Benign & Medical Home",
                "icon": "🏠",
                "cls": "routine",
                "codes": {"SIMPLE_CYST_BENIGN", "CYST_SIZE_RECORDED", "NO_FOLLOWUP_SIMPLE_CYST", "CONSIDER_REPEAT_IMAGING_SIMPLE_CYST", "COMPLEX_CYST_FEATURES_DOCUMENTED", "HEMANGIOMA_BENIGN", "LESION_SIZE_RECORDED", "NO_FOLLOWUP_HEMANGIOMA", "FNH_CONFIRMED", "FOLLOWUP_FNH_RADIOLOGY_RECOMMENDED", "NO_FOLLOWUP_FNH", "OCP_USE_RECORDED", "ANABOLIC_STEROID_USE_RECORDED", "ADENOMA_CONFIRMED"},
            },
        }

        code_to_group = {}
        for gkey, gdata in STEP_GROUPS.items():
            for c in gdata["codes"]:
                code_to_group[c] = gkey

        grouped: dict = {k: [] for k in STEP_GROUPS}
        stops_and_requests = []
        override_candidates = []

        for output in outputs:
            if isinstance(output, (Stop, DataRequest)):
                stops_and_requests.append(output)
            elif isinstance(output, Action):
                gkey = code_to_group.get(output.code)
                if gkey:
                    grouped[gkey].append(output)

        for output in outputs:
            if isinstance(output, Stop):
                for a in output.actions:
                    if a.override_options:
                        override_candidates.append(a)
            elif getattr(output, "override_options", None):
                 override_candidates.append(output)

        def render_group(gkey: str, actions: list) -> None:
            if not actions:
                return
            g = STEP_GROUPS[gkey]
            cls = g["cls"]
            icon = g["icon"]
            label = g["label"]

            border_colors = {"routine": "#22c55e", "info": "#3b82f6", "urgent": "#ef4444", "warning": "#f59e0b"}
            bg_colors = {"routine": "#052e16", "info": "#0c1a2e", "urgent": "#3b0a0a", "warning": "#2d1a00"}
            border = border_colors.get(cls, "#22c55e")
            bg = bg_colors.get(cls, "#052e16")

            for a in actions:
                if a.override_options and a not in override_candidates:
                    override_candidates.append(a)

            bullets = "".join(
                f'<li style="margin-bottom:5px">{html.escape(a.label)}'
                + (
                    '<span style="font-size:10px;color:#a5b4fc;margin-left:8px">'
                    '⚙ override available</span>'
                    if a.override_options else ""
                )
                + "</li>"
                for a in actions
            )

            st.markdown(
                f'<div style="background:{bg};border-left:5px solid {border};'
                f'border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                f'<p style="margin:0 0 10px 0;font-size:13px;font-weight:700;'
                f'color:#e2e8f0;letter-spacing:0.3px">'
                f'{icon} {html.escape(label)}</p>'
                f'<ul style="margin:0;padding-left:18px;color:#cbd5e1;'
                f'font-size:13.5px;line-height:1.7">{bullets}</ul>'
                f'</div>',
                unsafe_allow_html=True,
            )

        def render_stop_request(output) -> None:
            if isinstance(output, DataRequest):
                missing_str = ", ".join(_pretty(f) for f in output.missing_fields)
                msg_html = html.escape(output.message)
                st.markdown(
                    '<div style="background:#2d1a00;border-left:5px solid #f59e0b;'
                    'border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                    '<p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#fde68a">'
                    '⏳ Data Required to Proceed</p>'
                    f'<p style="margin:0 0 6px;font-size:13.5px;color:#fde68a">{msg_html}</p>'
                    f'<p style="margin:0;font-size:12px;color:#94a3b8">'
                    f'Missing: <code style="color:#fbbf24">{missing_str}</code></p>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            elif isinstance(output, Stop):
                is_emergent = output.urgency == "urgent"
                bg, border, icon = ("#3b0a0a", "#ef4444", "🚨") if is_emergent else ("#1e1e2e", "#6366f1", "ℹ️")
                tcol = "#fecaca" if is_emergent else "#c7d2fe"
                title = output.reason

                action_bullets = "".join(
                    f'<li style="margin-bottom:5px">{html.escape(a.label)}'
                    + (
                        '<span style="font-size:10px;color:#a5b4fc;margin-left:8px">'
                        '⚙ override available</span>'
                        if getattr(a, "override_options", None) else ""
                    )
                    + "</li>"
                    for a in output.actions
                )
                action_block = (
                    f'<ul style="margin:10px 0 0;padding-left:18px;color:#cbd5e1;'
                    f'font-size:13.5px;line-height:1.7">{action_bullets}</ul>'
                    if action_bullets else ""
                )
                st.markdown(
                    f'<div style="background:{bg};border-left:5px solid {border};'
                    f'border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                    f'<p style="margin:0 0 {"6px" if action_block else "0"};font-size:13px;'
                    f'font-weight:700;color:{tcol}">{icon} {html.escape(title)}</p>'
                    f'{action_block}</div>',
                    unsafe_allow_html=True,
                )

        blocking = [o for o in stops_and_requests if isinstance(o, DataRequest)]
        for o in blocking:
            render_stop_request(o)

        for gkey in STEP_GROUPS:
            render_group(gkey, grouped[gkey])

        terminal = [o for o in stops_and_requests if isinstance(o, Stop)]
        for o in terminal:
            render_stop_request(o)

        # ── Clinician Notes ────────────────────────────────────────────────
        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.lm_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.lm_notes,
            height=180,
        )

        # ── Save / Download ────────────────────────────────────────────────
        def _serialize_output(o):
            if isinstance(o, Action):
                return {"type": "action", "code": o.code, "label": o.label, "urgency": o.urgency}
            if isinstance(o, Stop):
                return {"type": "stop", "reason": o.reason, "urgency": getattr(o, "urgency", None)}
            if isinstance(o, DataRequest):
                return {"type": "data_request", "message": o.message, "missing_fields": o.missing_fields}
            return {"type": "other", "repr": repr(o)}

        full_output = {
            "patient_context": patient_data,
            "clinical_recommendations": {
                "engine_outputs": [_serialize_output(o) for o in outputs],
                "overrides": [
                    {
                        "node": o.target_node,
                        "field": o.field,
                        "new_value": o.new_value,
                        "reason": o.reason,
                        "created_at": o.created_at.isoformat(),
                    }
                    for o in st.session_state.lm_overrides
                ],
                "clinician_notes": st.session_state.lm_notes,
            },
        }

        if st.button("💾 Save this output", key="lm_save_output"):
            st.session_state.lm_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "lm_saved_output" in st.session_state:
            md_text = build_liver_mass_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.lm_overrides,
                notes=st.session_state.lm_notes,
            )
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="liver_mass_summary.md",
                mime="text/markdown",
                key="lm_download_md",
            )

        # ── Override Panel ─────────────────────────────────────────────────
        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                st.caption(
                    "Override engine decisions where clinical judgement differs. "
                    "A documented reason is required for each override."
                )

                for a in override_candidates:
                    opt = a.override_options
                    raw_node = opt["node"]
                    raw_field = opt["field"]
                    node = _pretty(raw_node)
                    field = _pretty(raw_field)
                    allowed = opt.get("allowed", [True, False])

                    with st.expander(f"⚙️ Override: **{node}** → `{field}`"):
                        preview = a.label[:120] + ("…" if len(a.label) > 120 else "")
                        st.markdown(
                            f'<div class="override-card">Engine decision based on: <b>{html.escape(preview)}</b></div>',
                            unsafe_allow_html=True,
                        )
                        existing = next(
                            (o for o in st.session_state.lm_overrides
                             if o.target_node == raw_node and o.field == raw_field),
                            None,
                        )
                        current_val = existing.new_value if existing else None
                        new_val = st.radio(
                            f"Set `{field}` to:",
                            options=allowed,
                            index=allowed.index(current_val) if current_val in allowed else 0,
                            key=f"ov_val_{raw_node}_{raw_field}",
                            horizontal=True,
                        )
                        reason = st.text_input(
                            "Reason (required):",
                            value=existing.reason if existing else "",
                            key=f"ov_reason_{raw_node}_{raw_field}",
                            placeholder="Document clinical rationale...",
                        )
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Apply Override", key=f"ov_apply_{raw_node}_{raw_field}"):
                                if not reason.strip():
                                    st.error("A reason is required to apply an override.")
                                else:
                                    st.session_state.lm_overrides = [
                                        o for o in st.session_state.lm_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.lm_overrides.append(
                                        Override(
                                            target_node=raw_node,
                                            field=raw_field,
                                            old_value=None,
                                            new_value=new_val,
                                            reason=reason.strip(),
                                        )
                                    )
                                    st.success("Override applied. Click **▶ Run Pathway** to re-evaluate.")
                        with col2:
                            if existing and st.button("🗑 Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.lm_overrides = [
                                    o for o in st.session_state.lm_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.lm_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.lm_overrides:
                        st.markdown(
                            '<div class="override-card">'
                            f'🛠 <b>{html.escape(_pretty(o.target_node))}</b> → <code>{html.escape(_pretty(o.field))}</code>'
                            f' set to <b>{html.escape(str(o.new_value))}</b><br>'
                            f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                            f'<span style="color:#64748b;font-size:11px">'
                            f'Applied: {o.created_at.strftime("%H:%M:%S")}</span>'
                            "</div>",
                            unsafe_allow_html=True,
                        )

        # ── Decision Audit Log ─────────────────────────────────────────────
        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try:
                    ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except Exception:
                    ts = "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if log.used_inputs:
                    st.caption(
                        "  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None)
                    )
