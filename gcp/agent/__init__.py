import os
import json

from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
# from google.adk.sessions import InMemorySessionService
from google.adk.tools.openapi_tool.auth import auth_helpers
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import (
    OpenAPIToolset,
)

from gcp.agent.sessions import FirestoreSessionService
from gcp.agent.prompts import INSTRUCTION

# ----------------- Env/Constants -----------------
APP_NAME_OPENAPI=os.getenv('APP_NAME_OPENAPI')
AGENT_NAME_OPENAPI=os.getenv('AGENT_NAME_OPENAPI')
GEMINI_MODEL=os.getenv('GEMINI_MODEL')
OPENAPI_SPEC_FILE = 'openapi.json'

try:
    with open(OPENAPI_SPEC_FILE, 'r') as f:
        openapi_spec_json = json.dumps(json.load(f))
except FileNotFoundError:
    raise FileNotFoundError(f'OpenAPI spec file not found at {OPENAPI_SPEC_FILE}')

# ----------------- Helpers -----------------
def create_openapi_toolset(token: str):
    '''Return an OpenAPI toolset that attaches the Bearer token.'''
    return OpenAPIToolset(
        spec_str=openapi_spec_json,
        spec_str_type='json',
        auth_scheme=auth_helpers.token_to_scheme_credential(
            'oauth2Token', 'header', 'Authorization', token
        )[0],
        auth_credential=auth_helpers.token_to_scheme_credential(
            'oauth2Token', 'header', 'Authorization', token
        )[1],
    )


async def setup_session_and_runner(uid: str, token: str, session_id: str):
    '''Initialize runner with the user-provided token.'''
    # session_service_openapi = InMemorySessionService()
    session_service_openapi = FirestoreSessionService()

    agent = LlmAgent(
        name=AGENT_NAME_OPENAPI,
        model=GEMINI_MODEL,
        tools=[create_openapi_toolset(token)],
        instruction=INSTRUCTION,
        description='Manages a Jira test cases creaion application using tools generated from an OpenAPI spec.',
    )

    runner_openapi = Runner(
        agent=agent,
        app_name=APP_NAME_OPENAPI,
        session_service=session_service_openapi,
    )

    await session_service_openapi.create_session(
        app_name=APP_NAME_OPENAPI, user_id=uid, session_id=session_id
    )

    return runner_openapi, session_id


async def call_openapi_agent_async(uid: str, session_id: str, query: str, runner: Runner):
    '''Send a query to the agent and return its final text response.'''
    content = types.Content(role='user', parts=[types.Part(text=query)])
    final_response_text = 'Agent did not provide a final text response.'

    async for event in runner.run_async(
        user_id=uid,
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response_text = event.content.parts[0].text.strip()

    return final_response_text


async def ask_agent(uid: str, token: str, session_id: str, query: str):
    runner, session_id = await setup_session_and_runner(uid, token, session_id)
    response_text = await call_openapi_agent_async(uid, session_id, query, runner)
    return response_text, session_id
