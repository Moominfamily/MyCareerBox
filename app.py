import streamlit as st
import pyrebase
import pandas as pd
import tempfile
import os
import datetime
from google.cloud import storage
from google.cloud import firestore
from google.oauth2 import service_account
import base64

# ----------------- Firebase Configuration -----------------
firebaseConfig = st.secrets["firebase"]
firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()

service_account_info = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(service_account_info)
storage_client = storage.Client(credentials=credentials)
db = firestore.Client(credentials=credentials)
bucket = storage_client.get_bucket("mycareerbox-bw.firebasestorage.app")

# ----------------- Session State -----------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "records" not in st.session_state:
    st.session_state.records = []

# ----------------- Restore from Query Params -----------------
query_params = st.query_params
if not st.session_state.authenticated and "email" in query_params:
    st.session_state.user_email = query_params["email"]
    st.session_state.authenticated = True

# ----------------- UI: Logo and Title -----------------
with open("logo_white.png", "rb") as image_file:
    logo_base64 = base64.b64encode(image_file.read()).decode()

st.markdown(
    f"""
    <style>
    .block-container {{
        padding-top: 1.5rem !important;
    }}
    .logo-wrapper {{
        margin-top: -5rem;
        margin-bottom: -6rem;
        text-align: left;
        padding-left: 0.1rem;
    }}
    .logo {{
        height: 240px;
    }}
    h1, h2, h3, h4, h5, h6 {{
        margin-top: 0.5rem;
    }}
    </style>
    <div class="logo-wrapper">
        <img src="data:image/png;base64,{logo_base64}" class="logo">
    </div>
    """,
    unsafe_allow_html=True
)

# ----------------- Load Records -----------------
def load_records():
    try:
        docs = db.collection("records").document(st.session_state.user_email).collection("entries").stream()
        records = []
        for doc in docs:
            record = doc.to_dict()
            record["doc_id"] = doc.id
            records.append(record)
        st.session_state.records = sorted(records, key=lambda r: r["date"], reverse=True)
    except Exception as e:
        st.error(f"❌ Failed to load records: {e}")

# ----------------- Authentication -----------------
def login():
    st.title("Log In")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if "login_error" not in st.session_state:
        st.session_state.login_error = False

    if st.button("Log In"):
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            st.session_state.authenticated = True
            st.session_state.user_email = email
            st.query_params.update({"email": email})
            st.rerun()
        except:
            st.session_state.login_error = True
            st.rerun()

    if st.session_state.login_error:
        st.error("Invalid email or password.")

    if st.button("Sign Up"):
        try:
            user = auth.create_user_with_email_and_password(email, password)
            st.success("Account created! Please log in.")
        except:
            st.error("Could not create account. Try a different email.")

# ----------------- Main App -----------------
def main_app():
    st.title("Internship & Job Application Tracker")
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.session_state.records = []
        st.query_params.clear()
        st.rerun()

    with st.form("entry_form"):
        col1, col2, col3 = st.columns(3)
        company = col1.text_input("Company")
        position = col2.text_input("Position")
        url = col3.text_input("Application URL")

        col4, col5, col6 = st.columns(3)
        resume_file = col4.file_uploader("Resume", type=["pdf", "docx"])
        contact = col5.text_input("Contact Info")
        status = col6.selectbox("Current Status", [
            "To Apply", "Online Test", "1st Interview", "2nd Interview", "3rd Interview", "Offer", "No Response", "Rejected"])

        jd = st.text_area("Job Description")
        dt = st.date_input("Date", value=datetime.date.today())
        submitted = st.form_submit_button("Add Record")

    if submitted:
        if resume_file:
            filename = resume_file.name
            blob = bucket.blob(f"{st.session_state.user_email}/{filename}")
            blob.upload_from_file(resume_file, content_type=resume_file.type)
        else:
            filename = "None"

        record = {
            "company": company,
            "position": position,
            "url": url,
            "resume": filename,
            "contact": contact,
            "status": status,
            "jd": jd,
            "date": str(dt)
        }

        try:
            doc_ref = db.collection("records") \
                        .document(st.session_state.user_email) \
                        .collection("entries") \
                        .add(record)
            record["doc_id"] = doc_ref[1].id
            st.session_state.records.insert(0, record)
            st.success("Record written to Firestore successfully.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Firestore write failed: {e}")

    st.markdown("""---""")
    search = st.text_input("Search by company name")

    for i, r in enumerate(st.session_state.records):
        if search.lower() in r["company"].lower():
            with st.expander(f"{r['company']} – {r['position']} ({r['status']})"):
                st.markdown(f"**Date:** {r['date']}")
                st.markdown(f"**URL:** [{r['url']}]({r['url']})")
                if r["resume"] != "None":
                    blob = bucket.blob(f"{st.session_state.user_email}/{r['resume']}")
                    signed_url = blob.generate_signed_url(
                        expiration=datetime.timedelta(hours=1),
                        method="GET"
                    )
                    st.markdown(f"**Resume:** [{r['resume']}]({signed_url})")
                else:
                    st.markdown("**Resume:** None")
                st.markdown(f"**Contact:** {r['contact']}")
                new_status = st.selectbox(
                    "Update Status",
                    ["To Apply", "Online Test", "1st Interview", "2nd Interview", "3rd Interview", "Offer", "No Response", "Rejected"],
                    index=["To Apply", "Online Test", "1st Interview", "2nd Interview", "3rd Interview", "Offer", "No Response", "Rejected"].index(r["status"]),
                    key=f"status_{i}"
                )

                if new_status != r["status"]:
                    try:
                        doc_id = r.get("doc_id")
                        if doc_id:
                            db.collection("records") \
                              .document(st.session_state.user_email) \
                              .collection("entries") \
                              .document(doc_id) \
                              .update({"status": new_status})
                            r["status"] = new_status
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to update status in Firestore: {e}")
                if r["jd"]:
                    st.markdown("**Job Description:**")
                    st.code(r["jd"])
                if st.button(f"Delete Record {i+1}", key=f"delete_{i}"):
                    try:
                        doc_id = r.get("doc_id")
                        if doc_id:
                            db.collection("records").document(st.session_state.user_email).collection("entries").document(doc_id).delete()
                        st.session_state.records.pop(i)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to delete record from Firestore: {e}")

    if st.button("Download All Records as Excel") and st.session_state.records:
        df = pd.DataFrame(st.session_state.records)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            df.to_excel(tmp.name, index=False, engine="openpyxl")
            with open(tmp.name, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="records.xlsx">Click here to download your Excel file</a>'
                st.markdown(href, unsafe_allow_html=True)
            os.remove(tmp.name)

# ----------------- Run App -----------------
if st.session_state.authenticated and not st.session_state.records:
    load_records()

if st.session_state.authenticated:
    main_app()
else:
    login()