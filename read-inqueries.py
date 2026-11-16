import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
KEY_PATH = BASE_DIR / "secrets" / "serviceAccountKey.json"

if not KEY_PATH.exists():
    raise FileNotFoundError(f"Service account key file not found at {KEY_PATH}")

cred = credentials.Certificate(KEY_PATH)

firebase_admin.initialize_app(cred)
db = firestore.client()

docs = db.collection("inqueries").order_by("createdAt",
                                direction=firestore.Query.DESCENDING).limit(10).stream()
                                
count = 0
for doc in docs:
    data = doc.to_dict()

    category = data.get("category","분류없음")
    status = data.get("status","?")

    content = data.get("content","")

    print(f"[{category}] ({status}) ({content[:50]})")
    count += 1
print(f"총 {count} 건")

