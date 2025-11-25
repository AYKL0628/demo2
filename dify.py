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
            
            if st.session_state.debug_mode:
                st.write(f"**🔍 DEBUG - Stream Status:** `{response.status_code}`")
            
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
                            
                            if st.session_state.debug_mode and not has_received_content:
                                st.write(f"**🔍 First Event:** `{event}`")
                            
                            # Workflow-specific events
                            if event == "workflow_started":
                                if st.session_state.debug_mode:
                                    yield "[Workflow started...]\n\n"
                            
                            elif event == "node_started":
                                node_data = data.get("data", {})
                                node_title = node_data.get("title", "Processing")
                                if st.session_state.debug_mode:
                                    yield f"[{node_title}...]\n"
                            
                            elif event == "node_finished":
                                # Key event for workflow outputs
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
                            
                            elif event == "text_chunk":
                                text = data.get("data", {}).get("text", "")
                                if text:
                                    has_received_content = True
                                    yield text
                            
                            elif event == "workflow_finished":
                                # Final workflow output
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
                                yield f"\n\n[Error: {error_msg}]"
                                break
                        
                        except json.JSONDecodeError:
                            continue
            
            if not has_received_content:
                st.warning("⚠️ No output received from workflow.")
                if st.session_state.debug_mode:
                    with st.expander("🔍 DEBUG - All Events"):
                        for evt in debug_events[:30]:
                            st.code(evt)
                
                yield "No output received. Check that your workflow has an output variable configured."
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error: {str(e)}")
        yield f"Error: {str(e)}"


def chatbot_blocking(
    query: str,
    user_id: str,
    conversation_id: str = "",
    inputs: Optional[dict] = None
) -> dict:
    """Send a blocking chat request to Dify API (for Chatbot apps)."""
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
        
        answer = result.get("answer", "No response received.")
        
        if "conversation_id" in result and not st.session_state.conversation_id:
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
    """Send a streaming chat request to Dify API (for Chatbot apps)."""
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
                                if conv_id and not st.session_state.conversation_id:
                                    st.session_state.conversation_id = conv_id
                            
                            elif event == "error":
                                error_msg = data.get('message', 'Unknown error')
                                st.error(f"❌ Error: {error_msg}")
                                break
                        
                        except json.JSONDecodeError:
                            continue
    
    except requests.exceptions.RequestException as e:
        yield f"Error: {str(e)}"


def clear_conversation():
    """Clear the current conversation and start fresh."""
    st.session_state.messages = []
    st.session_state.conversation_id = ""
    st.rerun()


# ============================================================================
# Streamlit UI
# ============================================================================

def main():
    """Main Streamlit application."""
    
    st.set_page_config(
        page_title="Dify AI Chatbot",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
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
                type="password",
                help="Your Dify app API key (starts with 'app-')"
            )
            
            api_url_input = st.text_input(
                "API Base URL",
                value=st.session_state.api_base_url,
                help="Default: https://api.dify.ai/v1"
            )
            
            if st.button("💾 Save Configuration"):
                st.session_state.api_key = api_key_input
                st.session_state.api_base_url = api_url_input
                st.success("✅ Configuration saved!")
                st.rerun()
        
        # App Type Selection - KEY SETTING
        st.write("### 🔧 App Type")
        app_type = st.radio(
            "Select your Dify app type:",
            options=["chatbot", "workflow"],
            index=0 if st.session_state.app_type == "chatbot" else 1,
            help="""
            **Chatbot**: Standard chat apps with conversation memory
            **Workflow**: Task-based apps that process inputs and return outputs
            """
        )
        
        if app_type != st.session_state.app_type:
            st.session_state.app_type = app_type
            st.rerun()
        
        # Debug mode
        st.session_state.debug_mode = st.checkbox(
            "🐛 Debug Mode",
            value=st.session_state.debug_mode,
            help="Show detailed request/response information"
        )
        
        # Streaming mode
        use_streaming = st.checkbox(
            "📡 Enable Streaming",
            value=True,
            help="Stream responses in real-time"
        )
        
        # Additional inputs
        with st.expander("📝 Additional Inputs", expanded=False):
            st.info("Add custom input variables for your Dify app")
            
            col1, col2 = st.columns(2)
            with col1:
                input_key = st.text_input("Key", placeholder="e.g., language")
            with col2:
                input_value = st.text_input("Value", placeholder="e.g., English")
            
            if st.button("➕ Add", use_container_width=True) and input_key and input_value:
                st.session_state.custom_inputs[input_key] = input_value
                st.success(f"✅ Added: {input_key} = {input_value}")
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
        st.caption(f"**User ID:** `{st.session_state.user_id[:8]}...`")
        if st.session_state.app_type == "chatbot" and st.session_state.conversation_id:
            st.caption(f"**Conversation:** `{st.session_state.conversation_id[:8]}...`")
        
        if st.button("🗑️ Clear Chat", use_container_width=True):
            clear_conversation()
    
    # Main content
    st.title("🤖 Dify AI " + ("Chatbot" if st.session_state.app_type == "chatbot" else "Workflow"))
    
    app_type_badge = "💬 Chatbot" if st.session_state.app_type == "chatbot" else "⚙️ Workflow"
    st.caption(f"{app_type_badge} | Powered by Dify API and Streamlit")
    
    if not st.session_state.api_key:
        st.warning("⚠️ Please configure your Dify API key in the sidebar.")
        st.info("""
        **Setup Instructions:**
        1. Go to https://cloud.dify.ai
        2. Open your app → **Publish** tab
        3. Copy the **API Secret Key**
        4. Paste it in sidebar Settings
        5. Select the correct **App Type** (Chatbot or Workflow)
        """)
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Enter your message...", disabled=not st.session_state.api_key):
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        custom_inputs = st.session_state.custom_inputs
        
        with st.chat_message("assistant"):
            
            # Route to correct function based on app type
            if st.session_state.app_type == "workflow":
                # WORKFLOW MODE
                if use_streaming:
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    for chunk in workflow_run_streaming(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        inputs=custom_inputs
                    ):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                else:
                    response = workflow_run_blocking(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        inputs=custom_inputs
                    )
                    full_response = response.get("answer", "No response.")
                    st.markdown(full_response)
            
            else:
                # CHATBOT MODE
                if use_streaming:
                    message_placeholder = st.empty()
                    full_response = ""
                    
                    for chunk in chatbot_streaming(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        conversation_id=st.session_state.conversation_id,
                        inputs=custom_inputs
                    ):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                else:
                    response = chatbot_blocking(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        conversation_id=st.session_state.conversation_id,
                        inputs=custom_inputs
                    ):
                    full_response = response.get("answer", "No response.")
                    st.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    main()
