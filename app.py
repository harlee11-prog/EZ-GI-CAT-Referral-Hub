import streamlit as st

st.set_page_config(
    page_title="EZ GI CAT Clinical Decision Support Hub",
    page_icon="🩺",
    layout="wide",
)

PATHWAYS = [
    {"title": "Helicobacter Pylori (H. pylori)", "page": "pages/1_H._Pylori.py", "pdf": "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-dh-pathway-hpylori.pdf", "group": "Upper GI", "desc": "Testing, treatment, and eradication follow-up."},
    {"title": "Gastroesophageal Reflux Disease (GERD)", "page": "pages/2_GERD.py", "pdf": "https://www.albertahealthservices.ca/assets/info/aph/if-aph-scn-dh-pathway-gerd.pdf", "group": "Upper GI", "desc": "Assessment and management of reflux symptoms."},
    {"title": "Dyspepsia", "page": "pages/3_Dyspepsia.py", "pdf": "https://www.albertahealthservices.ca/assets/info/aph/if-aph-scn-dh-pathway-dyspepsia.pdf", "group": "Upper GI", "desc": "Initial workup, alarm features, and referral triggers."},
    {"title": "Gastric Cancer", "page": "pages/4_Gastric_Cancer.py", "pdf": "https://www.albertahealthservices.ca/assets/info/aph/if-aph-prov-gastric-cancer-prevention-screening-and-diagnosis-primary-care-pathway.pdf", "group": "Upper GI", "desc": "Prevention, screening, diagnosis, and referral."},

    {"title": "Irritable Bowel Syndrome (IBS)", "page": "pages/5_IBS.py", "pdf": "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-ibs.pdf", "group": "Lower GI", "desc": "Diagnosis support and symptom-based pathway."},
    {"title": "Chronic Diarrhea", "page": "pages/6_Chronic_Diarrhea.py", "pdf": "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-chronic-diarrhea.pdf", "group": "Lower GI", "desc": "Stepwise evaluation of persistent diarrhea."},
    {"title": "Chronic Constipation", "page": "pages/7_Constipation.py", "pdf": "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-dh-pathway-chronic-constipation.pdf", "group": "Lower GI", "desc": "Assessment and treatment planning for constipation."},
    {"title": "Chronic Abdominal Pain", "page": "pages/13_Chronic_Abdominal_Pain.py", "pdf": "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-dh-pathway-chronic-abdominal-pain.pdf", "group": "Lower GI", "desc": "Evaluation and management of chronic abdominal pain."},
    {"title": "High Risk Rectal Bleeding (HRRB)", "page": "pages/8_HRRB.py", "pdf": "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-cancer-high-risk-rectal-bleeding-pathway.pdf", "group": "Lower GI", "desc": "High-risk rectal bleeding pathway and escalation guidance."},

    {"title": "Liver Mass", "page": "pages/9_Liver_Mass.py", "pdf": "https://www.albertahealthservices.ca/assets/info/aph/if-aph-prov-liver-mass-primary-care-pathway.pdf", "group": "Liver", "desc": "Primary care pathway for liver mass evaluation."},
    {"title": "Non-Alcoholic Fatty Liver Disease (NAFLD)", "page": "pages/10_NAFLD.py", "pdf": "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-nafld.pdf", "group": "Liver", "desc": "Risk stratification and fibrosis assessment support."},
    {"title": "Hepatitis C Virus (HCV)", "page": "pages/11_HCV.py", "pdf": "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-hepatitisc.pdf", "group": "Liver", "desc": "Hepatitis C assessment and pathway navigation."},

    {"title": "Iron Deficiency Anemia", "page": "pages/12_IDA.py", "pdf": "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-cancer-iron-deficiency-anemia-pathway.pdf", "group": "Cancer / Anemia", "desc": "Workup and referral pathway for iron deficiency anemia."},
]

GROUPS = ["Upper GI", "Lower GI", "Liver", "Cancer / Anemia"]

st.markdown("""
<style>
#MainMenu {visibility: hidden !important;}
header {visibility: hidden !important;}
footer {visibility: hidden !important;}
[data-testid="stToolbar"] {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
[data-testid="stStatusWidget"] {display: none !important;}
.stAppDeployButton {display: none !important;}
div[class*="viewerBadge"] {display: none !important;}

.stApp {
    background: linear-gradient(180deg, #f6f8fb 0%, #eef3f8 100%);
}

.block-container {
    max-width: 1240px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.hero {
    background: linear-gradient(135deg, #123b63 0%, #1d5d90 100%);
    border-radius: 22px;
    padding: 2.1rem 2.2rem;
    color: white;
    margin-bottom: 1.75rem;
    box-shadow: 0 18px 45px rgba(18, 59, 99, 0.18);
}

.hero h1 {
    margin: 0;
    font-size: 2.35rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    line-height: 1.1;
}

.hero p {
    margin: 0.8rem 0 0 0;
    color: rgba(255,255,255,0.9);
    font-size: 1rem;
    max-width: 900px;
}

.stat-row {
    display: flex;
    gap: 0.75rem;
    margin-top: 1.3rem;
    flex-wrap: wrap;
}

.stat-pill {
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 999px;
    padding: 0.52rem 0.9rem;
    font-size: 0.88rem;
    color: white;
    font-weight: 600;
}

.section-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 1.4px;
    color: #6b7280;
    font-weight: 800;
    margin: 1.1rem 0 0.7rem 0.15rem;
}

.tile-card {
    background: #ffffff;
    border: 1px solid #dbe4ee;
    border-radius: 18px;
    padding: 1.15rem 1rem 1rem 1rem;
    min-height: 170px;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    margin-bottom: 0.7rem;
}

.tile-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 14px 34px rgba(15, 23, 42, 0.09);
    border-color: #bfd0e2;
}

.tile-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 0.8rem;
}

.tile-title {
    font-size: 1.05rem;
    font-weight: 800;
    color: #1f2937;
    line-height: 1.15;
}

.tile-badge {
    font-size: 0.68rem;
    font-weight: 700;
    color: #24557d;
    background: #eaf2f9;
    border: 1px solid #d7e7f4;
    border-radius: 999px;
    padding: 0.24rem 0.52rem;
    white-space: nowrap;
}

.tile-desc {
    color: #667085;
    font-size: 0.93rem;
    line-height: 1.5;
}

.button-row {
    margin-bottom: 1.15rem;
}

[data-testid="stPageLink"] > div {
    width: 100%;
}

[data-testid="stPageLink"] a,
[data-testid="stPageLink"] a:link,
[data-testid="stPageLink"] a:visited {
    background: #123b63 !important;
    color: #ffffff !important;
    border-radius: 12px !important;
    padding: 0.68rem 0.9rem !important;
    font-weight: 700 !important;
    text-align: center !important;
    border: 1px solid #123b63 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-decoration: none !important;
    min-height: 44px !important;
}

[data-testid="stPageLink"] a:hover,
[data-testid="stPageLink"] a:active,
[data-testid="stPageLink"] a:focus {
    background: #0f3254 !important;
    color: #ffffff !important;
    border-color: #0f3254 !important;
    box-shadow: none !important;
    text-decoration: none !important;
}

[data-testid="stPageLink"] a *,
[data-testid="stPageLink"] [data-testid="stMarkdownContainer"],
[data-testid="stPageLink"] [data-testid="stMarkdownContainer"] p,
[data-testid="stPageLink"] span,
[data-testid="stPageLink"] p {
    color: #ffffff !important;
    fill: #ffffff !important;
    margin: 0 !important;
    font-weight: 700 !important;
}

.stLinkButton > a,
.stLinkButton > a:link,
.stLinkButton > a:visited {
    background: #f8fafc !important;
    color: #334155 !important;
    border: 1px solid #d1dae6 !important;
    border-radius: 12px !important;
    padding: 0.68rem 0.9rem !important;
    min-height: 44px !important;
    font-weight: 700 !important;
}

.stLinkButton > a:hover {
    background: #eef4f8 !important;
    color: #1f2937 !important;
    border-color: #c2cfdd !important;
}

hr {
    margin-top: 0.5rem !important;
    margin-bottom: 1rem !important;
}

@media (max-width: 900px) {
    .hero h1 {
        font-size: 1.8rem;
    }

    .tile-card {
        min-height: auto;
    }
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="hero">
    <h1>EZ GI CAT Clinical Decision Support Hub</h1>
    <p>Primary care decision pathways for common GI and liver presentations, with direct access to internal tools and AHS pathway PDFs.</p>
    <div class="stat-row">
        <div class="stat-pill">13 pathways</div>
        <div class="stat-pill">Primary care focused</div>
        <div class="stat-pill">PDF references linked</div>
        <div class="stat-pill">Clinical workflow hub</div>
    </div>
</div>
""", unsafe_allow_html=True)

for group in GROUPS:
    items = [p for p in PATHWAYS if p["group"] == group]
    st.markdown(f'<div class="section-label">{group}</div>', unsafe_allow_html=True)

    cols = st.columns(3)
    for i, item in enumerate(items):
        with cols[i % 3]:
            st.markdown(
                f"""
                <div class="tile-card">
                    <div class="tile-top">
                        <div class="tile-title">{item["title"]}</div>
                        <div class="tile-badge">{item["group"]}</div>
                    </div>
                    <div class="tile-desc">{item["desc"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown('<div class="button-row">', unsafe_allow_html=True)
            c1, c2 = st.columns([1.2, 1])
            with c1:
                st.page_link(item["page"], label="Open pathway", use_container_width=True)
            with c2:
                st.link_button("View PDF", item["pdf"], use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
