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
    
    # Initialize API configuration from secrets or empty strings
    if "api_key" not in st.session_state:
        st.session_state.api_key = st.secrets.get("DIFY_API_KEY", "")
    
    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = st.secrets.get("DIFY_API_BASE_URL", "https://api.dify.ai/v1")
    
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False


def chat_with_dify_blocking(
    query: str,
    user_id: str,
    conversation_id: str = "",
    inputs: Optional[dict] = None
) -> dict:
    """Send a blocking chat request to Dify API."""
    if not st.session_state.api_key:
        st.error("⚠️ Please configure your Dify API key in Settings")
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
        
        response.raise_for_status()
        result = response.json()
        
        # Extract answer from different possible locations
        answer = result.get("answer", "")
        
        # If no answer in root, check in data field (for workflow responses)
        if not answer and "data" in result:
            data = result["data"]
            if isinstance(data, dict):
                answer = data.get("outputs", {}).get("text", "") or data.get("text", "")
        
        # Update conversation_id
        if "conversation_id" in result and not st.session_state.conversation_id:
            st.session_state.conversation_id = result["conversation_id"]
        
        return {"answer": answer or "No response text received.", "raw": result}
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error: {str(e)}")
        return {"answer": f"Error: {str(e)}", "error": True}


def chat_with_dify_streaming(
    query: str,
    user_id: str,
    conversation_id: str = "",
    inputs: Optional[dict] = None
) -> Generator[str, None, None]:
    """Send a streaming chat request to Dify API - FIXED VERSION."""
    if not st.session_state.api_key:
        st.error("⚠️ Please configure your Dify API key in Settings")
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
        st.write("**🔍 DEBUG - Streaming Request:**")
        st.json(payload)
    
    has_received_content = False
    debug_events = []
    
    try:
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=60) as response:
            
            if st.session_state.debug_mode:
                st.write(f"**🔍 DEBUG - Stream Status:** `{response.status_code}`")
            
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    
                    if st.session_state.debug_mode:
                        debug_events.append(line_str)
                    
                    # Skip empty lines
                    if not line_str.strip():
                        continue
                    
                    # Dify streaming responses are in SSE format: " {...}"
                    if line_str.startswith(" "):
                        json_str = line_str[6:]  # Remove " " prefix
                        
                        try:
                            data = json.loads(json_str)
                            event = data.get("event", "")
                            
                            if st.session_state.debug_mode and not has_received_content:
                                st.write(f"**🔍 First Event Type:** `{event}`")
                            
                            # Handle ALL possible event types
                            if event in ["message", "agent_message"]:
                                # Chatbot app - regular message chunk
                                answer = data.get("answer", "")
                                if answer:
                                    has_received_content = True
                                    yield answer
                            
                            elif event == "agent_thought":
                                # Agent thinking process (optional to display)
                                thought = data.get("thought", "")
                                if thought and st.session_state.debug_mode:
                                    yield f"\n[Thinking: {thought}]\n"
                            
                            elif event == "workflow_started":
                                # Workflow started
                                if st.session_state.debug_mode:
                                    yield "[Workflow started...]\n\n"
                            
                            elif event == "node_started":
                                # Workflow node started
                                node_data = data.get("data", {})
                                node_title = node_data.get("title", "Unknown")
                                if st.session_state.debug_mode:
                                    yield f"[Processing: {node_title}...]\n"
                            
                            elif event == "node_finished":
                                # Workflow node finished - THIS IS KEY FOR WORKFLOWS
                                node_data = data.get("data", {})
                                
                                # Try multiple possible output locations
                                outputs = node_data.get("outputs", {})
                                
                                # Check for text output
                                text_output = (
                                    outputs.get("text", "") or
                                    outputs.get("output", "") or
                                    outputs.get("result", "") or
                                    node_data.get("process_data", {}).get("outputs", {}).get("text", "")
                                )
                                
                                if text_output:
                                    has_received_content = True
                                    yield text_output
                            
                            elif event == "text_chunk":
                                # Some workflows return text_chunk events
                                text = data.get("data", {}).get("text", "")
                                if text:
                                    has_received_content = True
                                    yield text
                            
                            elif event == "workflow_finished":
                                # Workflow finished - extract final output
                                workflow_data = data.get("data", {})
                                outputs = workflow_data.get("outputs", {})
                                
                                # If we haven't received content yet, get it from final output
                                if not has_received_content:
                                    final_text = (
                                        outputs.get("text", "") or
                                        outputs.get("output", "") or
                                        outputs.get("result", "") or
                                        str(outputs) if outputs else ""
                                    )
                                    
                                    if final_text:
                                        has_received_content = True
                                        yield final_text
                            
                            elif event == "message_end":
                                # Final message with conversation_id
                                conv_id = data.get("conversation_id", "")
                                if conv_id and not st.session_state.conversation_id:
                                    st.session_state.conversation_id = conv_id
                            
                            elif event == "error":
                                # Error occurred
                                error_msg = data.get('message', 'Unknown error')
                                st.error(f"❌ Dify Error: {error_msg}")
                                yield f"\n\n[Error: {error_msg}]"
                                break
                        
                        except json.JSONDecodeError as e:
                            if st.session_state.debug_mode:
                                st.warning(f"⚠️ JSON decode error: {str(e)}")
                            continue
            
            # If we didn't receive any content, show debug info
            if not has_received_content:
                st.warning("⚠️ No content was received in the stream.")
                if st.session_state.debug_mode:
                    with st.expander("🔍 DEBUG - All Events Received"):
                        for evt in debug_events[:30]:  # Show first 30 events
                            st.code(evt)
                
                yield "No response received. This might be a workflow app - try enabling Debug Mode to see what events are being received."
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Connection error: {str(e)}")
        yield f"Connection error: {str(e)}"


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
                help="Enter your Dify app API key (starts with 'app-')"
            )
            
            api_url_input = st.text_input(
                "API Base URL",
                value=st.session_state.api_base_url,
                help="Dify API base URL"
            )
            
            if st.button("💾 Save Configuration"):
                st.session_state.api_key = api_key_input
                st.session_state.api_base_url = api_url_input
                st.success("✅ Configuration saved!")
                st.rerun()
        
        # Debug mode - IMPORTANT FOR TROUBLESHOOTING
        st.session_state.debug_mode = st.checkbox(
            "🐛 Debug Mode (Show Events)",
            value=st.session_state.debug_mode,
            help="Show what events are being received from Dify"
        )
        
        # Streaming mode toggle
        use_streaming = st.checkbox(
            "📡 Enable Streaming",
            value=True,
            help="Stream responses for real-time display"
        )
        
        # Additional inputs
        with st.expander("📝 Additional Inputs", expanded=False):
            st.info("Add custom input parameters")
            
            col1, col2 = st.columns(2)
            with col1:
                input_key = st.text_input("Key", placeholder="e.g., city")
            with col2:
                input_value = st.text_input("Value", placeholder="e.g., Hong Kong")
            
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
        if st.session_state.conversation_id:
            st.caption(f"**Conversation:** `{st.session_state.conversation_id[:8]}...`")
        
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            clear_conversation()
    
    # Main content
    st.title("🤖 Dify AI Chatbot")
    st.caption("Powered by Dify API and Streamlit")
    
    if not st.session_state.api_key:
        st.warning("⚠️ Please configure your Dify API key in the sidebar.")
        st.info("""
        **Quick Start:**
        1. Go to your Dify workspace
        2. Open your app → **Publish** tab
        3. Copy the **API Secret Key** (starts with `app-`)
        4. Paste it in sidebar Settings
        """)
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Enter your question...", disabled=not st.session_state.api_key):
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        custom_inputs = st.session_state.custom_inputs
        
        with st.chat_message("assistant"):
            
            if use_streaming:
                message_placeholder = st.empty()
                full_response = ""
                
                try:
                    for chunk in chat_with_dify_streaming(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        conversation_id=st.session_state.conversation_id,
                        inputs=custom_inputs
                    ):
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(f"❌ {error_msg}")
                    full_response = error_msg
                
            else:
                try:
                    response = chat_with_dify_blocking(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        conversation_id=st.session_state.conversation_id,
                        inputs=custom_inputs
                    )
                    
                    full_response = response.get("answer", "No response received.")
                    st.markdown(full_response)
                
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(f"❌ {error_msg}")
                    full_response = error_msg
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    main()
