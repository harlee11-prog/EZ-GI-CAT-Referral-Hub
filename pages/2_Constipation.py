import streamlit as st, sys
sys.path.insert(0, "/content")

from chronic_constipation_engine import (
    ChronicConstipationPatient, ChronicConstipationPathwayEngine,
    generate_clinical_report, TreatmentTier
)

st.set_page_config(page_title="Chronic Constipation", page_icon="💊", layout="wide")
st.title("💊 Chronic Constipation Pathway")
st.markdown("---")

left, right = st.columns([1, 1.4])

with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 55)
    sex = st.selectbox("Sex", ["female", "male", "other"])
    crcl = st.number_input("Creatinine clearance mL/min (for Prucalopride dosing)", 0.0, 200.0, 75.0)
    hepatic = st.checkbox("Severe hepatic impairment")

    st.markdown("**Rome IV Diagnostic Criteria**")
    st.caption("Check all symptoms present for ≥25% of defecations")
    symptom_months = st.slider("Symptomatic months in last 6", 0, 6, 3)
    bm_per_week    = st.number_input("Bowel movements per week", 0, 21, 2)
    hard_stool     = st.checkbox("Hard or lumpy stool (Bristol type 1–2)")
    straining      = st.checkbox("Straining during defecation")
    incomplete_ev  = st.checkbox("Incomplete evacuation")
    anorectal_blk  = st.checkbox("Anorectal blockage sensation")
    manual_man     = st.checkbox("Manual maneuvers needed")

    st.markdown("**IBS-C Exclusion**")
    st.caption("If BOTH are predominant → route to IBS-C pathway instead")
    abd_pain = st.checkbox("Predominant abdominal pain")
    bloating = st.checkbox("Predominant bloating")

    st.markdown("**Defecatory Dysfunction Signals**")
    perineal_inj = st.checkbox("Traumatic perineal injury")
    outlet_blk   = st.checkbox("Persistent outlet blockage sensation")
    wiggle       = st.checkbox("Must wiggle/rotate on toilet to defecate")

    st.markdown("**Alarm Features**")
    st.caption("Any alarm feature triggers urgent referral")
    al_family_crc  = st.checkbox("Family history (1st degree) colorectal cancer")
    al_weight_loss = st.checkbox("Unintended weight loss >5% over 6–12 months")
    al_bowel_chg   = st.checkbox("Sudden or progressive change in bowel habit")
    al_blood       = st.checkbox("Visible blood in stool")
    al_ida         = st.checkbox("Iron deficiency anemia")
    al_anal_mass   = st.checkbox("Anal mass or irregularity on rectal exam")

    st.markdown("**Treatment History**")
    tx_tier_label = st.selectbox("Current treatment tier", [
        "Treatment Naive",
        "Failed Lifestyle / Fibre",
        "Failed Bulk / Osmotic Laxatives",
        "Failed Stimulant Laxatives",
        "Failed Advanced Therapy",
    ])
    tier_map = {
        "Treatment Naive":                 TreatmentTier.NAIVE,
        "Failed Lifestyle / Fibre":        TreatmentTier.FAILED_LIFESTYLE,
        "Failed Bulk / Osmotic Laxatives": TreatmentTier.FAILED_BULK_OSMOTIC,
        "Failed Stimulant Laxatives":      TreatmentTier.FAILED_STIMULANT,
        "Failed Advanced Therapy":         TreatmentTier.FAILED_ADVANCED,
    }
    months_on_therapy  = st.number_input("Months on current therapy", 0.0, 60.0, 0.0, 0.5)
    failed_lax_classes = st.number_input("Distinct laxative classes tried", 0, 10, 0)
    secondary_reviewed = st.checkbox("Secondary causes reviewed")

    run = st.button("▶ Run Pathway", type="primary", use_container_width=True)

with right:
    st.subheader("Clinical Recommendations")
    if run:
        patient = ChronicConstipationPatient(
            age=age,
            sex=sex,
            crcl_ml_min=crcl if crcl > 0 else None,
            severe_hepatic_impairment=hepatic or None,
            symptom_months_in_last_6=symptom_months,
            bowel_movements_per_week=bm_per_week,
            hard_lumpy_stool=hard_stool or None,
            straining=straining or None,
            incomplete_evacuation=incomplete_ev or None,
            anorectal_blockage=anorectal_blk or None,
            manual_maneuvers=manual_man or None,
            abdominal_pain_predominant=abd_pain or None,
            bloating_predominant=bloating or None,
            traumatic_perineal_injury=perineal_inj or None,
            outlet_blockage_sensation=outlet_blk or None,
            needs_wiggle_to_defecate=wiggle or None,
            alarm_family_hx_colorectal_cancer=al_family_crc or None,
            alarm_unintended_weight_loss=al_weight_loss or None,
            alarm_sudden_change_bowel_habit=al_bowel_chg or None,
            alarm_blood_in_stool=al_blood or None,
            alarm_iron_deficiency_anemia=al_ida or None,
            alarm_anal_mass_or_irregularity=al_anal_mass or None,
            treatment_tier=tier_map[tx_tier_label],
            months_on_current_therapy=months_on_therapy if months_on_therapy > 0 else None,
            failed_laxative_classes_count=failed_lax_classes,
            secondary_causes_reviewed=secondary_reviewed or None,
        )
        engine  = ChronicConstipationPathwayEngine()
        actions = engine.evaluate(patient)
        report  = generate_clinical_report(patient, actions, engine)

        if patient.has_alarm_features:
            st.error("🚨 Alarm features detected — urgent referral recommended")
        if patient.has_ibs_c_features:
            st.warning("⚠ IBS-C features present — consider IBS-C pathway")
        st.code(report, language=None)
    else:
        st.info("Fill in details on the left and click ▶ Run Pathway")
