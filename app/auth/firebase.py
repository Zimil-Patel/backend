import firebase_admin
from firebase_admin import credentials

def initialize_firebase():
    # Path to your Firebase service account key JSON file
    service_account_path = 'credentials/firebase-service-account.json'

    if firebase_admin._apps:
        # Firebase app is already initialized
        return
    
    # Initialize the Firebase app with the service account credentials
    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)
