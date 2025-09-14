import os
from uuid import uuid4

from google.cloud import firestore
from google.cloud.firestore_v1.document import DocumentReference

DATABASE_NAME = os.getenv('FIRESTORE_DATABASE')
CHATS_COLLECTION = os.getenv('FIRESTORE_CHATS_COLLECTION')
MESSAGES_COLLECTION = os.getenv('FIRESTORE_MESSAGES_COLLECTION')

db = firestore.Client(database=DATABASE_NAME)

def get_chat_id(uid):
    chat_docs = db.collection(CHATS_COLLECTION).where('uid', '==', uid).get()

    if len(chat_docs) == 0:
        chat_id = str(uuid4())
        chat_ref = db.collection(CHATS_COLLECTION).document(chat_id)
        chat_data = {'chat_id': chat_id, 'uid': uid}
        chat_ref.set(chat_data)
    else:
        chat_id = chat_docs[0].to_dict().get('chat_id')

    return chat_id


def create_message(uid, chat_id, session_id, role, text):
    msg_id = str(uuid4())
    msg_doc = db.collection(MESSAGES_COLLECTION).document(msg_id)
    msg_data = {
        'msg_id': msg_id,
        'text': text,
        'role': role,
        'timestamp': firestore.SERVER_TIMESTAMP,
        'chat_id': chat_id,
        'uid': uid,
        'session_id': session_id
    }
    msg_doc.set(msg_data)

    return msg_id


def get_chat_history(limit, chat_id, msg_id=None):
    msgs = []

    if not msg_id:
        msg_docs = (
            db.collection(MESSAGES_COLLECTION)
            .where('chat_id', '==', chat_id)
            .order_by('timestamp', firestore.Query.DESCENDING)
            .limit(limit)
            .get()
        )
    else:
        msg_doc = db.collection(MESSAGES_COLLECTION).document(msg_id).get()
        msg_docs = (
            db.collection(MESSAGES_COLLECTION)
            .where('chat_id', '==', chat_id)
            .where('timestamp', '<', msg_doc.to_dict().get('timestamp'))
            .order_by('timestamp', firestore.Query.DESCENDING)
            .limit(6)
            .get()
        )

    for doc in msg_docs:
        msgs.append(doc.to_dict())

    msgs = sorted(msgs, key=lambda d: d['timestamp'])

    return msgs
