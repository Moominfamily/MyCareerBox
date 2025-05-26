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
bucket = storage_client.get_bucket("mycareerbox-bw")

# ----------------- Session State -----------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "records" not in st.session_state:
    st.session_state.records = []
if "user_email" not in st.session_state:
    st.session_state.user_email = None

# ----------------- Restore from Query Params -----------------
query_params = st.query_params
if not st.session_state.authenticated and "email" in query_params:
    st.session_state.user_email = query_params["email"]
    st.session_state.authenticated = True

# ----------------- UI: Logo -----------------
def render_logo():
    with open("logo_white.png", "rb") as image_file:
        logo_base64 = base64.b64encode(image_file.read()).decode()

    st.markdown(
        f"""
        <style>
        .logo-container {{
            display: flex;
            align-items: center;
            margin-top: 0rem;
            margin-bottom: -1rem;
        }}
        .logo-img {{
            height: 64px;
            margin-right: 0.75rem;
        }}
        .logo-text {{
            font-size: 2rem;
            font-weight: 700;
            color: #1f2c4c;
        }}
        </style>
        <div class="logo-container">
            <img src="data:image/png;base64,{logo_base64}" class="logo-img">
            <div class="logo-text">MyCareerBox</div>
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
            records.insert(0, record)
        st.session_state.records = records
    except Exception as e:
        st.error(f"❌ Failed to load records: {e}")

# ----------------- Authentication -----------------
def login():
    render_logo()
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
            st.session_state.login_error = False
            load_records()
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
    render_logo()
    st.title("Internship & Job Application Tracker")
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.login_error = False
        st.session_state.user_email = None
        st.session_state.records = []
        st.query_params.clear()
        st.rerun()

# ----------------- Run App -----------------
if st.session_state.authenticated and not st.session_state.records:
    load_records()

if st.session_state.authenticated:
    main_app()
else:
    login()