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
        st.session_state.app_type = "chatbot"  # Changed default to chatbot


# ============================================================================
# Chatbot Functions (for /chat-messages endpoint)
# ============================================================================

def chatbot_streaming(
    query: str,
    user_id: str,
    conversation_id: str = "",
    inputs: Optional[dict] = None
) -> Generator[str, None, None]:
    """Send streaming chat request for Chatbot apps."""
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
    
    if st.session_state.debug_mode:
        st.write("**🔍 DEBUG - Chatbot Request:**")
        st.json(payload)
    
    try:
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=60) as response:
            
            if st.session_state.debug_mode:
                st.write(f"**🔍 DEBUG - Status:** `{response.status_code}`")
            
            if response.status_code != 200:
                error_text = response.text
                st.error(f"❌ HTTP {response.status_code}: {error_text}")
                yield f"Error: {error_text}"
                return
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    
                    if not line_str.strip():
                        continue
                    
                    if line_str.startswith(" "):
                        json_str = line_str[6:]
                        
                        try:
                            data = json.loads(json_str)
                            event = data.get("event", "")
                            
                            if st.session_state.debug_mode:
                                st.write(f"**Event:** `{event}`")
                            
                            if event in ["message", "agent_message"]:
                                answer = data.get("answer", "")
                                if answer:
                                    yield answer
                            
                            elif event == "message_end":
                                conv_id = data.get("conversation_id", "")
                                if conv_id:
                                    st.session_state.conversation_id = conv_id
                            
                            elif event == "error":
                                error_msg = data.get("message", "Unknown error")
                                st.error(f"❌ Error: {error_msg}")
                                yield f"\n\nError: {error_msg}"
                                break
                        
                        except json.JSONDecodeError:
                            continue
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Connection error: {str(e)}")
        yield f"Error: {str(e)}"


def chatbot_blocking(
    query: str,
    user_id: str,
    conversation_id: str = "",
    inputs: Optional[dict] = None
) -> dict:
    """Send blocking chat request for Chatbot apps."""
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
    
    if st.session_state.debug_mode:
        st.write("**🔍 DEBUG - Request:**")
        st.json(payload)
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if st.session_state.debug_mode:
            st.write(f"**🔍 DEBUG - Status:** `{response.status_code}`")
            st.write(f"**🔍 DEBUG - Response:**")
            st.code(response.text[:1000])
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get("answer", "No response.")
            
            if "conversation_id" in result:
                st.session_state.conversation_id = result["conversation_id"]
            
            return {"answer": answer, "raw": result}
        
        else:
            error_text = response.text
            st.error(f"❌ HTTP {response.status_code}: {error_text}")
            return {"answer": f"Error: {error_text}", "error": True}
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error: {str(e)}")
        return {"answer": f"Error: {str(e)}", "error": True}


# ============================================================================
# Workflow Functions (for /workflows/run endpoint)
# ============================================================================

def workflow_streaming(
    query: str,
    user_id: str,
    inputs: Optional[dict] = None
) -> Generator[str, None, None]:
    """Send streaming workflow request for Workflow apps."""
    if not st.session_state.api_key:
        yield "API key not configured."
        return
    
    url = f"{st.session_state.api_base_url}/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    workflow_inputs = {}
    if inputs:
        workflow_inputs.update(inputs)
    workflow_inputs["query"] = query
    
    payload = {
        "inputs": workflow_inputs,
        "response_mode": "streaming",
        "user": user_id
    }
    
    if st.session_state.debug_mode:
        st.write("**🔍 DEBUG - Workflow Request:**")
        st.json(payload)
    
    try:
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=120) as response:
            
            if response.status_code != 200:
                error_text = response.text
                st.error(f"❌ HTTP {response.status_code}: {error_text}")
                yield f"Error: {error_text}"
                return
            
            has_content = False
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    
                    if line_str.startswith(" "):
                        json_str = line_str[6:]
                        
                        try:
                            data = json.loads(json_str)
                            event = data.get("event", "")
                            
                            if event == "node_finished":
                                outputs = data.get("data", {}).get("outputs", {})
                                text = (
                                    outputs.get("text", "") or
                                    outputs.get("output", "") or
                                    outputs.get("result", "")
                                )
                                if text:
                                    has_content = True
                                    yield text
                            
                            elif event == "workflow_finished":
                                if not has_content:
                                    outputs = data.get("data", {}).get("outputs", {})
                                    text = (
                                        outputs.get("text", "") or
                                        outputs.get("output", "") or
                                        json.dumps(outputs, indent=2)
                                    )
                                    if text:
                                        yield text
                            
                            elif event == "error":
                                error_msg = data.get("message", "Unknown error")
                                st.error(f"❌ Error: {error_msg}")
                                break
                        
                        except json.JSONDecodeError:
                            continue
    
    except requests.exceptions.RequestException as e:
        yield f"Error: {str(e)}"


def workflow_blocking(
    query: str,
    user_id: str,
    inputs: Optional[dict] = None
) -> dict:
    """Send blocking workflow request for Workflow apps."""
    if not st.session_state.api_key:
        return {"answer": "API key not configured.", "error": True}
    
    url = f"{st.session_state.api_base_url}/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    workflow_inputs = {}
    if inputs:
        workflow_inputs.update(inputs)
    workflow_inputs["query"] = query
    
    payload = {
        "inputs": workflow_inputs,
        "response_mode": "blocking",
        "user": user_id
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            outputs = result.get("data", {}).get("outputs", {})
            
            answer = (
                outputs.get("text", "") or
                outputs.get("output", "") or
                json.dumps(outputs, indent=2)
            )
            
            return {"answer": answer, "raw": result}
        
        else:
            error_text = response.text
            return {"answer": f"Error: {error_text}", "error": True}
    
    except requests.exceptions.RequestException as e:
        return {"answer": f"Error: {str(e)}", "error": True}


def clear_conversation():
    """Clear conversation."""
    st.session_state.messages = []
    st.session_state.conversation_id = ""
    st.rerun()


# ============================================================================
# Main UI
# ============================================================================

def main():
    """Main application."""
    
    st.set_page_config(
        page_title="Dify AI Assistant",
        page_icon="🤖",
        layout="wide"
    )
    
    initialize_session_state()
    
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Settings")
        
        # API Config
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
        
        # App Type Selection - CRITICAL!
        st.write("### 🎯 App Type")
        app_type = st.radio(
            "What type of Dify app do you have?",
            options=["chatbot", "workflow"],
            index=0 if st.session_state.app_type == "chatbot" else 1,
            help="""
            **Chatbot**: Standard chat app with conversation memory (uses /chat-messages)
            **Workflow**: Task-based workflow app (uses /workflows/run)
            
            Check your Dify app to see which type it is!
            """
        )
        
        if app_type != st.session_state.app_type:
            st.session_state.app_type = app_type
            st.rerun()
        
        # Show which endpoint is being used
        endpoint = "/chat-messages" if app_type == "chatbot" else "/workflows/run"
        st.caption(f"📡 Using endpoint: `{endpoint}`")
        
        # Debug mode
        st.session_state.debug_mode = st.checkbox("🐛 Debug Mode", value=st.session_state.debug_mode)
        
        # Streaming
        use_streaming = st.checkbox("📡 Streaming", value=True)
        
        # Additional inputs
        with st.expander("📝 Additional Inputs"):
            st.info("Add custom input parameters (optional)")
            
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
                st.write("**Current Inputs:**")
                for key, value in st.session_state.custom_inputs.items():
                    col1, col2 = st.columns([3, 1])
                    col1.code(f"{key}: {value}")
                    if col2.button("🗑️", key=f"del_{key}"):
                        del st.session_state.custom_inputs[key]
                        st.rerun()
        
        st.divider()
        if st.button("🗑️ Clear Chat"):
            clear_conversation()
    
    # Main content
    app_icon = "💬" if st.session_state.app_type == "chatbot" else "⚙️"
    st.title(f"{app_icon} Dify AI {st.session_state.app_type.title()}")
    st.caption("Powered by Dify API and Streamlit")
    
    if not st.session_state.api_key:
        st.warning("⚠️ Configure your API key in the sidebar")
        st.info("""
        **Setup:**
        1. Get your API key from Dify app → Publish tab
        2. Select the correct **App Type** (Chatbot or Workflow)
        3. Paste API key in sidebar and click Save
        """)
    
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
            
            # Route to correct function based on app type
            if st.session_state.app_type == "chatbot":
                # CHATBOT MODE
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
            
            else:
                # WORKFLOW MODE
                if use_streaming:
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    for chunk in workflow_streaming(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        inputs=st.session_state.custom_inputs
                    ):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                
                else:
                    response = workflow_blocking(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        inputs=st.session_state.custom_inputs
                    )
                    full_response = response.get("answer", "No response.")
                    st.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    main()
