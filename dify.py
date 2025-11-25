import streamlit as st
import requests
import uuid
import json
from typing import Generator, Optional

# ============================================================================
# Helper Functions
# ============================================================================

def initialize_session_state():
    """Initialize session state variables for chat history and conversation ID."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = ""
    
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    
    if "custom_inputs" not in st.session_state:
        st.session_state.custom_inputs = {}
    
    if "api_key" not in st.session_state:
        st.session_state.api_key = st.secrets.get("DIFY_API_KEY", "")
    
    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = st.secrets.get("DIFY_API_BASE_URL", "https://api.dify.ai/v1")
    
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False
    
    # NEW: App type selection
    if "app_type" not in st.session_state:
        st.session_state.app_type = "chatbot"  # "chatbot" or "workflow"


def workflow_run_blocking(
    query: str,
    user_id: str,
    inputs: Optional[dict] = None
) -> dict:
    """Send a blocking workflow run request to Dify API."""
    if not st.session_state.api_key:
        st.error("⚠️ Please configure your Dify API key in Settings")
        return {"answer": "API key not configured.", "error": True}
    
    url = f"{st.session_state.api_base_url}/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    # Workflow apps use "inputs" instead of "query"
    # Merge the query into inputs
    workflow_inputs = inputs or {}
    workflow_inputs["query"] = query  # Add query as an input variable
    
    payload = {
        "inputs": workflow_inputs,
        "response_mode": "blocking",
        "user": user_id
    }
    
    if st.session_state.debug_mode:
        st.write("**🔍 DEBUG - Workflow Request:**")
        st.json(payload)
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if st.session_state.debug_mode:
            st.write(f"**🔍 DEBUG - Status:** `{response.status_code}`")
            st.write(f"**🔍 DEBUG - Response:**")
            st.code(response.text[:1500])
        
        response.raise_for_status()
        result = response.json()
        
        # Extract output from workflow response
        data = result.get("data", {})
        outputs = data.get("outputs", {})
        
        # Try multiple possible output field names
        answer = (
            outputs.get("text", "") or
            outputs.get("output", "") or
            outputs.get("result", "") or
            outputs.get("answer", "") or
            str(outputs) if outputs else "No output received from workflow."
        )
        
        return {"answer": answer, "raw": result}
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error: {str(e)}")
        return {"answer": f"Error: {str(e)}", "error": True}


def workflow_run_streaming(
    query: str,
    user_id: str,
    inputs: Optional[dict] = None
) -> Generator[str, None, None]:
    """Send a streaming workflow run request to Dify API."""
    if not st.session_state.api_key:
        st.error("⚠️ Please configure your Dify API key in Settings")
        yield "API key not configured."
        return
    
    url = f"{st.session_state.api_base_url}/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    # Workflow apps use "inputs" instead of "query"
    workflow_inputs = inputs or {}
    workflow_inputs["query"] = query
    
    payload = {
        "inputs": workflow_inputs,
        "response_mode": "streaming",
        "user": user_id
    }
    
    if st.session_state.debug_mode:
        st.write("**🔍 DEBUG - Workflow Streaming Request:**")
        st.json(payload)
    
    has_received_content = False
    debug_events = []
    
    try:
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=120) as response:
            
            if st.session_state.
