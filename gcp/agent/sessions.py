from google.cloud import firestore
from google.adk.sessions import BaseSessionService, Session
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part
import os
import time

FIRESTORE_DATABASE = os.getenv('FIRESTORE_DATABASE')
COLLECTION_NAME = 'adk-sessions'


class FirestoreSessionService(BaseSessionService):
    def __init__(self):
        self.db = firestore.Client(database=FIRESTORE_DATABASE)

    async def create_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        initial_state: dict | None = None,
    ) -> Session:
        session = Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            state=initial_state or {},
            events=[],
            last_update_time=time.time(),
        )
        self.db.collection(COLLECTION_NAME).document(session_id).set(
            session.model_dump()
        )
        return session

    async def get_session(
        self, app_name: str, user_id: str, session_id: str
    ) -> Session:
        session_doc = self.db.collection(COLLECTION_NAME).document(session_id).get()

        if (
            not session_doc.exists
            or session_doc.get('app_name') != app_name
            or session_doc.get('user_id') != user_id
        ):
            raise ValueError(
                f'Session {session_id} not found for {app_name}/{user_id}.'
            )

        session_data = session_doc.to_dict()

        events = []
        for event_data in session_data.get('events', []):
            content = (
                Content(
                    role=event_data.get('content', {}).get('role', ''),
                    parts=[
                        Part(text=p['text'])
                        for p in event_data.get('content', {}).get('parts', [])
                    ],
                )
                if 'content' in event_data
                else None
            )

            actions = (
                EventActions(
                    state_delta=event_data.get('actions', {}).get('state_delta', {})
                )
                if 'actions' in event_data
                else None
            )

            events.append(Event(content=content, actions=actions))

        return Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            events=events,
            state=session_data.get('state', {}),
            last_update_time=session_data.get('last_update_time', time.time()),
        )

    async def append_event(self, session: Session, event: Event):
        session.events.append(event)

        if event.actions and event.actions.state_delta:
            session.state.update(event.actions.state_delta)

        session_data = session.model_dump()
        session_data['last_update_time'] = firestore.SERVER_TIMESTAMP

        self.db.collection(COLLECTION_NAME).document(session.id).update(session_data)

    async def list_sessions(self, app_name: str, user_id: str):
        sessions = (
            self.db.collection(COLLECTION_NAME)
            .where('app_name', '==', app_name)
            .where('user_id', '==', user_id)
            .stream()
        )
        sessions = [session.to_dict() for session in sessions]
        sessions.sort(key=lambda x: x['last_update_time'], reverse=True)
        sessions = [Session(**session) for session in sessions]
        return sessions

    async def delete_session(self, app_name: str, user_id: str, session_id: str):
        session_doc_ref = self.db.collection(COLLECTION_NAME).document(session_id)
        session_doc = session_doc_ref.get()

        if (
            session_doc.exists
            and session_doc.get('app_name') == app_name
            and session_doc.get('user_id') == user_id
        ):
            session_doc_ref.delete()
        else:
            raise ValueError(
                f'Session {session_id} not found for {app_name}/{user_id}.'
            )
