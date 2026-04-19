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
    lines.append("# Liver Mass (Solid Lesion) Pathway — Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    lines.append(
        f"- **Age / Sex:** {patient_data.get('age', 'N/A')} / "
        f"{str(patient_data.get('sex', '')).capitalize()}"
    )
    lines.append(f"- **Lesion Type:** {_safe_text(patient_data.get('lesion_type')) or 'Not specified'}")
    lines.append(f"- **Imaging Modality:** {_safe_text(patient_data.get('imaging_modality')) or 'N/A'}")
    lines.append(f"- **Lesion Size:** {patient_data.get('lesion_size_cm', 'N/A')} cm")
    lines.append(
        f"- **High Risk Factors:** Cirrhosis ({patient_data.get('history_cirrhosis')}), "
        f"Hep B ({patient_data.get('chronic_hepatitis_b')}), "
        f"Hep C ({patient_data.get('chronic_hepatitis_c')}), "
        f"Prior Malignancy ({patient_data.get('prior_malignancy_any_location')})"
    )
    lines.append(
        f"- **Red Flag Hemorrhage:** "
        f"RUQ Pain ({patient_data.get('episodic_epigastric_or_ruq_pain')}), "
        f"Hypotension ({patient_data.get('hypotension')})"
    )
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
                        if isinstance(v, list) and v:
                            for item in v:
                                lines.append(f"  - {_safe_text(k).replace('_',' ').title()}: {_safe_text(item)}")
                        elif v not in (None, False, "", []):
                            lines.append(f"  - {_safe_text(k).replace('_',' ').title()}: {_safe_text(v)}")
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
                f"- **{_safe_text(ov.target_node)}.{_safe_text(ov.field)}** → "
                f"`{_safe_text(ov.new_value)}` "
                f"(Reason: {_safe_text(ov.reason)})"
            )
    else:
        lines.append("- No active overrides.")
    lines.append("")
    lines.append("## Clinician Notes")
    lines.append(notes.strip() if notes and notes.strip() else "No clinician notes entered.")
    lines.append("")
    return "\n".join(lines)


# ── GLOBAL CSS ─────────────────────────────────────────────────────────────────
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


# ── SESSION STATE ──────────────────────────────────────────────────────────────
if "lm_overrides" not in st.session_state:
    st.session_state.lm_overrides = []
if "lm_has_run" not in st.session_state:
    st.session_state.lm_has_run = False
if "lm_notes" not in st.session_state:
    st.session_state.lm_notes = ""


left, right = st.columns([1, 1.5])


# ═══════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — INPUTS
# ═══════════════════════════════════════════════════════════════════════════════
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
    st.caption("High risk = any of the following apply:")
    history_cirrhosis = st.checkbox("History of cirrhosis")
    chronic_hep_b = st.checkbox("Chronic Hepatitis B infection")
    chronic_hep_c = st.checkbox("Chronic Hepatitis C infection")
    prior_malignancy = st.checkbox("Prior malignancy (any location)")
    clinician_concern = st.checkbox("Clinician concern for malignancy (other reason)")

    # ── Red Flag Symptoms ─────────────────────────────────────────────────────
    st.markdown("**🚨 Red Flag — Possible Hemorrhage**")
    st.caption("Red flag = solid mass + episodic RUQ/epigastric pain + hypotension")
    epigastric_pain = st.checkbox("Episodic epigastric or RUQ pain")
    hypotension = st.checkbox("Hypotension")

    # ── Other Symptoms ────────────────────────────────────────────────────────
    st.markdown("**Associated Symptoms**")
    weight_loss = st.checkbox("Unintentional weight loss")
    persistent_pain = st.checkbox("Persistent abdominal pain")
    fever = st.checkbox("Fever")
    early_satiety = st.checkbox("Early satiety")

    # ── Cyst-Specific ─────────────────────────────────────────────────────────
    is_cyst = lesion_type in {"simple_cyst", "complex_cyst"}
    if is_cyst:
        st.markdown("**Cyst Details**")
        cyst_features = st.checkbox("Complex cyst features present (wall thickening, septations, nodules, enhancement)")
        cyst_symptoms = st.checkbox("Symptoms attributable to cyst")
        abnormal_enzymes = st.checkbox("Elevated liver enzymes possibly related to cyst")
    else:
        cyst_features = False
        cyst_symptoms = False
        abnormal_enzymes = False

    # ── Lesion-Specific Details ───────────────────────────────────────────────
    if lesion_type == "hemangioma":
        st.markdown("**Hemangioma Details**")
        possibly_symptomatic = st.checkbox("Possibly symptomatic (e.g. pain)")
    else:
        possibly_symptomatic = False

    if lesion_type == "fnh":
        st.markdown("**FNH Details**")
        definitive_fnh = st.checkbox("Definitively confirmed as FNH on imaging")
        fnh_uncertain = st.checkbox("FNH characterization uncertain — needs MRI")
    else:
        definitive_fnh = False
        fnh_uncertain = False

    if lesion_type == "adenoma":
        st.markdown("**Adenoma Details**")
        pregnant = st.checkbox("Patient is pregnant")
        ocp_use = st.checkbox("Oral contraceptive use")
        anabolic_use = st.checkbox("Anabolic steroid use")
        adenoma_confirmed = st.checkbox("Adenoma diagnosis confirmed on imaging")
    else:
        pregnant = False
        ocp_use = False
        anabolic_use = False
        adenoma_confirmed = False

    # ── Workup Status ─────────────────────────────────────────────────────────
    with st.expander("Workup status (optional — enriches guidance outputs)"):
        advanced_imaging_done = st.checkbox("Advanced imaging (MRI/triphasic CT) already completed")
        biopsy_considered = st.checkbox("Biopsy has been considered / documented")
        referred_hepatology = st.checkbox("Hepatology referral already made")
        referred_surgery = st.checkbox("Hepatobiliary (HPB) surgery referral already made")
        urgent_referral = st.checkbox("Urgent referral requirement documented")
        metastatic_pattern = st.checkbox("Metastatic pattern present on imaging")
        repeat_imaging_planned = st.checkbox("Repeat imaging plan documented")

    # ── Lab Values ────────────────────────────────────────────────────────────
    st.markdown("**Lab Values (optional — for documentation)**")
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


# ═══════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL
# ═══════════════════════════════════════════════════════════════════════════════
with right:
    if not st.session_state.lm_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        # ── Build patient_data dict ────────────────────────────────────────
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
            # cyst
            "cyst_size_cm": lesion_size if lesion_size > 0 else None,
            "cyst_complex_features_present": cyst_features or None,
            "symptoms_attributable_to_cyst": cyst_symptoms or None,
            "abnormal_liver_enzymes": abnormal_enzymes or None,
            # hemangioma
            "possibly_symptomatic": possibly_symptomatic or None,
            # fnh
            "definitive_fnh": definitive_fnh or None,
            "fnh_uncertain": fnh_uncertain or None,
            # adenoma
            "pregnant": pregnant or None,
            "oral_contraceptive_use": ocp_use or None,
            "anabolic_steroid_use": anabolic_use or None,
            "adenoma_confirmed": adenoma_confirmed or None,
            # workup
            "advanced_imaging_done": advanced_imaging_done or None,
            "biopsy_considered": biopsy_considered or None,
            "referred_to_hepatology": referred_hepatology or None,
            "referred_to_surgery": referred_surgery or None,
            "urgent_referral_required": urgent_referral or None,
            "metastatic_pattern_present": metastatic_pattern or None,
            "repeat_imaging_planned": repeat_imaging_planned or None,
            # labs
            "alt": alt_val if alt_val > 0 else None,
            "ast": ast_val if ast_val > 0 else None,
            "alp": alp_val if alp_val > 0 else None,
            "bilirubin": bilirubin_val if bilirubin_val > 0 else None,
            "afp": afp_val if afp_val > 0 else None,
        }

        outputs, logs, applied_overrides = run_liver_mass_pathway(
            patient_data, overrides=st.session_state.lm_overrides
        )

        # ── Compute derived flags for SVG ──────────────────────────────────
        has_lesion = bool(liver_lesion_detected)
        lesion_classified = has_lesion and lesion_type is not None

        hem_flag = bool(
            lesion_type in {"hemangioma", "adenoma", "indeterminate_suspicious", "solid_unspecified", "metastatic_disease", "fnh"}
            and epigastric_pain
            and hypotension
        )

        is_cyst_branch = lesion_type in {"simple_cyst", "complex_cyst"}
        is_solid_branch = lesion_type in {"hemangioma", "fnh", "adenoma", "indeterminate_suspicious", "solid_unspecified", "metastatic_disease"}

        risk_flag = any([history_cirrhosis, chronic_hep_b, chronic_hep_c, prior_malignancy, clinician_concern])
        # Named benign lesions go to low-risk branch regardless
        named_benign = lesion_type in {"hemangioma", "fnh", "adenoma"}
        low_risk_branch = is_solid_branch and not hem_flag and (named_benign or not risk_flag)
        high_risk_branch = is_solid_branch and not hem_flag and not named_benign and risk_flag

        simple_cyst_branch = is_cyst_branch and not hem_flag and lesion_type == "simple_cyst"
        complex_cyst_branch = is_cyst_branch and not hem_flag and lesion_type == "complex_cyst"

        # ── ANIMATED SVG PATHWAY ──────────────────────────────────────────
        W, H = 700, 940
        C_BG = "#0f1827"
        C_MAIN = "#1e6ab0"
        C_DIAMOND = "#0d9488"
        C_URGENT = "#dc2626"
        C_EXIT = "#d97706"
        C_UNVISIT = "#334155"
        C_GREEN = "#16a34a"

        svg = [
            f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
            f'style="font-family:Inter,system-ui,sans-serif;background:{C_BG};'
            f'border-radius:14px;max-width:100%">',
        ]

        # Arrow markers
        for mid_id, col in [("mg", C_GREEN), ("mr", C_URGENT), ("mo", C_EXIT), ("mb", C_MAIN), ("md", "#64748b")]:
            svg.append(
                f'<defs><marker id="{mid_id}" markerWidth="9" markerHeight="7" '
                f'refX="9" refY="3.5" orient="auto">'
                f'<polygon points="0 0, 9 3.5, 0 7" fill="{col}"/>'
                f'</marker></defs>'
            )

        def svgt(x, y, text, color="#e2e8f0", size=10, bold=False, anchor="middle"):
            w = "700" if bold else "400"
            svg.append(
                f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
                f'font-size="{size}" font-weight="{w}" fill="{color}">{html.escape(str(text))}</text>'
            )

        def nc(visited, urgent=False, exit_=False):
            if not visited:
                return C_UNVISIT
            if urgent:
                return C_URGENT
            if exit_:
                return C_EXIT
            return C_MAIN

        def dc(visited):
            return C_DIAMOND if visited else C_UNVISIT

        def mid_arrow(vis, urgent=False, exit_=False):
            if not vis:
                return "md"
            if urgent:
                return "mr"
            if exit_:
                return "mo"
            return "mg"

        def rect_node(x, y, w, h, color, line1, line2="", rx=10):
            tc = "#ffffff" if color != C_UNVISIT else "#64748b"
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                f'fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(x + w / 2, y + h / 2 - 6, line1, tc, 10, True)
                svgt(x + w / 2, y + h / 2 + 8, line2, tc, 9)
            else:
                svgt(x + w / 2, y + h / 2 + 4, line1, tc, 10, True)

        def exit_node(x, y, w, h, color, line1, line2=""):
            tc = "#ffffff" if color != C_UNVISIT else "#64748b"
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" '
                f'fill="{color}" opacity="0.88" stroke="#ffffff22" stroke-width="1"/>'
            )
            if line2:
                svgt(x + w / 2, y + h / 2 - 6, line1, tc, 9, True)
                svgt(x + w / 2, y + h / 2 + 7, line2, tc, 8)
            else:
                svgt(x + w / 2, y + h / 2 + 4, line1, tc, 9, True)

        def diamond_node(cx, cy, w, h, color, line1, line2=""):
            hw, hh = w / 2, h / 2
            pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
            tc = "#ffffff" if color != C_UNVISIT else "#64748b"
            svg.append(f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(cx, cy - 6, line1, tc, 9, True)
                svgt(cx, cy + 8, line2, tc, 8)
            else:
                svgt(cx, cy + 4, line1, tc, 9, True)

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label=""):
            m = mid_arrow(vis, urgent, exit_)
            stroke = {
                "mg": C_GREEN, "mr": C_URGENT, "mo": C_EXIT, "mb": C_MAIN
            }.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt(x + 6, (y1 + y2) / 2 - 3, label, stroke, 9, True, "start")

        def hline(x1, x2, y, vis, urgent=False, exit_=False, label=""):
            m = mid_arrow(vis, urgent, exit_)
            stroke = {
                "mg": C_GREEN, "mr": C_URGENT, "mo": C_EXIT, "mb": C_MAIN
            }.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" '
                f'stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt((x1 + x2) / 2, y - 5, label, stroke, 9, True)

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid_arrow(vis, urgent, exit_)
            stroke = {
                "mg": C_GREEN, "mr": C_URGENT, "mo": C_EXIT, "mb": C_MAIN
            }.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" '
                f'fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt((x1 + x2) / 2, y1 - 5, label, stroke, 9, True)

        # ── Layout ─────────────────────────────────────────────────────────
        CX = 350
        NW, NH = 200, 48
        DW, DH = 190, 58
        EW, EH = 130, 42

        # Column positions
        LEXT = 10        # left exit column
        REXT = W - 10 - EW  # right exit column

        # Cyst branch positions (far left)
        CL = 60          # cyst left column center
        CYST_W = 120

        # Solid low-risk branch (left-center)
        LR_X = 100
        LR_W = 130

        # Solid high-risk branch (right)
        HR_X = W - 150
        HR_W = 130

        Y = {
            "entry":    14,
            "d_hem":   100,
            "d_type":  195,
            "cyst_br": 295,   # cyst type fork
            "simple":  380,
            "complex": 380,
            "d_risk":  295,   # solid risk diamond
            "low_mgt": 385,
            "high_mgt": 385,
            "benign_detail": 475,
            "high_detail": 475,
            "refer_out": 565,
        }

        # ── 1. Entry ───────────────────────────────────────────────────────
        rect_node(CX - NW / 2, Y["entry"], NW, NH, nc(True),
                  "Liver Lesion Detected", "Incidental or Symptomatic")
        vline(CX, Y["entry"] + NH, Y["d_hem"], has_lesion)

        # ── 2. Red Flag Hemorrhage ────────────────────────────────────────
        diamond_node(CX, Y["d_hem"] + DH / 2, DW, DH,
                     dc(lesion_classified), "Red Flag?", "Hemorrhage?")
        svgt(CX, Y["d_hem"] - 4, "Solid mass + RUQ pain + hypotension", "#94a3b8", 8)

        # Emergency exit (right)
        exit_node(REXT, Y["d_hem"] + (DH - EH) / 2, EW, EH,
                  nc(hem_flag, urgent=True), "🚨 EMERGENT", "ED / RAAPID")
        elbow_line(CX + DW / 2, Y["d_hem"] + DH / 2,
                   REXT, Y["d_hem"] + (DH - EH) / 2 + EH / 2,
                   hem_flag, urgent=True, label="Yes")

        # Continue down
        v_proceed = lesion_classified and not hem_flag
        vline(CX, Y["d_hem"] + DH, Y["d_type"], v_proceed, label="No")

        # ── 3. Cyst vs Solid diamond ──────────────────────────────────────
        diamond_node(CX, Y["d_type"] + DH / 2, DW, DH,
                     dc(v_proceed), "Lesion Category", "Cyst vs Solid?")

        # ── CYST BRANCH (left) ─────────────────────────────────────────────
        v_cyst = v_proceed and is_cyst_branch
        # Elbow left to cyst area
        cyst_cx = 120
        elbow_line(CX - DW / 2, Y["d_type"] + DH / 2,
                   cyst_cx, Y["cyst_br"], v_cyst, exit_=True, label="Cyst")

        # Cyst type fork
        v_simple = v_cyst and simple_cyst_branch
        v_complex = v_cyst and complex_cyst_branch

        # Simple cyst (left)
        simple_x = 18
        simple_cx = simple_x + CYST_W / 2
        elbow_line(cyst_cx, Y["cyst_br"],
                   simple_cx, Y["simple"], v_simple, exit_=True, label="Simple")
        exit_node(simple_x, Y["simple"], CYST_W, 50,
                  nc(v_simple, exit_=True), "Simple Cyst", "Benign — No F/U")

        if v_simple:
            svgt(simple_cx, Y["simple"] + 68, "✔ No follow-up", C_GREEN, 8, True)

        # Complex cyst (below fork)
        complex_x = 18
        complex_cy = Y["complex"] + 95
        exit_node(complex_x, complex_cy, CYST_W, 50,
                  nc(v_complex, exit_=True), "Complex Cyst", "MRI + HPB Surgery")
        elbow_line(cyst_cx, Y["cyst_br"],
                   simple_cx, complex_cy + 25, v_complex, exit_=True, label="Complex")

        if v_complex:
            svgt(simple_cx, complex_cy + 68, "MRI liver / CT", C_EXIT, 8, True)

        # ── SOLID BRANCH (right/down) ──────────────────────────────────────
        v_solid = v_proceed and is_solid_branch
        vline(CX, Y["d_type"] + DH, Y["d_risk"], v_solid, label="Solid")

        # ── 4. Risk Assessment diamond ─────────────────────────────────────
        diamond_node(CX, Y["d_risk"] + DH / 2, DW, DH,
                     dc(v_solid), "Risk Assessment", "High or Low Risk?")

        # ── LOW RISK BRANCH (left) ─────────────────────────────────────────
        v_low = v_solid and low_risk_branch
        low_cx = 170
        low_w = 145
        low_x = low_cx - low_w / 2
        elbow_line(CX - DW / 2, Y["d_risk"] + DH / 2,
                   low_cx, Y["low_mgt"], v_low, exit_=True, label="Low Risk")

        rect_node(low_x, Y["low_mgt"], low_w, NH,
                  nc(v_low, exit_=True), "Low-Risk Mgt", "Hemangioma/FNH/Adenoma")

        # Lesion-specific sub-outcomes
        if v_low and lesion_type == "hemangioma":
            hem_ref = radiology_followup or (lesion_size > 5 and possibly_symptomatic)
            sub_lbl = "Refer HPB (exception)" if hem_ref else "Benign — No follow-up"
            sub_col = C_EXIT if hem_ref else C_GREEN
            rect_node(low_x, Y["benign_detail"], low_w, 38,
                      sub_col, sub_lbl)
            vline(low_cx, Y["low_mgt"] + NH, Y["benign_detail"], v_low, exit_=True)

        elif v_low and lesion_type == "fnh":
            if definitive_fnh and not fnh_uncertain:
                sub_lbl = "Definitive FNH — Benign"
                sub_col = C_GREEN
            else:
                sub_lbl = "Order MRI to confirm FNH"
                sub_col = C_EXIT
            rect_node(low_x, Y["benign_detail"], low_w, 38,
                      sub_col, sub_lbl)
            vline(low_cx, Y["low_mgt"] + NH, Y["benign_detail"], v_low, exit_=True)

        elif v_low and lesion_type == "adenoma":
            sub_lbl = "⚡ Timely Referral" if pregnant else "Refer Hepatology"
            sub_col = C_URGENT if pregnant else C_EXIT
            rect_node(low_x, Y["benign_detail"], low_w, 38,
                      sub_col, sub_lbl)
            vline(low_cx, Y["low_mgt"] + NH, Y["benign_detail"], v_low, exit_=True)
            if v_low:
                svgt(low_cx, Y["benign_detail"] + 55,
                     "(Adenoma during pregnancy → urgent)", "#fca5a5", 7, False)

        elif v_low:
            # Indeterminate solid low risk
            rect_node(low_x, Y["benign_detail"], low_w, 38,
                      nc(v_low, exit_=True), "MRI + Refer HPB")
            vline(low_cx, Y["low_mgt"] + NH, Y["benign_detail"], v_low, exit_=True)

        # ── HIGH RISK BRANCH (right) ───────────────────────────────────────
        v_high = v_solid and high_risk_branch
        high_cx = 535
        high_w = 145
        high_x = high_cx - high_w / 2
        elbow_line(CX + DW / 2, Y["d_risk"] + DH / 2,
                   high_cx, Y["high_mgt"], v_high, urgent=True, label="High Risk")

        rect_node(high_x, Y["high_mgt"], high_w, NH,
                  nc(v_high, urgent=True), "High-Risk Mgt", "Investigations + Referral")

        # Labs box
        if v_high:
            rect_node(high_x, Y["high_detail"], high_w, 38,
                      C_MAIN, "CBC, LFTs, AFP, HBsAg,", "HCV Ab — Order")
            vline(high_cx, Y["high_mgt"] + NH, Y["high_detail"], v_high)

            # Sub-outcomes based on specific risk factors
            ref_y = Y["refer_out"]
            if prior_malignancy and (history_cirrhosis or chronic_hep_b or chronic_hep_c):
                rect_node(high_x, ref_y, high_w, 48,
                          C_URGENT, "HPB + Hepatology +", "Prior Oncology Team")
            elif prior_malignancy:
                rect_node(high_x, ref_y, high_w, 48,
                          C_URGENT, "MRI/CT + HPB +", "Prior Oncology Team")
            elif history_cirrhosis or chronic_hep_b or chronic_hep_c:
                rect_node(high_x, ref_y, high_w, 48,
                          C_URGENT, "MRI Liver + HPB +", "Hepatology Referral")
            elif clinician_concern:
                rect_node(high_x, ref_y, high_w, 48,
                          C_URGENT, "MRI Liver + HPB", "(Clinician Concern)")
            vline(high_cx, Y["high_detail"] + 38, ref_y, v_high, urgent=True)

        # New metastatic disease note
        if lesion_type == "metastatic_disease" and v_high:
            svgt(high_cx, Y["refer_out"] + 80,
                 "Contact Oncology / HPB", C_URGENT, 8, True)
            svgt(high_cx, Y["refer_out"] + 93,
                 "Consider early palliative approach", "#94a3b8", 7)

        # ── Legend ─────────────────────────────────────────────────────────
        ly = H - 22
        lx = 14
        for col, lbl in [
            (C_MAIN, "Visited"),
            (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent/High Risk"),
            (C_EXIT, "Exit/Branch"),
            (C_UNVISIT, "Not reached"),
        ]:
            svg.append(
                f'<rect x="{lx}" y="{ly - 11}" width="12" height="12" rx="2" fill="{col}"/>'
            )
            svgt(lx + 16, ly, lbl, "#94a3b8", 9, anchor="start")
            lx += 128
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg)
            + "</div>",
            height=980,
            scrolling=True,
        )

        # ── Context card ───────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("Clinical Recommendations")

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)

        risk_parts = []
        if history_cirrhosis:
            risk_parts.append("Cirrhosis")
        if chronic_hep_b:
            risk_parts.append("Hep B")
        if chronic_hep_c:
            risk_parts.append("Hep C")
        if prior_malignancy:
            risk_parts.append("Prior Malignancy")
        if clinician_concern:
            risk_parts.append("Clinician Concern")
        risk_str = ", ".join(risk_parts) if risk_parts else "None identified"

        lesion_disp = lesion_type_sel if lesion_type else "Not selected"
        size_disp = f"{lesion_size} cm" if lesion_size > 0 else "Not specified"

        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Lesion Type:</b> {lesion_disp} &nbsp;|&nbsp; <b>Size:</b> {size_disp}</span><br>'
            f'<span><b>Modality:</b> {modality_sel} &nbsp;|&nbsp; <b>Detection:</b> {detection_sel}</span><br>'
            f'<span><b>High-Risk Factors:</b> {html.escape(risk_str)}</span><br>'
            f'<span><b>Red Flag (Hemorrhage):</b> {"⚠️ YES — EMERGENT" if hem_flag else "No"}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Step groups for rendering ──────────────────────────────────────
        ENTRY_CODES = {
            "LESION_CLASSIFIED", "LESION_CHARACTERIZATION_UNCERTAIN",
            "RADIOLOGY_RECOMMENDS_FOLLOWUP", "NO_LIVER_LESION",
        }
        HEMORRHAGE_CODES = {
            "NO_HEMORRHAGE_RED_FLAG", "EMERGENT_ED_OR_RAAPID",
        }
        CYST_CODES = {
            "SIMPLE_CYST_BENIGN", "CYST_SIZE_RECORDED", "NO_FOLLOWUP_SIMPLE_CYST",
            "CONSIDER_REPEAT_IMAGING_SIMPLE_CYST", "ORDER_MRI_LIVER_COMPLEX_CYST",
            "REFER_HPB_COMPLEX_CYST", "COMPLEX_CYST_FEATURES_DOCUMENTED",
        }
        RISK_CODES = {
            "SOLID_LESION_RISK_ASSESSED", "WEIGHT_LOSS_FLAG", "PERSISTENT_PAIN_FLAG",
            "FEVER_FLAG", "EARLY_SATIETY_FLAG", "ALT_RECORDED", "AST_RECORDED",
            "ALP_RECORDED", "BILIRUBIN_RECORDED", "AFP_RECORDED",
        }
        HIGH_RISK_CODES = {
            "ORDER_HIGH_RISK_LIVER_LABS", "ADVICE_SERVICE_NOTE",
            "ORDER_MRI_OR_TRIPHASIC_CT_HIGH_RISK", "REFER_HPB_HIGH_RISK",
            "REFER_HEPATOLOGY_CIRRHOSIS_OR_HEPATITIS",
            "ORDER_MRI_OR_CHEST_ABDO_PELVIS_CT_PRIOR_MALIGNANCY",
            "REFER_PRIOR_ONCOLOGY_TEAM", "CONTACT_ONCOLOGY_OR_HPB_METASTATIC_DISEASE",
            "ORDER_MRI_LIVER_CLINICIAN_CONCERN", "REFER_HPB_CLINICIAN_CONCERN",
            "ADVANCED_IMAGING_ALREADY_DONE", "BIOPSY_CONSIDERED",
            "HEPATOLOGY_REFERRAL_ALREADY_MADE", "SURGICAL_REFERRAL_ALREADY_MADE",
            "URGENT_REFERRAL_FLAG",
        }
        LOW_RISK_CODES = {
            "HEMANGIOMA_BENIGN", "LESION_SIZE_RECORDED", "REFER_HPB_HEMANGIOMA_EXCEPTION",
            "NO_FOLLOWUP_HEMANGIOMA", "FNH_CONFIRMED", "FOLLOWUP_FNH_RADIOLOGY_RECOMMENDED",
            "NO_FOLLOWUP_FNH", "ORDER_MRI_CONFIRM_FNH",
            "REFER_HEPATOLOGY_ADENOMA", "TIMELY_REFERRAL_ADENOMA_PREGNANCY",
            "OCP_USE_RECORDED", "ANABOLIC_STEROID_USE_RECORDED", "ADENOMA_CONFIRMED",
            "ORDER_MRI_LIVER_LOW_RISK_SOLID", "REFER_HPB_LOW_RISK_INDETERMINATE",
            "REPEAT_IMAGING_PLANNED_RECORDED",
        }

        STEP_GROUPS = [
            ("lesion_entry", ENTRY_CODES),
            ("hemorrhage", HEMORRHAGE_CODES),
            ("cyst_pathway", CYST_CODES),
            ("risk_assessment", RISK_CODES),
            ("high_risk_mgt", HIGH_RISK_CODES),
            ("low_risk_mgt", LOW_RISK_CODES),
        ]

        GROUP_META = {
            "lesion_entry": ("🔬 Initial Lesion Classification", "#1d4ed8", "#1e3a5f", "#bfdbfe"),
            "hemorrhage":   ("🚨 Red Flag — Hemorrhage Check", "#dc2626", "#3b0a0a", "#fecaca"),
            "cyst_pathway": ("💧 Cyst Pathway", "#0d9488", "#052e16", "#99f6e4"),
            "risk_assessment": ("⚖️ Risk Assessment", "#7c3aed", "#1e1b4b", "#ddd6fe"),
            "high_risk_mgt": ("🔴 High-Risk Solid Lesion Management", "#dc2626", "#3b0a0a", "#fecaca"),
            "low_risk_mgt":  ("🟢 Low-Risk Lesion Management", "#16a34a", "#052e16", "#bbf7d0"),
        }

        grouped: dict = {k: [] for k, _ in STEP_GROUPS}
        stops_and_requests = []
        override_candidates = []

        all_actions_flat = []
        for output in outputs:
            if isinstance(output, Action):
                all_actions_flat.append(output)
            elif isinstance(output, (Stop, DataRequest)):
                stops_and_requests.append(output)
                if isinstance(output, Stop):
                    for a in getattr(output, "actions", []):
                        all_actions_flat.append(a)

        for action in all_actions_flat:
            placed = False
            for gkey, codes in STEP_GROUPS:
                if action.code in codes:
                    grouped[gkey].append(action)
                    placed = True
                    break
            if not placed:
                grouped["risk_assessment"].append(action)
            if action.override_options:
                override_candidates.append(action)

        # Also collect override_candidates from Stop actions
        for output in stops_and_requests:
            if isinstance(output, Stop):
                for a in getattr(output, "actions", []):
                    if a.override_options and a not in override_candidates:
                        override_candidates.append(a)

        def render_action(a: Action, extra_cls: str = "") -> None:
            u2c = {"urgent": "urgent", "warning": "warning", None: "routine", "": "routine"}
            cls = u2c.get(a.urgency or "", "routine")
            if extra_cls:
                cls = extra_cls
            badge_label = (a.urgency or "info").upper()
            label_html = html.escape(a.label).replace("\n", "<br>")
            items = ""
            if isinstance(a.details, dict):
                for k, v in a.details.items():
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k)).replace('_',' ').title()}:</b> {html.escape(str(v))}</li>"
            detail_html = f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""
            override_html = (
                '<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">'
                "🔒 Override available — reason required</p>"
                if a.override_options
                else ""
            )
            st.markdown(
                f'<div class="action-card {cls}">'
                f'<h4><span class="badge {cls}">{badge_label}</span> {label_html}</h4>'
                f"{detail_html}{override_html}</div>",
                unsafe_allow_html=True,
            )

        def render_group(gkey, actions):
            if not actions:
                return
            title, border, bg, tc = GROUP_META[gkey]
            action_block = ""
            for a in actions:
                urgency_icon = "🔴" if a.urgency == "urgent" else "🟢"
                label_e = html.escape(a.label)
                action_block += f'<li style="margin-bottom:5px">{urgency_icon} {label_e}'
                if isinstance(a.details, dict):
                    for dk, dv in a.details.items():
                        if dv not in (None, False, "", []):
                            action_block += f' <span style="color:#94a3b8;font-size:11px">({html.escape(str(dk)).replace("_"," ").title()}: {html.escape(str(dv))})</span>'
                action_block += "</li>"
            action_block = f'<ul style="margin:6px 0 0 14px;padding:0;font-size:13px">{action_block}</ul>'
            st.markdown(
                f'<div style="background:{bg};border-left:5px solid {border};'
                f'border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                f'<p style="margin:0 0 6px;font-size:13px;font-weight:700;color:{tc}">'
                f"{html.escape(title)}</p>"
                f"{action_block}</div>",
                unsafe_allow_html=True,
            )

        def render_stop_request(o):
            if isinstance(o, DataRequest):
                missing_str = ", ".join(f"`{f}`" for f in o.missing_fields)
                msg_html = html.escape(o.message).replace("\n", "<br>")
                st.markdown(
                    f'<div class="action-card warning">'
                    f'<h4><span class="badge warning">DATA NEEDED</span> ⏳ {msg_html}</h4>'
                    f"<ul><li>Missing: {missing_str}</li></ul></div>",
                    unsafe_allow_html=True,
                )
                for sa in o.suggested_actions:
                    render_action(sa, extra_cls="info")
            elif isinstance(o, Stop):
                reason_html = html.escape(o.reason).replace("\n", "<br>")
                cls_stop = "stop" if o.urgency == "urgent" else "warning"
                icon = "🚨" if o.urgency == "urgent" else "🛑"
                bg = "#3b0a0a" if o.urgency == "urgent" else "#2d1a00"
                border = "#ef4444" if o.urgency == "urgent" else "#f59e0b"
                tcol = "#fecaca" if o.urgency == "urgent" else "#fde68a"
                action_block = ""
                for a in getattr(o, "actions", []):
                    urg_icon = "🔴" if a.urgency == "urgent" else "🟢"
                    action_block += f"<li>{urg_icon} {html.escape(a.label)}"
                    if a.override_options:
                        action_block += ' <span style="color:#a5b4fc;font-size:11px">⊕ override available</span>'
                    action_block += "</li>"
                if action_block:
                    action_block = (
                        f'<ul style="margin:6px 0 0 14px;padding:0;font-size:13px">'
                        f"{action_block}</ul>"
                    )
                st.markdown(
                    f'<div style="background:{bg};border-left:5px solid {border};'
                    f"border-radius:10px;padding:14px 18px;margin-bottom:14px\">"
                    f'<p style="margin:0 0 {"6px" if action_block else "0"};font-size:13px;'
                    f'font-weight:700;color:{tcol}">{icon} {html.escape(reason_html)}</p>'
                    f"{action_block}</div>",
                    unsafe_allow_html=True,
                )

        # ── Render everything ──────────────────────────────────────────────
        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        # Blocking data requests first
        blocking = [o for o in stops_and_requests if isinstance(o, DataRequest)]
        for o in blocking:
            render_stop_request(o)

        # Grouped action steps
        for gkey, _ in STEP_GROUPS:
            render_group(gkey, grouped[gkey])

        # Terminal stops (end-of-pathway outcomes)
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
            "patient_context": {k: str(v) for k, v in patient_data.items()},
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
                st.markdown(
                    '<p class="section-label">CLINICIAN OVERRIDES</p>',
                    unsafe_allow_html=True,
                )
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
                            f'<div class="override-card">Engine decision based on: '
                            f"<b>{html.escape(preview)}</b></div>",
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
                            if st.button(
                                "✅ Apply Override",
                                key=f"ov_apply_{raw_node}_{raw_field}",
                            ):
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
                                    st.success(
                                        "Override applied. Click **▶ Run Pathway** to re-evaluate."
                                    )
                        with col2:
                            if existing and st.button(
                                "🗑 Remove Override",
                                key=f"ov_remove_{raw_node}_{raw_field}",
                            ):
                                st.session_state.lm_overrides = [
                                    o for o in st.session_state.lm_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.lm_overrides:
                    st.markdown(
                        '<p class="section-label">ACTIVE OVERRIDES</p>',
                        unsafe_allow_html=True,
                    )
                    for o in st.session_state.lm_overrides:
                        st.markdown(
                            '<div class="override-card">'
                            f"🛠 <b>{html.escape(_pretty(o.target_node))}</b> → "
                            f"<code>{html.escape(_pretty(o.field))}</code>"
                            f" set to <b>{html.escape(str(o.new_value))}</b><br>"
                            f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                            f'<span style="color:#64748b;font-size:11px">'
                            f"Applied: {o.created_at.strftime('%H:%M:%S')}</span>"
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
                        "  ".join(
                            f"`{k}={v}`"
                            for k, v in log.used_inputs.items()
                            if v is not None
                        )
                    )
