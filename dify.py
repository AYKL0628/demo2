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
    
    # HARDCODED API KEY - Replace with your actual key
    if "api_key" not in st.session_state:
        st.session_state.api_key = "app-6dYJsjilYPeonNoDN3EKOazW"  # ← Put your key here
    
    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = "https://api.dify.ai/v1"
    
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False
    
    if "app_type" not in st.session_state:
        st.session_state.app_type = "chatbot"  # Or "workflow" if you use that
    
    if "current_page" not in st.session_state:
        st.session_state.current_page = "chat"



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
        st.write("**🔍 DEBUG - Request:**")
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
                    
                    if line_str.startswith("data: "):
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
            st.write("**🔍 DEBUG - Response:**")
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
        st.write("**🔍 DEBUG - Request:**")
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
                    
                    if line_str.startswith("data: "):
                        json_str = line_str[6:]
                        
                        try:
                            data = json.loads(json_str)
                            event = data.get("event", "")
                            
                            if event == "workflow_started":
                                if st.session_state.debug_mode:
                                    yield "⚙️ Workflow started...\n\n"
                            
                            elif event == "node_started":
                                if st.session_state.debug_mode:
                                    node_title = data.get("data", {}).get("title", "Processing")
                                    yield f"▶️ {node_title}...\n"
                            
                            elif event == "node_finished":
                                outputs = data.get("data", {}).get("outputs", {})
                                text = (
                                    outputs.get("text", "") or
                                    outputs.get("output", "") or
                                    outputs.get("result", "") or
                                    outputs.get("answer", "")
                                )
                                if text:
                                    has_content = True
                                    yield text
                            
                            elif event == "text_chunk":
                                text = data.get("data", {}).get("text", "")
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
                                        has_content = True
                                        yield text
                            
                            elif event == "error":
                                error_msg = data.get("message", "Unknown error")
                                st.error(f"❌ Error: {error_msg}")
                                break
                        
                        except json.JSONDecodeError:
                            continue
            
            if not has_content:
                yield "No output received from workflow."
    
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
                outputs.get("result", "") or
                json.dumps(outputs, indent=2)
            )
            
            return {"answer": answer, "raw": result}
        
        else:
            error_text = response.text
            st.error(f"❌ HTTP {response.status_code}: {error_text}")
            return {"answer": f"Error: {error_text}", "error": True}
    
    except requests.exceptions.RequestException as e:
        return {"answer": f"Error: {str(e)}", "error": True}


def clear_conversation():
    """Clear conversation."""
    st.session_state.messages = []
    st.session_state.conversation_id = ""
    st.rerun()


# ============================================================================
# FAQ Data - CUSTOMIZE THESE!
# ============================================================================

FAQ_DATA = [
    {
        "question": "When are the quizzes?",
        "answer": """The quizzes for the course CTDL1902 are scheduled as follows:

1. **Quiz 1**: 
   - Date: October 8
   - Available for:
     - Lecture 1 (L1): October 8
     - Lecture 2 (L2): October 8
     - Lecture 3 (L3): October 9
     - Lecture 4 (L4): October 9

2. **Quiz 2**: 
   - Contribution: 3%
   - Dates: 
     - Lecture 1 (L1): October 22
     - Lecture 2 (L2): October 22
     - Lecture 3 (L3): October 23
     - Lecture 4 (L4): October 23

3. **Quiz 3**: 
   - Contribution: 3%
   - Dates:
     - Lecture 1 (L1): November 12
     - Lecture 2 (L2): November 12
     - Lecture 3 (L3): November 13
     - Lecture 4 (L4): November 13

Additionally, there are **In-video Quizzes** that are ongoing throughout the course and are tied to the lecture videos. Be sure to watch the videos to access these quizzes."""
    },
    {
        "question": "What is RNN with attention?",
        "answer": """**Recurrent Neural Networks (RNNs) with Attention** are an advanced architecture used in deep learning, particularly for sequence-to-sequence tasks like language translation, text summarization, and speech recognition.

### Key Concepts:

1. **Recurrent Neural Networks (RNNs)**: 
   - RNNs are designed to process sequences of data by maintaining a hidden state that captures information from previous time steps. They are effective for tasks where context and order of data are important, such as time series analysis or natural language processing.

2. **Attention Mechanism**:
   - The attention mechanism allows the model to focus on specific parts of the input sequence when making predictions. Instead of relying solely on the last hidden state (as traditional RNNs do), attention weights are computed to determine the relevance of all previous states. This enables the model to weigh the importance of different inputs dynamically.

### How RNNs with Attention Work:

1. **Encoding**: The input sequence is processed by the RNN, generating a series of hidden states that encapsulate the information in the sequence.

2. **Attention Calculation**: For each output step, the model calculates attention scores for all hidden states from the input sequence. This involves:
   - Computing a score (often using dot product or a feed-forward network) that reflects how relevant each hidden state is to the current output.
   - Normalizing these scores using a softmax function to create attention weights.

3. **Context Vector**: The attention weights are then used to create a weighted sum of the hidden states, forming a context vector that highlights the most relevant parts of the input sequence for generating the current output.

4. **Decoding**: The context vector is combined with the current input (or previous output) to produce the next output in the sequence.

### Benefits of RNNs with Attention:

- **Improved Performance**: By focusing on the most relevant parts of the input, attention mechanisms enhance the model's ability to capture dependencies over long sequences.
- **Interpretability**: Attention weights provide insights into which parts of the input the model considers important for its predictions.
- **Flexibility**: This architecture can handle variable-length input sequences effectively.

In summary, RNNs with attention improve upon traditional RNNs by incorporating a mechanism that allows the model to dynamically focus on different parts of the input sequence, resulting in more accurate and interpretable outputs.
        
        """
    },
    {
        "question": "What are the requirements of the presentaion?",
        "answer": """The requirements for the group presentation in the CTDL1902 course are as follows:

1. **Content**:
   - Demonstrate a clear understanding of AI concepts and how they differ from human cognition.
   - Apply critical thinking to evaluate AI solutions and their implications.
   - Analyze AI's role in society using various theoretical frameworks, such as network theory, complexity theory, and ethical theories.

2. **Structure**:
   - Organize the presentation logically, covering key topics and findings in a coherent manner.
   - Include an introduction, main body, and conclusion.

3. **Duration**:
   - Adhere to the time limit specified by the instructor (typically around 10-15 minutes, but confirm with course guidelines).

4. **Visual Aids**:
   - Use slides or other visual aids to enhance understanding and engagement (ensure they are clear and not overly cluttered).

5. **Communication**:
   - Clearly articulate ideas, using appropriate academic language.
   - Engage the audience and encourage questions or discussions.

6. **Team Collaboration**:
   - Ensure that all group members contribute to the presentation, with clear division of roles and responsibilities.
   - Practice collectively to ensure smooth transitions and timing.

7. **Citations**:
   - Properly cite any sources or references used in the presentation to acknowledge contributions and uphold academic integrity.

8. **Feedback and Revisions**:
   - Be open to feedback during practice sessions and make necessary revisions to improve the presentation.

These requirements aim to ensure that the presentation is informative, engaging, and reflective of the group's understanding of the course material. Make sure to check any specific guidelines provided by your instructor for additional details or expectations."""
    },
    {
        "question": "Explain backwards propogation",
        "answer": """1) Define key concepts:
Backward propagation, or backpropagation, is a key algorithm used in training artificial neural networks. It involves calculating the gradient of the loss function with respect to each weight in the network by applying the chain rule of calculus. This process allows for the adjustment of weights in a way that reduces the error of the network's predictions.

2) Provide evidence from the database:
Backpropagation is described in the context of fixing weights for an entire network of perceptron neurons. It utilizes the chain rule to compute the slopes (gradients) of the loss function with respect to weights, which are then adjusted using gradient descent. This method is essential for training multilayer networks and is highlighted in the following source:

"Errors for the entire network can be written as one, single equation" and "Using math (i.e., the Chain Rule), calculate slopes for every w, then use gradient descent" (source: Towards Data Science article on neural networks).
3) Solve or answer logically:
The backpropagation process follows these steps:

Feed Forward: Input data is passed through the network to get predictions.
Calculate Loss: The difference between the predictions and the actual values is computed using a loss function.
Backpropagate Error: The algorithm calculates the gradient of the loss function with respect to the output of the network, and then uses the chain rule to propagate this error backward through the network layers, calculating gradients for each weight.
Update Weights: Each weight is adjusted in the direction that minimizes the loss, using an optimization technique like gradient descent.
4) Check for accuracy against known facts:
Backpropagation is a widely used method in machine learning and is considered accurate for training neural networks. It is supported by extensive theoretical and empirical research. The process described aligns with standard practices in deep learning, confirming its validity as an effective training mechanism."""
    },
    {
        "question": "Explain pros and cons of jobs after AI.",
        "answer": """The rise of artificial intelligence (AI) is transforming the job market across various sectors. While AI brings many benefits, it also poses challenges. Here’s an overview of the pros and cons of jobs in a post-AI world:

### Pros:

1. **Increased Efficiency**:
   - AI can automate repetitive and mundane tasks, allowing employees to focus on more strategic and creative aspects of their work. This can lead to higher productivity and job satisfaction.

2. **New Job Creation**:
   - While AI may replace some jobs, it also creates new ones. Roles in AI development, maintenance, ethical oversight, and data analysis are emerging, requiring a workforce skilled in technology.

3. **Enhanced Decision-Making**:
   - AI can analyze vast amounts of data quickly, providing insights that help professionals make informed decisions. This can improve outcomes in fields like healthcare, finance, and marketing.

4. **Flexibility and Remote Work**:
   - Many AI tools facilitate remote work and flexible schedules, allowing for a better work-life balance. This can lead to increased job satisfaction and attract a more diverse workforce.

5. **Skill Development**:
   - The demand for tech-savvy employees encourages continuous learning and skill development. Workers are motivated to upgrade their skills, fostering a culture of lifelong learning.

### Cons:

1. **Job Displacement**:
   - Certain jobs, particularly those involving routine tasks, may be automated, leading to unemployment for workers in those roles. This can disproportionately affect low-skilled workers and exacerbate income inequality.

2. **Skill Gap**:
   - As AI technologies advance, there may be a shortage of workers with the necessary skills to operate and manage these new systems. This skill gap can create barriers to employment for many individuals.

3. **Dependence on Technology**:
   - Increased reliance on AI can lead to a decrease in critical thinking and problem-solving skills. Employees may become overly dependent on technology, which can be problematic in situations where human judgment is essential.

4. **Ethical Concerns**:
   - The integration of AI into the workplace raises ethical issues, such as bias in algorithms, privacy concerns, and the potential for surveillance. These issues require careful management to ensure fair and equitable treatment of employees.

5. **Economic Disparities**:
   - The benefits of AI may not be evenly distributed across industries or regions, potentially leading to greater economic disparities. Some sectors may thrive while others struggle, creating a divide in job opportunities.

### Conclusion:

The impact of AI on jobs is complex, with both positive and negative implications. While AI has the potential to enhance productivity and create new opportunities, it also poses challenges that must be addressed to ensure a fair and equitable workforce. Adaptation through reskilling and a focus on ethical AI deployment will be crucial as we navigate this evolving landscape."""
    },
    {
        "question": "List potential risks of using AI",
        "answer": """Here are several potential risks associated with the use of artificial intelligence (AI):

1. **Bias and Discrimination**:
   - AI systems can inherit biases present in their training data, leading to discriminatory outcomes in areas such as hiring, lending, and law enforcement.

2. **Loss of Jobs**:
   - Automation of tasks performed by humans can result in job displacement, particularly for low-skilled workers, potentially leading to increased unemployment and economic inequality.

3. **Privacy Concerns**:
   - AI systems often require large amounts of personal data to function effectively, raising concerns about data privacy and the potential for misuse of sensitive information.

4. **Security Vulnerabilities**:
   - AI systems can be susceptible to hacking and adversarial attacks, where malicious actors manipulate AI inputs to produce incorrect or harmful outputs.

5. **Lack of Transparency**:
   - Many AI models, especially deep learning systems, function as "black boxes," making it difficult to understand how decisions are made, which can lead to a lack of accountability.

6. **Over-reliance on Technology**:
   - Excessive dependence on AI systems may erode critical thinking and problem-solving skills among humans, as they may defer to AI for decision-making.

7. **Ethical Concerns**:
   - The deployment of AI raises ethical questions, such as the morality of using AI in warfare, surveillance, and other sensitive contexts.

8. **Misinformation and Deepfakes**:
   - AI can be used to create convincing fake content (e.g., deepfakes), which can spread misinformation and manipulate public opinion.

9. **Job Polarization**:
   - AI may lead to job polarization, where high-skill, high-wage opportunities increase, while low-skill jobs decline, exacerbating economic divides.

10. **Environmental Impact**:
    - The computational power required for training large AI models can have significant energy requirements, leading to increased carbon footprints and environmental concerns.

11. **Societal Manipulation**:
    - AI algorithms may be used to manipulate people’s behavior through targeted advertising and social media, raising concerns about autonomy and free will.

12. **Regulatory Challenges**:
    - The rapid advancement of AI technologies can outpace existing legal and regulatory frameworks, leading to gaps in governance and oversight.

Addressing these risks requires proactive measures, including the development of ethical guidelines, robust regulatory frameworks, and ongoing dialogue among stakeholders to ensure responsible AI deployment."""
    }
]
        

# ============================================================================
# FAQ Page
# ============================================================================

def show_faq_page():
    """Display the FAQ page."""
    st.title("❓ Frequently Asked Questions")
    st.caption("Common questions about CTDL1902")
    
    # Back to Chat button
    if st.button("← Back to Chat", use_container_width=False):
        st.session_state.current_page = "chat"
        st.rerun()
    
    st.divider()
    
    # Search functionality
    search_query = st.text_input("🔍 Search FAQs", placeholder="Type to search...")
    
    st.divider()
    
    # Filter FAQs based on search
    filtered_faqs = FAQ_DATA
    if search_query:
        filtered_faqs = [
            faq for faq in FAQ_DATA
            if search_query.lower() in faq["question"].lower() or
               search_query.lower() in faq["answer"].lower()
        ]
    
    # Display FAQs
    if filtered_faqs:
        for i, faq in enumerate(filtered_faqs):
            with st.expander(f"**{faq['question']}**", expanded=(i == 0 and not search_query)):
                st.markdown(faq["answer"])
    else:
        st.info("No FAQs match your search. Try different keywords.")
    
    st.divider()
    
    # Additional help section
    st.subheader("💡 Still need help?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Contact Support:**
        - Email: support@example.com
        - Discord: [Join our server](#)
        """)
    
    with col2:
        st.markdown("""
        **Resources:**
        - [Dify Documentation](https://docs.dify.ai)
        - [GitHub Repository](#)
        """)


# ============================================================================
# Chat Page
# ============================================================================

def show_chat_page():
    """Display the main chat page."""
    
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Settings")
        
        # FAQ Board Button - HIGHLIGHTED
        if st.button("❓ FAQ Board", use_container_width=True, type="primary"):
            st.session_state.current_page = "faq"
            st.rerun()
        
        st.divider()
        
     
        
        
        # App Type Selection
        st.write("### 🎯 App Type")
        app_type = st.radio(
            "Select your Dify app type:",
            options=["chatbot", "workflow"],
            index=0 if st.session_state.app_type == "chatbot" else 1,
            help="Choose the type that matches your Dify app"
        )
        
        if app_type != st.session_state.app_type:
            st.session_state.app_type = app_type
            st.rerun()
        
        # Streaming mode
        use_streaming = st.checkbox(
            "📡 Enable Streaming",
            value=True,
            help="Stream responses in real-time"
        )
        
        # Debug mode (optional)
        st.session_state.debug_mode = st.checkbox(
            "🐛 Debug Mode",
            value=st.session_state.debug_mode,
            help="Show detailed request/response information"
        )
        
        # Additional inputs
        with st.expander("📝 Additional Inputs"):
            st.info("Add custom input parameters (optional)")
            
            col1, col2 = st.columns(2)
            with col1:
                input_key = st.text_input("Key", placeholder="e.g., language")
            with col2:
                input_value = st.text_input("Value", placeholder="e.g., English")
            
            if st.button("➕ Add Input") and input_key and input_value:
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
        
        # Conversation info
        st.divider()
        st.caption(f"**User ID:** `{st.session_state.user_id[:8]}...`")
        if st.session_state.app_type == "chatbot" and st.session_state.conversation_id:
            st.caption(f"**Conversation:** `{st.session_state.conversation_id[:8]}...`")
        
        # Clear conversation button
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            clear_conversation()
    
    # Main content
    app_icon = "💬" if st.session_state.app_type == "chatbot" else "⚙️"
    st.title(f"{app_icon} Dify AI Assistant")
    st.caption(f"{'Chatbot' if st.session_state.app_type == 'chatbot' else 'Workflow'} | Powered by Dify and Streamlit")
    
    if not st.session_state.api_key:
        st.warning("⚠️ Please configure your Dify API key in the sidebar to start chatting.")
        st.info("""
        **Quick Start:**
        1. Go to your Dify workspace
        2. Open your app → **Publish** tab
        3. Copy the **API Secret Key** (starts with `app-`)
        4. Paste it in the sidebar Settings
        5. Select the correct **App Type** (Chatbot or Workflow)
        
        💡 Need help? Check out the **FAQ Board** in the sidebar!
        """)
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Type your message here...", disabled=not st.session_state.api_key):
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Display assistant response
        with st.chat_message("assistant"):
            
            # Route to correct function based on app type
            if st.session_state.app_type == "chatbot":
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
            
            else:
                # Workflow mode
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
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": full_response})


# ============================================================================
# Main App Router
# ============================================================================

def main():
    """Main application with page routing."""
    
    st.set_page_config(
        page_title="Dify AI Assistant",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    initialize_session_state()
    
    # Route to appropriate page
    if st.session_state.current_page == "faq":
        show_faq_page()
    else:
        show_chat_page()


if __name__ == "__main__":
    main()
