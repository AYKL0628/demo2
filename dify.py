import streamlit as st
import requests
import uuid
import json
from typing import Generator, Optional

# ============================================================================
# Configuration
# ============================================================================

def get_api_config():
    """Get API configuration from secrets or session state."""
    if "api_key" not in st.session_state:
        st.session_state.api_key = st.secrets.get("DIFY_API_KEY", "")
    
    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = st.secrets.get("DIFY_API_BASE_URL", "https://api.dify.ai/v1")
    
    return st.session_state.api_key, st.session_state.api_base_url


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
    api_key, api_base_url = get_api_config()
    
    if not api_key:
        st.error("⚠️ Please configure your Dify API key in Settings")
        return {"answer": "API key not configured.", "error": True}
    
    url = f"{api_base_url}/chat-messages"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
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
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        st.error(f"Error communicating with Dify API: {str(e)}")
        return {"answer": "Sorry, I encountered an error. Please try again.", "error": True}


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
    api_key, api_base_url = get_api_config()
    
    if not api_key:
        st.error("⚠️ Please configure your Dify API key in Settings")
        yield "API key not configured."
        return
    
    url = f"{api_base_url}/chat-messages"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
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
                    
                    # Dify streaming responses are in SSE format: " {...}"
                    if line_str.startswith(" "):
                        json_str = line_str[6:]  # Remove " " prefix
                        
                        try:
                            data = json.loads(json_str)
                            
                            # Handle different event types
                            event = data.get("event", "")
                            
                            if event == "message":
                                # Regular message chunk
                                answer = data.get("answer", "")
                                if answer:
                                    yield answer
                            
                            elif event == "message_end":
                                # Final message with conversation_id
                                conversation_id = data.get("conversation_id", "")
                                if conversation_id and not st.session_state.conversation_id:
                                    st.session_state.conversation_id = conversation_id
                            
                            elif event == "error":
                                # Error occurred
                                st.error(f"Error: {data.get('message', 'Unknown error')}")
                                break
                        
                        except json.JSONDecodeError:
                            continue
    
    except requests.exceptions.RequestException as e:
        st.error(f"Error communicating with Dify API: {str(e)}")
        yield "Sorry, I encountered an error. Please try again."


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
    
    # Initialize session state
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
                help="Enter your Dify API key"
            )
            
            api_url_input = st.text_input(
                "API Base URL",
                value=st.session_state.api_base_url,
                help="Dify API base URL"
            )
            
            if st.button("💾 Save Configuration"):
                st.session_state.api_key = api_key_input
                st.session_state.api_base_url = api_url_input
                st.success("Configuration saved!")
                st.rerun()
        
        # Streaming mode toggle
        use_streaming = st.checkbox(
            "Enable Streaming Response",
            value=True,
            help="Stream responses for real-time display"
        )
        
        # Additional inputs (optional parameters for Dify)
        with st.expander("📝 Additional Inputs", expanded=False):
            st.info("Add custom input parameters to send with your queries")
            
            input_key = st.text_input("Input Key", placeholder="e.g., city")
            input_value = st.text_input("Input Value", placeholder="e.g., Hong Kong")
            
            if st.button("➕ Add Input") and input_key and input_value:
                st.session_state.custom_inputs[input_key] = input_value
                st.success(f"Added: {input_key} = {input_value}")
            
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
        
        # Clear conversation button
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            clear_conversation()
    
    # Main content
    st.title("🤖 Dify AI Chatbot")
    st.caption("Powered by Dify API and Streamlit")
    
    # Warning if API key not configured
    if not st.session_state.api_key:
        st.warning("⚠️ Please configure your Dify API key in the sidebar Settings to start chatting.")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Enter your question here..."):
        
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
                
                for chunk in chat_with_dify_streaming(
                    query=prompt,
                    user_id=st.session_state.user_id,
                    conversation_id=st.session_state.conversation_id,
                    inputs=custom_inputs
                ):
                    full_response += chunk
                    message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                
            else:
                # Blocking response
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
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": full_response})


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    main()
