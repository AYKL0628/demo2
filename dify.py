
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
        st.session_state.app_type = "workflow"


def workflow_run_streaming(
    query: str,
    user_id: str,
    inputs: Optional[dict] = None
) -> Generator[str, None, None]:
    """Send streaming workflow request - FIXED JSON formatting."""
    if not st.session_state.api_key:
        st.error("⚠️ Please configure your Dify API key")
        yield "API key not configured."
        return
    
    url = f"{st.session_state.api_base_url}/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    # FIXED: Properly structure the inputs dictionary
    workflow_inputs = {}
    if inputs:
        workflow_inputs.update(inputs)
    workflow_inputs["query"] = query
    
    # FIXED: Proper JSON structure with all commas
    payload = {
        "inputs": workflow_inputs,
        "response_mode": "streaming",
        "user": user_id
    }
    
    if st.session_state.debug_mode:
        st.write("**🔍 DEBUG - Request Payload:**")
        st.json(payload)  # This will show properly formatted JSON
    
    has_content = False
    debug_events = []
    
    try:
        # Send request with proper JSON serialization
        response = requests.post(
            url, 
            headers=headers, 
            json=payload,  # requests automatically serializes this correctly
            stream=True, 
            timeout=120
        )
        
        if st.session_state.debug_mode:
            st.write(f"**🔍 DEBUG - Status:** `{response.status_code}`")
        
        if response.status_code != 200:
            error_text = response.text
            st.error(f"❌ HTTP {response.status_code}")
            st.code(error_text)
            yield f"Error {response.status_code}: {error_text}"
            return
        
        # Process streaming response
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
                            if st.session_state.debug_mode:
                                node_title = data.get("data", {}).get("title", "Processing")
                                yield f"▶️ {node_title}...\n"
                        
                        elif event == "node_finished":
                            node_data = data.get("data", {})
                            outputs = node_data.get("outputs", {})
                            
                            text = (
                                outputs.get("text", "") or
                                outputs.get("output", "") or
                                outputs.get("result", "") or
                                outputs.get("answer", "")
                            )
                            
                            if text:
                                has_content = True
                                yield text
                        
                        elif event == "text_chunk" or event == "text":
                            text_data = data.get("data", {})
                            text = text_data.get("text", "") or text_data.get("delta", "")
                            if text:
                                has_content = True
                                yield text
                        
                        elif event == "workflow_finished":
                            if not has_content:
                                outputs = data.get("data", {}).get("outputs", {})
                                final_text = (
                                    outputs.get("text", "") or
                                    outputs.get("output", "") or
                                    outputs.get("result", "") or
                                    json.dumps(outputs, indent=2)
                                )
                                if final_text:
                                    has_content = True
                                    yield final_text
                        
                        elif event == "error":
                            error_msg = data.get("message", "Unknown error")
                            st.error(f"❌ Workflow error: {error_msg}")
                            yield f"\n\n**Error:** {error_msg}"
                            break
                    
                    except json.JSONDecodeError:
                        continue
        
        if not has_content:
            if st.session_state.debug_mode:
                with st.expander("🔍 All Events"):
                    for evt in debug_events[:30]:
                        st.code(evt)
            yield "No output received from workflow."
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Connection error: {str(e)}")
        yield f"Error: {str(e)}"


def workflow_run_blocking(
    query: str,
    user_id: str,
    inputs: Optional[dict] = None
) -> dict:
    """Send blocking workflow request - FIXED JSON formatting."""
    if not st.session_state.api_key:
        return {"answer": "API key not configured.", "error": True}
    
    url = f"{st.session_state.api_base_url}/workflows/run"
    
    headers = {
        "Authorization": f"Bearer {st.session_state.api_key}",
        "Content-Type": "application/json"
    }
    
    # FIXED: Properly structure inputs
    workflow_inputs = {}
    if inputs:
        workflow_inputs.update(inputs)
    workflow_inputs["query"] = query
    
    # FIXED: Proper JSON structure
    payload = {
        "inputs": workflow_inputs,
        "response_mode": "blocking",
        "user": user_id
    }
    
    if st.session_state.debug_mode:
        st.write("**🔍 DEBUG - Request Payload:**")
        st.json(payload)
    
    try:
        response = requests.post(
            url, 
            headers=headers, 
            json=payload,  # Properly serialized
            timeout=120
        )
        
        if st.session_state.debug_mode:
            st.write(f"**🔍 DEBUG - Status:** `{response.status_code}`")
        
        if response.status_code == 200:
            result = response.json()
            
            if st.session_state.debug_mode:
                st.write("**🔍 DEBUG - Response:**")
                st.json(result)
            
            data = result.get("data", {})
            outputs = data.get("outputs", {})
            
            answer = (
                outputs.get("text", "") or
                outputs.get("output", "") or
                outputs.get("result", "") or
                outputs.get("answer", "") or
                json.dumps(outputs, indent=2) if outputs else "No output."
            )
            
            return {"answer": answer, "raw": result}
        
        else:
            error_text = response.text
            st.error(f"❌ HTTP {response.status_code}")
            st.code(error_text)
            return {"answer": f"Error {response.status_code}: {error_text}", "error": True}
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error: {str(e)}")
        return {"answer": f"Error: {str(e)}", "error": True}


def clear_conversation():
    """Clear conversation."""
    st.session_state.messages = []
    st.rerun()


# ============================================================================
# Main UI
# ============================================================================

def main():
    """Main application."""
    
    st.set_page_config(
        page_title="Dify Workflow App",
        page_icon="⚙️",
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
        
        # Debug mode
        st.session_state.debug_mode = st.checkbox("🐛 Debug Mode", value=st.session_state.debug_mode)
        
        # Streaming
        use_streaming = st.checkbox("📡 Streaming", value=True)
        
        # Additional inputs
        with st.expander("📝 Additional Inputs"):
            st.info("Add custom workflow inputs (optional)")
            
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
    st.title("⚙️ Dify Workflow Assistant")
    st.caption("Powered by Dify Workflows API")
    
    if not st.session_state.api_key:
        st.warning("⚠️ Configure your API key in the sidebar")
    
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
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    main()
