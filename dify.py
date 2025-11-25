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
    """
    Send a blocking chat request to Dify API.
    
    Args:
        query: User's question/message
        user_id: Unique identifier for the user
        conversation_id: ID for maintaining conversation context (empty for first message)
        inputs: Additional input parameters (optional)
    
    Returns:
        Response dictionary from Dify API
    """
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
    
    # Add conversation_id only if it exists (not first message)
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    # Debug logging
    if st.session_state.debug_mode:
        st.write("**🔍 DEBUG - Request Details:**")
        st.write(f"- URL: `{url}`")
        st.write(f"- Headers: `{{'Authorization': 'Bearer {st.session_state.api_key[:10]}...', 'Content-Type': 'application/json'}}`")
        st.write(f"- Payload: `{payload}`")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        # Debug logging
        if st.session_state.debug_mode:
            st.write(f"**🔍 DEBUG - Response Status:** `{response.status_code}`")
            st.write(f"**🔍 DEBUG - Response Headers:** `{dict(response.headers)}`")
            st.write(f"**🔍 DEBUG - Response Text:** `{response.text[:500]}`")
        
        response.raise_for_status()
        result = response.json()
        
        if st.session_state.debug_mode:
            st.write(f"**🔍 DEBUG - Parsed Response:** `{result}`")
        
        return result
    
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP Error {response.status_code}: {response.text}"
        st.error(f"❌ API Error: {error_msg}")
        return {"answer": f"Error: {error_msg}", "error": True}
    
    except requests.exceptions.Timeout:
        st.error("❌ Request timed out. Please try again.")
        return {"answer": "Request timed out.", "error": True}
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Connection error: {str(e)}")
        return {"answer": f"Connection error: {str(e)}", "error": True}
    
    except json.JSONDecodeError as e:
        st.error(f"❌ Invalid JSON response: {str(e)}")
        return {"answer": "Invalid response from API.", "error": True}


def chat_with_dify_streaming(
    query: str,
    user_id: str,
    conversation_id: str = "",
    inputs: Optional[dict] = None
) -> Generator[str, None, None]:
    """
    Send a streaming chat request to Dify API.
    
    Args:
        query: User's question/message
        user_id: Unique identifier for the user
        conversation_id: ID for maintaining conversation context
        inputs: Additional input parameters (optional)
    
    Yields:
        Chunks of the response as they arrive
    """
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
    
    # Debug logging
    if st.session_state.debug_mode:
        st.write("**🔍 DEBUG - Streaming Request:**")
        st.write(f"- URL: `{url}`")
        st.write(f"- Payload: `{payload}`")
    
    try:
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=60) as response:
            
            if st.session_state.debug_mode:
                st.write(f"**🔍 DEBUG - Stream Status:** `{response.status_code}`")
            
            response.raise_for_status()
            
            full_response_debug = []
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    
                    if st.session_state.debug_mode:
                        full_response_debug.append(line_str)
                    
                    # Dify streaming responses are in SSE format: " {...}"
                    if line_str.startswith(" "):
                        json_str = line_str[6:]  # Remove " " prefix
                        
                        try:
                            data = json.loads(json_str)
                            
                            # Handle different event types
                            event = data.get("event", "")
                            
                            if event == "message" or event == "agent_message":
                                # Regular message chunk
                                answer = data.get("answer", "")
                                if answer:
                                    yield answer
                            
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
                                st.warning(f"⚠️ JSON decode error for line: {line_str[:100]}")
                            continue
            
            if st.session_state.debug_mode and full_response_debug:
                with st.expander("🔍 DEBUG - Full Streaming Response"):
                    st.code("\n".join(full_response_debug[:20]))  # Show first 20 lines
    
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP Error {response.status_code}: {response.text}"
        st.error(f"❌ API Error: {error_msg}")
        yield f"Error: {error_msg}"
    
    except requests.exceptions.Timeout:
        st.error("❌ Request timed out. Please try again.")
        yield "Request timed out."
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Connection error: {str(e)}")
        yield f"Connection error: {str(e)}"


def test_api_connection():
    """Test the API connection and return diagnostics."""
    if not st.session_state.api_key:
        return {"status": "error", "message": "API key not configured"}
    
    url = f"{st.session_state.api_base_url}/chat-messages"
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    # Simple test payload
    payload = {
        "inputs": {},
        "query": "Hello",
        "response_mode": "blocking",
        "user": "test-user"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            return {"status": "success", "message": "API connection successful!", "data": response.json()}
        else:
            return {
                "status": "error",
                "message": f"API returned status {response.status_code}",
                "details": response.text
            }
    
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Connection failed: {str(e)}"}


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
    
    # Page configuration
    st.set_page_config(
        page_title="Dify AI Chatbot",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state FIRST
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
                help="Enter your Dify API key from your Dify workspace"
            )
            
            api_url_input = st.text_input(
                "API Base URL",
                value=st.session_state.api_base_url,
                help="Dify API base URL (default: https://api.dify.ai/v1)"
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("💾 Save", use_container_width=True):
                    st.session_state.api_key = api_key_input
                    st.session_state.api_base_url = api_url_input
                    st.success("✅ Saved!")
                    st.rerun()
            
            with col2:
                if st.button("🧪 Test API", use_container_width=True):
                    with st.spinner("Testing connection..."):
                        result = test_api_connection()
                        
                        if result["status"] == "success":
                            st.success(f"✅ {result['message']}")
                            st.json(result.get("data", {}))
                        else:
                            st.error(f"❌ {result['message']}")
                            if "details" in result:
                                st.code(result["details"])
        
        # Debug mode toggle
        st.session_state.debug_mode = st.checkbox(
            "🐛 Debug Mode",
            value=st.session_state.debug_mode,
            help="Show detailed request/response information"
        )
        
        # Streaming mode toggle
        use_streaming = st.checkbox(
            "📡 Enable Streaming",
            value=True,
            help="Stream responses for real-time display"
        )
        
        # Additional inputs
        with st.expander("📝 Additional Inputs", expanded=False):
            st.info("Add custom input parameters to send with your queries")
            
            col1, col2 = st.columns(2)
            with col1:
                input_key = st.text_input("Input Key", placeholder="e.g., city")
            with col2:
                input_value = st.text_input("Input Value", placeholder="e.g., Hong Kong")
            
            if st.button("➕ Add Input", use_container_width=True) and input_key and input_value:
                st.session_state.custom_inputs[input_key] = input_value
                st.success(f"✅ Added: {input_key} = {input_value}")
                st.rerun()
            
            # Display current custom inputs
            if st.session_state.custom_inputs:
                st.write("**Current Inputs:**")
                for key, value in st.session_state.custom_inputs.items():
                    col1, col2 = st.columns([3, 1])
                    col1.code(f"{key}: {value}")
                    if col2.button("🗑️", key=f"del_{key}"):
                        del st.session_state.custom_inputs[key]
                        st.rerun()
        
        # Conversation info
        st.divider()
        st.caption(f"**User ID:** `{st.session_state.user_id[:8]}...`")
        if st.session_state.conversation_id:
            st.caption(f"**Conversation:** `{st.session_state.conversation_id[:8]}...`")
        else:
            st.caption("**Conversation:** New conversation")
        
        st.caption(f"**Messages:** {len(st.session_state.messages)}")
        
        # Clear conversation button
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            clear_conversation()
    
    # Main content
    st.title("🤖 Dify AI Chatbot")
    st.caption("Powered by Dify API and Streamlit")
    
    # Warning if API key not configured
    if not st.session_state.api_key:
        st.warning("⚠️ Please configure your Dify API key in the sidebar Settings to start chatting.")
        st.info("""
        **To get your Dify API key:**
        1. Log into your Dify workspace at https://dify.ai
        2. Navigate to your application
        3. Go to the **API Access** section
        4. Generate and copy your API key
        5. Paste it in the sidebar Settings and click Test API
        """)
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Enter your question here...", disabled=not st.session_state.api_key):
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get custom inputs if any
        custom_inputs = st.session_state.custom_inputs
        
        # Display assistant response
        with st.chat_message("assistant"):
            
            if use_streaming:
                # Streaming response
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
                    error_msg = f"Unexpected error: {str(e)}"
                    st.error(f"❌ {error_msg}")
                    full_response = error_msg
                
            else:
                # Blocking response
                try:
                    response = chat_with_dify_blocking(
                        query=prompt,
                        user_id=st.session_state.user_id,
                        conversation_id=st.session_state.conversation_id,
                        inputs=custom_inputs
                    )
                    
                    full_response = response.get("answer", "No response received.")
                    
                    # Update conversation_id if this is the first message
                    if not st.session_state.conversation_id and "conversation_id" in response:
                        st.session_state.conversation_id = response["conversation_id"]
                    
                    st.markdown(full_response)
                
                except Exception as e:
                    error_msg = f"Unexpected error: {str(e)}"
                    st.error(f"❌ {error_msg}")
                    full_response = error_msg
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": full_response})


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    main()
