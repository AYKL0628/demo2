import streamlit as st
import requests
import uuid
import json
from typing import Generator, Optional

# ============================================================================
# Helper Functions
# ============================================================================

def initialize_session_state():
    """Initialize session state variables."""
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
    
    if "app_type" not in st.session_state:
        st.session_state.app_type = "workflow"  # Default to workflow


def workflow_run_blocking(
    query: str,
    user_id: str,
    inputs: Optional[dict] = None
) -> dict:
    """Send a blocking workflow run request - FIXED VERSION."""
    if not st.session_state.api_key:
        st.error("⚠️ Please configure your Dify API key")
        return {"answer": "API key not configured.", "error": True}
    
    url = f"{st.session_state.api_base_url}/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    # FIXED: Workflows use ONLY "inputs" - no separate "query" field
    # Merge query into inputs dictionary
    workflow_inputs = inputs.copy() if inputs else {}
    
    # Add query to inputs - you may need to adjust the key name
    # Common key names: "query", "input", "text", "question"
    # Check your workflow's Start node to see what input variable name it expects
    workflow_inputs["query"] = query
    
    payload = {
        "inputs": workflow_inputs,
        "response_mode": "blocking",
        "user": user_id
    }
    
    if st.session_state.debug_mode:
        st.write("**🔍 DEBUG - Request Payload:**")
        st.json(payload)
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if st.session_state.debug_mode:
            st.write(f"**🔍 DEBUG - Status:** `{response.status_code}`")
            st.write(f"**🔍 DEBUG - Response:**")
            st.code(response.text[:2000])
        
        response.raise_for_status()
        result = response.json()
        
        # Extract output from workflow
        data = result.get("data", {})
        outputs = data.get("outputs", {})
        
        # Try different possible output field names
        answer = (
            outputs.get("text", "") or
            outputs.get("output", "") or
            outputs.get("result", "") or
            outputs.get("answer", "") or
            json.dumps(outputs, indent=2) if outputs else "No output received."
        )
        
        return {"answer": answer, "raw": result}
    
    except requests.exceptions.HTTPError as e:
        error_details = response.text if 'response' in locals() else str(e)
        st.error(f"❌ HTTP Error {response.status_code}: {error_details}")
        return {"answer": f"Error {response.status_code}: {error_details}", "error": True}
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Connection Error: {str(e)}")
        return {"answer": f"Error: {str(e)}", "error": True}


def workflow_run_streaming(
    query: str,
    user_id: str,
    inputs: Optional[dict] = None
) -> Generator[str, None, None]:
    """Send a streaming workflow run request - FIXED VERSION."""
    if not st.session_state.api_key:
        st.error("⚠️ Please configure your Dify API key")
        yield "API key not configured."
        return
    
    url = f"{st.session_state.api_base_url}/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    # FIXED: Use only inputs, no separate query parameter
    workflow_inputs = inputs.copy() if inputs else {}
    workflow_inputs["query"] = query
    
    payload = {
        "inputs": workflow_inputs,
        "response_mode": "streaming",
        "user": user_id
    }
    
    if st.session_state.debug_mode:
        st.write("**🔍 DEBUG - Streaming Payload:**")
        st.json(payload)
    
    has_received_content = False
    debug_events = []
    
    try:
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=120) as response:
            
            if st.session_state.debug_mode:
                st.write(f"**🔍 DEBUG - Status:** `{response.status_code}`")
            
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    
                    if st.session_state.debug_mode:
                        debug_events.append(line_str)
                    
                    if not line_str.strip():
                        continue
                    
                    if line_str.startswith(" "):
                        json_str = line_str[6:]
                        
                        try:
                            data = json.loads(json_str)
                            event = data.get("event", "")
                            
                            if st.session_state.debug_mode and len(debug_events) <= 3:
                                st.write(f"**🔍 Event:** `{event}`")
                            
                            if event == "workflow_started":
                                if st.session_state.debug_mode:
                                    yield "⚙️ Workflow started...\n\n"
                            
                            elif event == "node_started":
                                node_data = data.get("data", {})
                                node_title = node_data.get("title", "Processing")
                                if st.session_state.debug_mode:
                                    yield f"▶️ {node_title}...\n"
                            
                            elif event == "node_finished":
                                node_data = data.get("data", {})
                                outputs = node_data.get("outputs", {})
                                
                                text_output = (
                                    outputs.get("text", "") or
                                    outputs.get("output", "") or
                                    outputs.get("result", "") or
                                    outputs.get("answer", "")
                                )
                                
                                if text_output:
                                    has_received_content = True
                                    yield text_output
                            
                            elif event == "text_chunk" or event == "text":
                                text_data = data.get("data", {})
                                text = text_data.get("text", "") or text_data.get("delta", "")
                                if text:
                                    has_received_content = True
                                    yield text
                            
                            elif event == "workflow_finished":
                                workflow_data = data.get("data", {})
                                outputs = workflow_data.get("outputs", {})
                                
                                if not has_received_content:
                                    final_text = (
                                        outputs.get("text", "") or
                                        outputs.get("output", "") or
                                        outputs.get("result", "") or
                                        outputs.get("answer", "") or
                                        json.dumps(outputs, indent=2) if outputs else ""
                                    )
                                    
                                    if final_text:
                                        has_received_content = True
                                        yield final_text
                            
                            elif event == "error":
                                error_msg = data.get('message', 'Unknown error')
                                st.error(f"❌ Workflow Error: {error_msg}")
                                yield f"\n\n**Error:** {error_msg}"
                                break
                        
                        except json.JSONDecodeError:
                            continue
            
            if not has_received_content:
                st.warning("⚠️ No output received from workflow")
                if st.session_state.debug_mode:
                    with st.expander("🔍 DEBUG - All Events"):
                        for evt in debug_events[:30]:
                            st.code(evt)
                
                yield "No output received. Check your workflow configuration."
    
    except requests.exceptions.HTTPError as e:
        error_details = response.text if 'response' in locals() else str(e)
        st.error(f"❌ HTTP Error: {error_details}")
        yield f"Error: {error_details}"
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Connection Error: {str(e)}")
        yield f"Error: {str(e)}"


def chatbot_blocking(
    query: str,
    user_id: str,
    conversation_id: str = "",
    inputs: Optional[dict] = None
) -> dict:
    """Send a blocking chat request (for Chatbot apps)."""
    if not st.session_state.api_key:
        return {"answer": "API key not configured.", "error": True}
    
    url = f"{st.session_state.api_base_url}/chat-messages"
    
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": inputs or {},
        "query": query,
        "response_mode": "blocking",
        "user": user_id
    }
    
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        answer = result.get("answer", "No response.")
        
        if "conversation_id" in result:
            st.session_state.conversation_id = result["conversation_id"]
        
        return {"answer": answer, "raw": result}
    
    except requests.exceptions.RequestException as e:
        return {"answer": f"Error: {str(e)}", "error": True}


def chatbot_streaming(
    query: str,
    user_id: str,
    conversation_id: str = "",
    inputs: Optional[dict] = None
) -> Generator[str, None, None]:
    """Send a streaming chat request (for Chatbot apps)."""
    if not st.session_state.api_key:
        yield "API key not configured."
        return
    
    url = f"{st.session_state.api_base_url}/chat-messages"
    
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": inputs or {},
        "query": query,
        "response_mode": "streaming",
        "user": user_id
    }
    
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    try:
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=60) as response:
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    
                    if line_str.startswith(" "):
                        json_str = line_str[6:]
                        
                        try:
                            data = json.loads(json_str)
                            event = data.get("event", "")
                            
                            if event in ["message", "agent_message"]:
                                answer = data.get("answer", "")
                                if answer:
                                    yield answer
                            
                            elif event == "message_end":
                                conv_id = data.get("conversation_id", "")
                                if conv_id:
                                    st.session_state.conversation_id = conv_id
                            
                            elif event == "error":
                                st.error(f"❌ Error: {data.get('message', 'Unknown error')}")
                                break
                        
                        except json.JSONDecodeError:
                            continue
    
    except requests.exceptions.RequestException as e:
        yield f"Error: {str(e)}"


def clear_conversation():
    """Clear conversation."""
    st.session_state.messages = []
    st.session_state.conversation_id = ""
    st.rerun()


# ============================================================================
# Streamlit UI
# ============================================================================

def main():
    """Main application."""
    
    st.set_page_config(
        page_title="Dify AI App",
        page_icon="🤖",
        layout="wide"
    )
    
    initialize_session_state()
    
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Settings")
        
        # API Configuration
        with st.expander("🔑 API Configuration", expanded=not bool(st.session_state.api_key)):
            api_key_input = st.text_input(
                "Dify API Key",
                value=st.session_state.api_key,
                type="password"
            )
            
            api_url_input = st.text_input(
                "API Base URL",
                value=st.session_state.api_base_url
            )
            
            if st.button("💾 Save"):
                st.session_state.api_key = api_key_input
                st.session_state.api_base_url = api_url_input
                st.success("✅ Saved!")
                st.rerun()
        
        # App Type
        st.write("### 🔧 App Type")
        app_type = st.radio(
            "Select app type:",
            options=["workflow", "chatbot"],
            index=0 if st.session_state.app_type == "workflow" else 1
        )
        
        if app_type != st.session_state.app_type:
            st.session_state.app_type = app_type
            st.rerun()
        
        # Debug mode
        st.session_state.debug_mode = st.checkbox("🐛 Debug Mode", value=st.session_state.debug_mode)
        
        # Streaming
        use_streaming = st.checkbox("📡 Streaming", value=True)
        
        # Custom inputs
        with st.expander("📝 Custom Inputs"):
            st.info("Add input variables (optional)")
            
            col1, col2 = st.columns(2)
            with col1:
                input_key = st.text_input("Key", placeholder="e.g., language")
            with col2:
                input_value = st.text_input("Value", placeholder="e.g., English")
            
            if st.button("➕ Add") and input_key and input_value:
                st.session_state.custom_inputs[input_key] = input_value
                st.success(f"✅ Added: {input_key}")
                st.rerun()
            
            if st.session_state.custom_inputs:
                for key, value in st.session_state.custom_inputs.items():
                    col1, col2 = st.columns([3, 1])
                    col1.code(f"{key}: {value}")
                    if col2.button("🗑️", key=f"del_{key}"):
                        del st.session_state.custom_inputs[key]
                        st.rerun()
        
        st.divider()
        if st.button("🗑️ Clear Chat"):
            clear_conversation()
    
    # Main
    app_icon = "⚙️" if st.session_state.app_type == "workflow" else "💬"
    st.title(f"{app_icon} Dify AI {st.session_state.app_type.title()}")
    
    if not st.session_state.api_key:
        st.warning("⚠️ Configure API key in sidebar")
    
    # Display messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Type your message...", disabled=not st.session_state.api_key):
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            
            if st.session_state.app_type == "workflow":
                # Workflow mode
                if use_streaming:
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    for chunk in workflow_run_streaming(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        inputs=st.session_state.custom_inputs
                    ):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                else:
                    response = workflow_run_blocking(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        inputs=st.session_state.custom_inputs
                    )
                    full_response = response.get("answer", "No response.")
                    st.markdown(full_response)
            
            else:
                # Chatbot mode
                if use_streaming:
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    for chunk in chatbot_streaming(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        conversation_id=st.session_state.conversation_id,
                        inputs=st.session_state.custom_inputs
                    ):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                else:
                    response = chatbot_blocking(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        conversation_id=st.session_state.conversation_id,
                        inputs=st.session_state.custom_inputs
                    )
                    full_response = response.get("answer", "No response.")
                    st.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    main()
