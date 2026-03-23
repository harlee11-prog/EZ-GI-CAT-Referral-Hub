import streamlit as st

st.set_page_config(page_title="EZ GI CAT Clinical Decision Hub", page_icon="🏥", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.title("🏥EZ GI CAT Clinical Decision Support Hub")
st.caption("Alberta Health Services · Primary Care Networks")
st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.markdown("### 🦠 H. Pylori")
        nav1, pdf1 = st.columns([2, 1])
        with nav1:
            st.page_link("pages/1_H_Pylori.py", label="Open →", use_container_width=True)
        with pdf1:
            st.link_button("📄 PDF", "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-dh-pathway-hpylori.pdf", use_container_width=True)

with col2:
    with st.container(border=True):
        st.markdown("### 💊 Chronic Constipation")
        nav2, pdf2 = st.columns([2, 1])
        with nav2:
            st.page_link("pages/2_Constipation.py", label="Open →", use_container_width=True)
        with pdf2:
            st.link_button("📄 PDF", "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-dh-pathway-chronic-constipation.pdf", use_container_width=True)

with col3:
    with st.container(border=True):
        st.markdown("### 🩸 Iron Deficiency Anemia")
        nav3, pdf3 = st.columns([2, 1])
        with nav3:
            st.page_link("pages/3_IDA.py", label="Open →", use_container_width=True)
        with pdf3:
            st.link_button("📄 PDF", "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-cancer-iron-deficiency-anemia-pathway.pdf", use_container_width=True)


st.markdown("")

# ── ROW 2 ──
col4, col5, col6 = st.columns(3)

with col4:
    with st.container(border=True):
        st.markdown("### 🔬 Chronic Diarrhea")
        nav4, pdf4 = st.columns([2, 1])
        with nav4:
            st.page_link("pages/4_Chronic_Diarrhea.py", label="Open →", use_container_width=True)
        with pdf4:
            st.link_button("📄 PDF", "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-dh-pathway-chronic-diarrhea.pdf", use_container_width=True)

with col5:
    with st.container(border=True):
        st.markdown("### 🫁 Irritable Bowel Syndrome")
        nav5, pdf5 = st.columns([2, 1])
        with nav5:
            st.page_link("pages/5_IBS.py", label="Open →", use_container_width=True)
        with pdf5:
            st.link_button("📄 PDF", "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-dh-pathway-ibs.pdf", use_container_width=True)

with col6:
    with st.container(border=True):
        st.markdown("### 🩺 Rectal Bleeding")
        nav6, pdf6 = st.columns([2, 1])
        with nav6:
            st.page_link("pages/6_HRRB.py", label="Open →", use_container_width=True)
        with pdf6:
            st.link_button("📄 PDF", "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-cancer-high-risk-rectal-bleeding-pathway.pdf", use_container_width=True)
