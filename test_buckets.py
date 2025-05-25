import streamlit as st
from google.cloud import storage
from google.oauth2 import service_account

service_account_info = st.secrets["gcp_service_account"]
credentials = service_account.Credentials.from_service_account_info(service_account_info)
storage_client = storage.Client(credentials=credentials)

print("Current project:", storage_client.project)
print("Available buckets:")
for b in storage_client.list_buckets():
    print("-", b.name)