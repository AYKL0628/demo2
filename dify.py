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
        st.session_state.debug_mode = True  # Enable debug by default
    
    if "app_type" not in st.session_state:
        st.session_state.app_type = "chatbot"


def chatbot_streaming(
    query: str,
    user_id: str,
    conversation_id: str = "",
    inputs: Optional[dict] = None
) -> Generator[str, None, None]:
    """Send streaming chat request - ENHANCED DEBUGGING VERSION."""
    
    st.write("🔄 Starting chatbot request...")
    
    if not st.session_state.api_key:
        st.error("⚠️ No API key!")
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
    
    st.write("**📤 Request Info:**")
    st.write(f"- URL: `{url}`")
    st.write(f"- User ID: `{user_id[:16]}...`")
    st.write("**Payload:**")
    st.json(payload)
    
    event_count = 0
    received_data = []
    
    try:
        st.write("🔌 Connecting to Dify API...")
        
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=60) as response:
            
            st.write(f"**📥 Response Status:** `{response.status_code}`")
            st.write(f"**📥 Response Headers:** `{dict(response.headers)}`")
            
            if response.status_code != 200:
                error_text = response.text
                st.error(f"❌ HTTP {response.status_code}")
                st.code(error_text)
                
                try:
                    error_json = json.loads(error_text)
                    st.json(error_json)
                except:
                    pass
                
                yield f"Error {response.status_code}: {error_text}"
                return
            
            st.write("✅ Connection successful! Receiving stream...")
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    event_count += 1
                    
                    st.write(f"**Event {event_count}:** `{line_str[:100]}...`")
                    received_data.append(line_str)
                    
                    if not line_str.strip():
                        continue
                    
                    if line_str.startswith(" "):
                        json_str = line_str[6:]
                        
                        try:
                            data = json.loads(json_str)
                            event = data.get("event", "")
                            
                            st.write(f"  └─ **Event Type:** `{event}`")
                            
                            if event in ["message", "agent_message"]:
                                answer = data.get("answer", "")
                                st.write(f"  └─ **Answer chunk:** `{answer[:50]}...`")
                                if answer:
                                    yield answer
                            
                            elif event == "message_end":
                                conv_id = data.get("conversation_id", "")
                                st.write(f"  └─ **Conversation ID:** `{conv_id}`")
                                if conv_id:
                                    st.session_state.conversation_id = conv_id
                            
                            elif event == "error":
                                error_msg = data.get("message", "Unknown error")
                                st.error(f"❌ Dify Error: {error_msg}")
                                yield f"\n\nError: {error_msg}"
                                break
                            
                            # Show full data for first few events
                            if event_count <= 5:
                                with st.expander(f"Full Data for Event {event_count}"):
                                    st.json(data)
                        
                        except json.JSONDecodeError as e:
                            st.warning(f"⚠️ JSON decode error: {str(e)}")
                            st.code(json_str[:200])
                            continue
            
            st.write(f"**📊 Total events received:** {event_count}")
            
            if event_count == 0:
                st.error("❌ No events received from stream!")
                st.write("**This could mean:**")
                st.write("1. The app has no response configured")
                st.write("2. The LLM model is not set up")
                st.write("3. The app is not published")
                yield "No response received from Dify. Check your app configuration."
    
    except requests.exceptions.Timeout:
        st.error("❌ Request timed out after 60 seconds")
        yield "Request timed out."
    
    except requests.exceptions.ConnectionError as e:
        st.error(f"❌ Connection error: {str(e)}")
        yield f"Connection error: {str(e)}"
    
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        yield f"Error: {str(e)}"


def chatbot_blocking(
    query: str,
    user_id: str,
    conversation_id: str = "",
    inputs: Optional[dict] = None
) -> dict:
    """Send blocking chat request - ENHANCED DEBUGGING VERSION."""
    
    st.write("🔄 Starting blocking chatbot request...")
    
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
    
    st.write("**📤 Request:**")
    st.json(payload)
    
    try:
        st.write("🔌 Sending request...")
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        st.write(f"**📥 Status:** `{response.status_code}`")
        st.write("**📥 Response Text:**")
        st.code(response.text[:2000])
        
        if response.status_code == 200:
            result = response.json()
            
            st.write("**✅ Success! Full Response:**")
            st.json(result)
            
            answer = result.get("answer", "")
            
            if not answer:
                st.warning("⚠️ Response has no 'answer' field!")
                st.write("**Available fields:**", list(result.keys()))
            
            if "conversation_id" in result:
                st.session_state.conversation_id = result["conversation_id"]
            
            return {"answer": answer or "No answer in response.", "raw": result}
        
        else:
            st.error(f"❌ HTTP {response.status_code}")
            return {"answer": f"Error {response.status_code}: {response.text}", "error": True}
    
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
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
        page_title="Dify AI Assistant - DEBUG MODE",
        page_icon="🐛",
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
        
        # Verify API key format
        if st.session_state.api_key:
            if st.session_state.api_key.startswith("app-"):
                st.success("✅ API key format looks correct")
            else:
                st.error("⚠️ API key should start with 'app-'")
        
        # Debug mode (always on for now)
        st.info("🐛 Debug mode is ON - You'll see detailed logs")
        
        # Streaming toggle
        use_streaming = st.checkbox("📡 Use Streaming", value=False, help="Uncheck to use blocking mode for simpler debugging")
        
        st.divider()
        
        st.caption(f"User ID: `{st.session_state.user_id[:16]}...`")
        if st.session_state.conversation_id:
            st.caption(f"Conversation: `{st.session_state.conversation_id[:16]}...`")
        
        if st.button("🗑️ Clear Chat"):
            clear_conversation()
    
    # Main content
    st.title("🐛 Dify Chatbot - DEBUG MODE")
    st.caption("Enhanced debugging to find the issue")
    
    if not st.session_state.api_key:
        st.error("⚠️ No API key configured! Add it in the sidebar.")
        return
    
    # Display messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Type your message..."):
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            
            with st.expander("🔍 Debug Output", expanded=True):
                
                if use_streaming:
                    st.write("### Streaming Mode")
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
                    st.write("### Blocking Mode")
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
