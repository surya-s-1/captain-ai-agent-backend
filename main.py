# from dotenv import load_dotenv
# load_dotenv()

import os
import uuid
import uvicorn
import logging
from typing import List, Dict, Optional
from fastapi import FastAPI, Body, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from auth import get_current_user
from gcp.agent import ask_agent

from gcp.firestore import (
    get_chat_id,
    create_message,
    get_chat_history
)

allow_domains = os.getenv('ALLOW_DOMAINS', '')
origins = [domain.strip() for domain in allow_domains.split(',') if domain.strip()]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/health')
async def health_check():
    return 'OK'


@app.post('/query')
async def new_query(
    request: Request,
    user: Dict = Depends(get_current_user),
):
    try:
        uid = user.get('uid', None)
        if not uid:
            raise HTTPException(status_code=401, detail='Unauthorized')

        session_id = request.headers.get('x-session-id')
        if not session_id:
            session_id = f'session_{uuid.uuid4()}'

        body = await request.json()
        query = body.get('query')
        if not query:
            raise HTTPException(status_code=400, detail='Missing \'text\' in request body')

        chat_id = get_chat_id(uid)
        msg_id = create_message(uid, chat_id, session_id, 'user', query)
        
        return PlainTextResponse(
            headers={'x-session-id': session_id},
            content=msg_id
        )

    except HTTPException as e:
        raise e

    except Exception as e:
        logging.exception(e)

        raise HTTPException(status_code=500)


@app.get('/response')
async def get_response(
    request: Request,
    user: Dict = Depends(get_current_user),
):
    try:
        uid = user.get('uid', None)
        if not uid:
            raise HTTPException(status_code=401, detail='Unauthorized')

        # 1. Extract Authorization header and session id 
        session_id = request.headers.get('x-session-id')       
        if not session_id:
            raise HTTPException(status_code=400, detail='Missing session id')

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise HTTPException(
                status_code=401, detail='Missing or invalid Authorization header'
            )
        token = auth_header.split(' ', 1)[1]

        # 2. Get user query
        chat_id = get_chat_id(uid)
        history = get_chat_history(6, chat_id)

        if not history:
            raise HTTPException(status_code=400, detail='No history found')

        history = history[-6:]
        query = ''

        for each in history:
            query += f'{each.get('role', '')}: {each.get('text', '')}' + '\n'

        # 3. Ask Agent
        response_text, session_id = await ask_agent(uid, token, session_id, query)

        # 4. Store response
        msg_id = create_message(uid, chat_id, session_id, 'model', response_text)

        return JSONResponse(
            content={'msg_id': msg_id, 'text': response_text},
            headers={'x-session-id': session_id}
        )

    except HTTPException as e:
        raise e

    except Exception as e:
        logging.exception(e)
        raise HTTPException(status_code=500)


@app.get('/chat-history')
async def chat_history(
    msg_id: Optional[str] = None, user: Dict = Depends(get_current_user)
):
    try:
        uid = user.get('uid', None)
        if not uid:
            raise HTTPException(status_code=401, detail='Unauthorized')

        chat_id = get_chat_id(uid)
        history = get_chat_history(6, chat_id, msg_id)

        formatted_history = []
        for each in history:
            formatted_history.append(
                {
                    'msg_id': each.get('msg_id', ''),
                    'text': each.get('text', ''),
                    'timestamp': each.get('timestamp', ''),
                    'role': each.get('role', ''),
                    'session_id': each.get('session_id', '')
                }
            )

        return formatted_history

    except Exception as e:
        logging.exception(e)

        raise HTTPException(status_code=500)

if __name__ == '__main__':
    uvicorn.run(app=app, host='0.0.0.0', port=8002)
