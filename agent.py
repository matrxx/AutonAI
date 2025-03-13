from flask import Flask, render_template, request, jsonify, send_file
import mimetypes
from flask_cors import CORS
import os
import json
import time
import uuid
import threading
import queue
from datetime import datetime
from typing import List, Dict, Any
import requests
import re
import PyPDF2
import docx
from io import BytesIO

# Initialize Flask app
app = Flask(__name__)
CORS(app, origins="*", allow_headers=["Content-Type"], methods=["GET", "POST", "OPTIONS"])
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Global variables for the task system
task_queue = queue.Queue()
agent_updates = []
shared_memory = []
document_context = ""
system_running = False
project_status = {
    "description": "",
    "tasks": [],
    "progress": 0,
    "start_time": None,
    "last_update": None
}

class Tool:
    """A tool that the agent can use to interact with the world"""
    
    def __init__(self, name: str, description: str, func):
        self.name = name
        self.description = description
        self.func = func
        
    def run(self, input_str: str) -> str:
        """Execute the tool's function with the given input"""
        return self.func(input_str)
    
    def __str__(self) -> str:
        return f"{self.name}: {self.description}"

class Task:
    """Represents a task that can be assigned to an agent"""
    
    def __init__(self, description, agent_type=None, priority=1, dependencies=None):
        self.id = str(uuid.uuid4())[:8]  # Short unique ID
        self.description = description
        self.agent_type = agent_type
        self.priority = priority  # 1 = highest, 5 = lowest
        self.dependencies = dependencies or []
        self.status = "pending"  # pending, in_progress, completed, blocked
        self.created_at = datetime.now()
        self.updated_at = self.created_at
        self.completed_at = None
        self.result = None
        self.notes = []
        
    def update_status(self, status, note=None):
        self.status = status
        self.updated_at = datetime.now()
        if note:
            self.add_note(note)
        if status == "completed":
            self.completed_at = datetime.now()
    
    def add_note(self, note):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.notes.append({"timestamp": timestamp, "note": note})
    
    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "agent_type": self.agent_type,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completed_at": self.completed_at.strftime("%Y-%m-%d %H:%M:%S") if self.completed_at else None,
            "result": self.result,
            "notes": self.notes,
            "dependencies": self.dependencies
        }

class DocumentProcessor:
    """Process various document types"""
    
    @staticmethod
    def extract_text_from_pdf(file_data):
        """Extract text from PDF file"""
        pdf_reader = PyPDF2.PdfReader(BytesIO(file_data))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    
    @staticmethod
    def extract_text_from_docx(file_data):
        """Extract text from DOCX file"""
        doc = docx.Document(BytesIO(file_data))
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text
    
    @staticmethod
    def extract_text_from_txt(file_data):
        """Extract text from TXT file"""
        return file_data.decode('utf-8')
    
    @staticmethod
    def process_document(file_data, file_type):
        """Process document based on file type"""
        if file_type.lower().endswith('.pdf'):
            return DocumentProcessor.extract_text_from_pdf(file_data)
        elif file_type.lower().endswith('.docx'):
            return DocumentProcessor.extract_text_from_docx(file_data)
        elif file_type.lower().endswith('.txt'):
            return DocumentProcessor.extract_text_from_txt(file_data)
        else:
            return "Unsupported file format"

# Define the versatile agent types that can handle any domain
AGENT_TYPES = {
    "Agent1": {
        "role": "Versatile Agent 1",
        "skills": ["planning", "coding", "design", "data analysis", "content creation"],
        "system_prompt": """You are a versatile AI agent capable of handling any task across multiple domains including:
- Software development (frontend, backend, full-stack)
- Data analysis and visualization
- Machine learning and AI
- Content creation and copywriting
- Business analysis and planning
- Design and creative work
- Research and information gathering

You are not limited to any specific role or domain. When assigned a task, approach it with your full capabilities.

Your response should include:
1. A brief analysis of the task and what it requires
2. A complete solution with all necessary code, content, or designs
3. Any explanations needed to understand your solution

IMPORTANT: You will provide complete solutions directly in your response. For code, use appropriate 
code blocks with language identifiers. Only use explicitly available tools if needed. Otherwise, provide 
solutions directly without trying to use unavailable tools."""
    },
    "Agent2": {
        "role": "Versatile Agent 2",
        "skills": ["planning", "coding", "design", "data analysis", "content creation"],
        "system_prompt": """You are a versatile AI agent capable of handling any task across multiple domains including:
- Software development (frontend, backend, full-stack)
- Data analysis and visualization
- Machine learning and AI
- Content creation and copywriting
- Business analysis and planning
- Design and creative work
- Research and information gathering

You are not limited to any specific role or domain. When assigned a task, approach it with your full capabilities.

Your response should include:
1. A brief analysis of the task and what it requires
2. A complete solution with all necessary code, content, or designs
3. Any explanations needed to understand your solution

IMPORTANT: You will provide complete solutions directly in your response. For code, use appropriate 
code blocks with language identifiers. Only use explicitly available tools if needed. Otherwise, provide 
solutions directly without trying to use unavailable tools."""
    },
    "Agent3": {
        "role": "Versatile Agent 3",
        "skills": ["planning", "coding", "design", "data analysis", "content creation"],
        "system_prompt": """You are a versatile AI agent capable of handling any task across multiple domains including:
- Software development (frontend, backend, full-stack)
- Data analysis and visualization
- Machine learning and AI
- Content creation and copywriting
- Business analysis and planning
- Design and creative work
- Research and information gathering

You are not limited to any specific role or domain. When assigned a task, approach it with your full capabilities.

Your response should include:
1. A brief analysis of the task and what it requires
2. A complete solution with all necessary code, content, or designs
3. Any explanations needed to understand your solution

IMPORTANT: You will provide complete solutions directly in your response. For code, use appropriate 
code blocks with language identifiers. Only use explicitly available tools if needed. Otherwise, provide 
solutions directly without trying to use unavailable tools."""
    },
    "Agent4": {
        "role": "Versatile Agent 4",
        "skills": ["planning", "coding", "design", "data analysis", "content creation"],
        "system_prompt": """You are a versatile AI agent capable of handling any task across multiple domains including:
- Software development (frontend, backend, full-stack)
- Data analysis and visualization
- Machine learning and AI
- Content creation and copywriting
- Business analysis and planning
- Design and creative work
- Research and information gathering

You are not limited to any specific role or domain. When assigned a task, approach it with your full capabilities.

Your response should include:
1. A brief analysis of the task and what it requires
2. A complete solution with all necessary code, content, or designs
3. Any explanations needed to understand your solution

IMPORTANT: You will provide complete solutions directly in your response. For code, use appropriate 
code blocks with language identifiers. Only use explicitly available tools if needed. Otherwise, provide 
solutions directly without trying to use unavailable tools."""
    }
}

# Define agent tools
def search_web(query: str) -> str:
    """Simulate a web search tool (in a real implementation, use an actual search API)"""
    return f"Search results for '{query}' would appear here"

def get_weather(location: str) -> str:
    """Simulate a weather checking tool"""
    return f"The weather in {location} is currently sunny and 72°F"

def calculate(expression: str) -> str:
    """A simple calculator tool"""
    try:
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error in calculation: {str(e)}"

def summarize_text(text: str) -> str:
    """Tool to summarize text (in a real implementation, use an LLM for this)"""
    return f"Summary of text ({len(text)} characters): This is a placeholder for text summarization."

# Common tools available to all agents
COMMON_TOOLS = {
    "search": Tool("search", "Search the web for information", search_web),
    "calculate": Tool("calculate", "Perform mathematical calculations", calculate),
}

# Agent-specific tools
AGENT_TOOLS = {
    "ContentWriter": {
        "summarize": Tool("summarize", "Summarize long text", summarize_text),
    },
    # Add other agent-specific tools as needed
}

def call_llm(messages, model="llama2:13b", timeout=300, max_retries=2):
    """Call the local Ollama API with extended timeout and better error handling"""
    # Format the messages for Ollama
    prompt = ""
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            prompt += f"<s>[INST] <<SYS>>\n{content}\n<</SYS>>\n\n"
        elif role == "user":
            if not prompt:  # First message
                prompt += f"<s>[INST] {content} [/INST]"
            else:  # Not the first message
                prompt += f"[INST] {content} [/INST]"
        elif role in ["assistant", "agent"]:
            prompt += f" {content} </s>"
    
    # Call the Ollama API with retries
    for attempt in range(max_retries):
        try:
            response = requests.post('http://localhost:11434/api/generate',
                            json={
                                'model': model,
                                'prompt': prompt,
                                'stream': False
                            }, timeout=timeout)  # Increased timeout
            
            if response.status_code == 200:
                return response.json()['response']
            else:
                print(f"Error calling Ollama API (attempt {attempt+1}): {response.status_code} - {response.text}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retry
        except Exception as e:
            print(f"Exception when calling Ollama (attempt {attempt+1}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retry
    
    # If all retries failed, return a simple error message
    return "I was unable to process this task due to a connection issue. Please try a different approach or provide a different task description."

def parse_llm_response(response: str, expecting_json=False):
    """Parse the LLM response for actions or JSON content with better resilience"""
    # Check for tool usage with more flexible pattern matching
    action_patterns = [
        r"ACTION:\s*(\w+)[\s\n]*INPUT:\s*([\s\S]+?)(?=\n\n|$)",  # Standard format
        r"I'll use the (\w+) tool[\s\n]*Input:\s*([\s\S]+?)(?=\n\n|$)",  # Conversational format
        r"I need to use the (\w+) tool[\s\n]*with input:[\s\n]*([\s\S]+?)(?=\n\n|$)"  # Another variant
    ]
    
    for pattern in action_patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return {
                "type": "action",
                "tool": match.group(1).strip(),
                "input": match.group(2).strip()
            }
    
    # Check if we're expecting JSON
    if expecting_json:
        try:
            # Look for JSON in the response (within code blocks or directly)
            json_pattern = r'```(?:json)?\s*(\[.*\]|\{.*\})\s*```'
            json_match = re.search(json_pattern, response, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                return {
                    "type": "json",
                    "content": json.loads(json_str)
                }
            
            # Try to find JSON without code blocks
            json_pattern = r'(\[.*\]|\{.*\})'
            json_match = re.search(json_pattern, response, re.DOTALL)
            
            if json_match:
                # Try to parse as JSON
                try:
                    json_str = json_match.group(1)
                    return {
                        "type": "json",
                        "content": json.loads(json_str)
                    }
                except:
                    pass
        except:
            pass
    
    # Default to treating as plain text
    return {
        "type": "text",
        "content": response
    }

def get_agent_prompt(agent_type, task_description):
    """Get a prompt for a specific agent type and task"""
    base_prompt = AGENT_TYPES[agent_type]["system_prompt"]
    
    prompt = f"""{base_prompt}

Your current task is: {task_description}

When you need to perform an action, use one of the available tools by responding in this exact format:
ACTION: tool_name
INPUT: input for the tool

You can also provide your results in a structured format using JSON when appropriate.

Project Context:
{project_status["description"]}

"""
    
    # Add document context if available
    global document_context
    if document_context:
        prompt += f"\nDocument Context:\n{document_context}\n"
    
    # Add related task information
    related_tasks = [t for t in project_status["tasks"] 
                    if t["agent_type"] != agent_type and t["status"] == "completed"]
    if related_tasks:
        prompt += "\nCompleted tasks from other team members:\n"
        for task in related_tasks[-3:]:  # Only show the last 3 to avoid context overflow
            prompt += f"- {task['description']} (by {task['agent_type']})\n"
            if task['result']:
                prompt += f"  Result: {task['result'][:200]}...\n"
    
    return prompt

# Create a directory to store agent outputs
OUTPUT_DIR = 'agent_outputs'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Improved file saving function for agent.py

def save_output_file(agent_type, file_name, content, file_type='text'):
    """Save agent output as a file, extracting code blocks if needed"""
    # Create agent-specific folder if it doesn't exist
    agent_dir = os.path.join(OUTPUT_DIR, agent_type)
    if not os.path.exists(agent_dir):
        os.makedirs(agent_dir)
    
    # Sanitize file name
    safe_name = "".join([c for c in file_name if c.isalnum() or c in "._-"]).strip()
    if not safe_name:
        safe_name = "output"
    
    # Add timestamp to prevent overwriting
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Determine file extension based on content and type
    extension = ".txt"  # Default
    
    # Try to extract code blocks from the content
    extracted_content = extract_code_from_response(content, file_type)
    
    # Set proper extension based on file_type
    if file_type == 'html':
        extension = ".html"
    elif file_type == 'css':
        extension = ".css"
    elif file_type == 'js':
        extension = ".js"
    elif file_type == 'json':
        extension = ".json"
    
    # Create full file name with timestamp and extension
    full_name = f"{timestamp}_{safe_name}{extension}"
    file_path = os.path.join(agent_dir, full_name)
    
    # Write content to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(extracted_content)
    
    return {
        'path': file_path,
        'name': os.path.basename(file_path),
        'agent': agent_type,
        'timestamp': timestamp,
        'size': len(extracted_content),
        'type': extension[1:]  # Remove the dot
    }

def extract_code_from_response(content, file_type):
    """
    Extract actual code from an agent response, removing markdown and error messages
    """
    # Check if this is an error message
    if "Error connecting to Ollama" in content:
        return "// The agent was unable to generate content due to connection issues."
    
    # Try to extract code blocks with the appropriate language tag
    code_block_pattern = None
    
    if file_type == 'html':
        code_block_pattern = r'```(?:html)?\s*([\s\S]+?)\s*```'
    elif file_type == 'css':
        code_block_pattern = r'```(?:css)?\s*([\s\S]+?)\s*```'
    elif file_type == 'js':
        code_block_pattern = r'```(?:javascript|js)?\s*([\s\S]+?)\s*```'
    elif file_type == 'json':
        code_block_pattern = r'```(?:json)?\s*([\s\S]+?)\s*```'
    
    # If we have a pattern, try to extract code
    if code_block_pattern:
        matches = re.findall(code_block_pattern, content, re.IGNORECASE)
        if matches:
            # Return the first matching code block
            return matches[0]
    
    # If no specific code block found, try to extract any code block
    generic_code_block = re.findall(r'```(?:\w+)?\s*([\s\S]+?)\s*```', content)
    if generic_code_block:
        return generic_code_block[0]
    
    # If no code blocks found, check if the content might be direct code
    if file_type == 'html' and content.strip().startswith('<') and ('</html>' in content or '</body>' in content):
        return content
    elif file_type == 'css' and '{' in content and '}' in content:
        return content
    elif file_type == 'js' and ('function' in content or 'const ' in content or 'let ' in content):
        return content
    
    # Default case, just return the content
    return content

def process_task(task):
    """Process a single task with better error handling and file extraction"""
    agent_type = task.agent_type
    if not agent_type:
        log_update("System", f"No agent type specified for task: {task.description}. Defaulting to Agent1.")
        agent_type = "Agent1"
    
    # Get appropriate prompt for this agent and task
    system_prompt = get_agent_prompt(agent_type, task.description)
    
    # Add direct instructions to avoid tool usage
    system_prompt += """
IMPORTANT: Please provide your complete solution directly in your response. 
Do not try to use specialized tools or actions. Include any code directly using 
markdown code blocks with appropriate language tags.
"""
    
    # Create context for the LLM
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Complete this task: {task.description}"}
    ]
    
    # Update task status
    task.update_status("in_progress", f"Task started by {agent_type}")
    log_update(agent_type, f"Working on: {task.description}")
    
    # Call the LLM with increased timeout
    response = call_llm(messages, timeout=300)
    
    # Store the result
    task.result = response
    
    # Mark task as completed
    task.update_status("completed", f"Task completed by {agent_type}")
    log_update(agent_type, f"Completed task: {task.description}")
    
    # Save relevant output files based on task description
    if task.result:
        # Detect file types from task description
        desc_lower = task.description.lower()
        
        # First save the full response as text
        file_info = save_output_file(agent_type, f"{task.description[:30]}_full", task.result, 'text')
        log_update(agent_type, f"Full response saved as: {file_info['name']}")
        
        # Now extract and save specific files based on content detected in description
        if 'html' in desc_lower or 'webpage' in desc_lower or 'website' in desc_lower:
            html_info = save_output_file(agent_type, f"{task.description[:30]}_html", task.result, 'html')
            log_update(agent_type, f"HTML content saved as: {html_info['name']}")
            
        if 'css' in desc_lower or 'style' in desc_lower:
            css_info = save_output_file(agent_type, f"{task.description[:30]}_css", task.result, 'css')
            log_update(agent_type, f"CSS content saved as: {css_info['name']}")
            
        if 'javascript' in desc_lower or 'js' in desc_lower:
            js_info = save_output_file(agent_type, f"{task.description[:30]}_js", task.result, 'js')
            log_update(agent_type, f"JavaScript content saved as: {js_info['name']}")
        
        # Store file info on the task
        task.file_info = file_info
    
    # Return the result
    return task.result

def create_project_plan(description):
    """Create an initial project plan with proper agent type validation"""
    global project_status
    
    # Reset project status
    project_status = {
        "description": description,
        "tasks": [],
        "progress": 0,
        "start_time": datetime.now(),
        "last_update": datetime.now()
    }
    
    # Create a prompt for the project manager
    system_prompt = AGENT_TYPES["Agent1"]["system_prompt"]
    prompt = f"""
{system_prompt}

You need to create a detailed project plan for the following project:

{description}

Break down this project into specific tasks that can be assigned to our team of specialists:
- Agent1 (you): Planning, coordination, delegation
- Agent2: Implementation, development
- Agent3: Design, creative work
- Agent4: Testing, validation

For each task, specify:
1. A clear, specific description
2. The agent type who should handle it (Agent1, Agent2, Agent3, or Agent4 only)
3. Priority (1-5, where 1 is highest)
4. Any dependencies (task IDs that must be completed first)

Respond with a JSON array of tasks, where each task has the fields: description, agent_type, priority.
"""
    
    # Call the LLM with an increased timeout
    response = call_llm([{"role": "system", "content": prompt}], timeout=300)
    
    # Parse the response to extract tasks
    parsed = parse_llm_response(response, expecting_json=True)
    
    tasks = []
    if parsed["type"] == "json" and isinstance(parsed["content"], list):
        # Successfully parsed JSON list of tasks
        task_list = parsed["content"]
        for task_data in task_list:
            # Get agent type with validation
            agent_type = task_data.get("agent_type", "Agent1")
            # Ensure it's a valid agent type
            if agent_type not in AGENT_TYPES:
                log_update("System", f"Invalid agent type: {agent_type}. Using Agent1 instead.")
                agent_type = "Agent1"
                
            task = Task(
                description=task_data.get("description", "Undefined task"),
                agent_type=agent_type,
                priority=task_data.get("priority", 3),
                dependencies=task_data.get("dependencies", [])
            )
            tasks.append(task)
    else:
        # Fallback: manual parsing
        lines = response.split("\n")
        current_task = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for task indicators
            if line.startswith("-") or line.startswith("*") or line.startswith("Task"):
                # Try to extract agent type
                agent_match = re.search(r'(Agent1|Agent2|Agent3|Agent4)', line)
                agent_type = agent_match.group(1) if agent_match else "Agent1"
                
                # Create a new task
                description = re.sub(r'^\s*[-*]\s*', '', line)
                description = re.sub(r'\(.*?\)', '', description).strip()
                
                task = Task(description=description, agent_type=agent_type)
                tasks.append(task)
    
    # If we still have no tasks, create a generic one
    if not tasks:
        task = Task(description=f"Implement project: {description}", agent_type="Agent1")
        tasks.append(task)
    
    # Sort tasks by priority
    tasks.sort(key=lambda t: getattr(t, 'priority', 3))
    
    # Update project status
    for task in tasks:
        project_status["tasks"].append(task.to_dict())
    
    # Log the plan creation
    log_update("Agent1", f"Created project plan with {len(tasks)} tasks")
    for task in tasks:
        log_update("Agent1", f"Task: {task.description} (Assigned to: {task.agent_type})")
    
    return tasks

# Update the initial UI message
def initializeUI():
    # Display welcome message
    appendMessage('system', 'Multi-Agent System initialized. The following versatile agents are ready to assist you:\n' +
        '- Agent1: Versatile coordinator capable of handling any task\n' +
        '- Agent2: Versatile agent capable of handling any task\n' +
        '- Agent3: Versatile agent capable of handling any task\n' +
        '- Agent4: Versatile agent capable of handling any task\n\n' +
        'To start a project, type "start project: [your project description]"')

def log_update(agent, message):
    """Log an update from an agent to the shared memory"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update = {
        "timestamp": timestamp,
        "agent": agent,
        "message": message
    }
    agent_updates.append(update)
    print(f"[{timestamp}] [{agent}] {message}")

def get_next_task():
    """Get the next task to be processed with proper agent type validation"""
    pending_tasks = []
    
    for t in project_status["tasks"]:
        if t["status"] == "pending":
            # Create a task with only the basic required fields
            task = Task(
                description=t["description"],
                agent_type=t.get("agent_type"),
                priority=t.get("priority", 3)
            )
            
            # Validate agent type
            if not task.agent_type or task.agent_type not in AGENT_TYPES:
                # Set a default agent type (Agent1)
                task.agent_type = "Agent1"
                log_update("System", f"Invalid agent type detected. Setting to Agent1 for task: {task.description[:50]}...")
            
            # Set the ID to match the stored task
            task.id = t["id"]
            
            # Set dependencies if they exist
            if "dependencies" in t:
                task.dependencies = t["dependencies"]
                
            pending_tasks.append(task)
    
    # If no tasks are pending, return None
    if not pending_tasks:
        return None
    
    # Sort by priority (lowest number = highest priority)
    pending_tasks.sort(key=lambda t: t.priority)
    
    # Find the first task with no unmet dependencies
    for task in pending_tasks:
        dependencies_met = True
        
        # Check if all dependencies are completed
        if task.dependencies:
            for dep_id in task.dependencies:
                dep_completed = False
                for t in project_status["tasks"]:
                    if t["id"] == dep_id and t["status"] == "completed":
                        dep_completed = True
                        break
                
                if not dep_completed:
                    dependencies_met = False
                    break
        
        if dependencies_met:
            return task
    
    # If no tasks have all dependencies met, return the highest priority task
    return pending_tasks[0]

def update_project_progress():
    """Update the project progress percentage"""
    total_tasks = len(project_status["tasks"])
    if total_tasks == 0:
        project_status["progress"] = 0
        return
    
    completed_tasks = sum(1 for t in project_status["tasks"] if t["status"] == "completed")
    project_status["progress"] = int((completed_tasks / total_tasks) * 100)
    project_status["last_update"] = datetime.now()

# Add this to your worker_thread function to catch and handle errors better

def worker_thread():
    """Background worker thread that processes tasks with better error handling"""
    global system_running
    
    while system_running:
        try:
            # If there are no tasks in the queue, check if we need to get a new one
            if task_queue.empty():
                next_task = get_next_task()
                if next_task:
                    task_queue.put(next_task)
            
            # Try to get a task with a 5-second timeout
            try:
                task = task_queue.get(timeout=5)
                
                # Verify the agent type exists before processing
                if not task.agent_type or task.agent_type not in AGENT_TYPES:
                    log_update("System", f"Invalid agent type: {task.agent_type}. Using Agent1 instead.")
                    task.agent_type = "Agent1"  # Default to Agent1
                
                # Process the task
                process_task(task)
                
                # Update the corresponding task in project_status
                for i, t in enumerate(project_status["tasks"]):
                    if t["id"] == task.id:
                        project_status["tasks"][i] = task.to_dict()
                        break
                
                # Update project progress
                update_project_progress()
                
                # Mark task as done
                task_queue.task_done()
                
            except queue.Empty:
                # No tasks in queue, sleep briefly
                time.sleep(1)
                
        except Exception as e:
            # Get detailed error information
            import traceback
            error_details = traceback.format_exc()
            
            # Log the specific error with details
            log_update("System", f"Error in worker thread: {str(e)}")
            print(f"Detailed error: {error_details}")
            
            # Sleep longer after an error to avoid rapid error loops
            time.sleep(5)

# Flask routes
@app.route('/')
def home():
    return jsonify({"status": "Async Multi-Agent System is running"})

@app.route('/api/chat', methods=['POST'])
def chat():
    global system_running, project_status
    
    data = request.json
    user_message = data.get('message', '')
    
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Log the user message
    log_update("User", user_message)
    
    # Check for system commands
    if user_message.lower().startswith("start project:") or user_message.lower().startswith("create project:"):
        # Extract project description
        project_description = user_message.split(":", 1)[1].strip()
        
        # Stop any existing project
        system_running = False
        time.sleep(1)  # Give worker thread time to clean up
        
        # Create a new project plan
        tasks = create_project_plan(project_description)
        
        # Start the worker thread if not already running
        system_running = True
        worker = threading.Thread(target=worker_thread)
        worker.daemon = True
        worker.start()
        
        # Response for the user
        task_list = "\n".join([f"- {task.description} → {task.agent_type}" for task in tasks])
        response = f"""[ProjectManager] I've analyzed your project and created a plan with {len(tasks)} tasks:

{task_list}

The team is now working on these tasks. You can check progress by asking for a status update."""

    elif user_message.lower().startswith("stop") or user_message.lower() == "stop":
        # Stop the worker thread
        system_running = False
        response = "[System] Project has been stopped. All agents have ceased working."
    
    elif "status" in user_message.lower() or "progress" in user_message.lower():
        # Provide a status update
        update_project_progress()
        
        completed = sum(1 for t in project_status["tasks"] if t["status"] == "completed")
        in_progress = sum(1 for t in project_status["tasks"] if t["status"] == "in_progress")
        pending = sum(1 for t in project_status["tasks"] if t["status"] == "pending")
        total = len(project_status["tasks"])
        
        # Get the most recent updates from each agent
        recent_updates = {}
        for update in reversed(agent_updates[-20:]):  # Look through the last 20 updates
            agent = update["agent"]
            if agent not in recent_updates and agent != "User" and agent != "System":
                recent_updates[agent] = update
            if len(recent_updates) >= 4:  # We have updates from all 4 agent types
                break
        
        status_msg = f"""[ProjectManager] Project Status:
- Progress: {project_status["progress"]}% complete
- Tasks: {completed}/{total} completed, {in_progress} in progress, {pending} pending

Recent agent activities:
"""
        for agent, update in recent_updates.items():
            status_msg += f"- {agent}: {update['message']}\n"
        
        if in_progress > 0:
            status_msg += "\nCurrently working on:\n"
            for task in project_status["tasks"]:
                if task["status"] == "in_progress":
                    status_msg += f"- {task['description']} (Assigned to: {task['agent_type']})\n"
        
        response = status_msg
    
    elif any(agent in user_message.lower() for agent in ["projectmanager", "frontenddev", "backenddev", "contentwriter"]):
        # Direct question to a specific agent
        for agent_type in ["ProjectManager", "FrontendDev", "BackendDev", "ContentWriter"]:
            if agent_type.lower() in user_message.lower():
                # Create a prompt for this agent
                system_prompt = AGENT_TYPES[agent_type]["system_prompt"]
                prompt = f"""
{system_prompt}

Project Context:
{project_status["description"]}

The user is asking you directly: {user_message}

Respond as {agent_type} with your expertise. Focus on giving a helpful, informative response.
"""
                # Call the LLM
                agent_response = call_llm([{"role": "system", "content": prompt}])
                response = f"[{agent_type}] {agent_response}"
                break
    else:
        # General question or instruction - route to Project Manager
        system_prompt = AGENT_TYPES["ProjectManager"]["system_prompt"]
        prompt = f"""
{system_prompt}

Current Project Context:
{project_status["description"]}

The user says: {user_message}

Respond as the Project Manager. If this is a new instruction, explain how you'll integrate it into the project plan.
If it's a question, provide a helpful response based on the current project state.
"""
        # Call the LLM
        agent_response = call_llm([{"role": "system", "content": prompt}])
        response = f"[ProjectManager] {agent_response}"
    
    # Log the response
    log_update("System", response)
    
    return jsonify({
        'response': response,
        'updates': agent_updates[-10:],  # Return the last 10 updates
        'project_status': {
            'description': project_status["description"],
            'progress': project_status["progress"],
            'tasks_completed': sum(1 for t in project_status["tasks"] if t["status"] == "completed"),
            'tasks_total': len(project_status["tasks"])
        }
    })

@app.route('/api/upload', methods=['POST'])
def upload_file():
    global document_context
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    file_data = file.read()
    file_type = file.filename
    
    try:
        extracted_text = DocumentProcessor.process_document(file_data, file_type)
        
        # Truncate if too long
        max_length = 5000
        if len(extracted_text) > max_length:
            extracted_text = extracted_text[:max_length] + f"\n[Note: Document truncated from {len(extracted_text)} characters to {max_length} characters]"
        
        document_context = extracted_text
        log_update("System", f"Document uploaded: {file.filename} ({len(extracted_text)} characters)")
        
        return jsonify({
            'success': True,
            'message': f'Successfully processed {file.filename}',
            'textLength': len(extracted_text)
        })
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

@app.route('/api/clear', methods=['POST'])
def clear_conversation():
    global system_running, agent_updates, project_status, document_context
    
    # Stop the worker thread
    system_running = False
    time.sleep(1)  # Give worker thread time to clean up
    
    # Clear all data
    agent_updates = []
    document_context = ""
    project_status = {
        "description": "",
        "tasks": [],
        "progress": 0,
        "start_time": None,
        "last_update": None
    }
    
    log_update("System", "System has been reset. All progress has been cleared.")
    
    return jsonify({'success': True})

@app.route('/api/status', methods=['GET'])
def get_status():
    update_project_progress()
    
    return jsonify({
        'project': {
            'description': project_status["description"],
            'progress': project_status["progress"],
            'tasks_completed': sum(1 for t in project_status["tasks"] if t["status"] == "completed"),
            'tasks_total': len(project_status["tasks"]),
            'start_time': project_status["start_time"].strftime("%Y-%m-%d %H:%M:%S") if project_status["start_time"] else None,
            'last_update': project_status["last_update"].strftime("%Y-%m-%d %H:%M:%S") if project_status["last_update"] else None,
        },
        'tasks': project_status["tasks"],
        'updates': agent_updates[-20:],  # Return the last 20 updates
        'running': system_running
    })

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get the console logs for display in the web UI"""
    # Get the last 100 logs
    logs = agent_updates[-100:] if agent_updates else []
    
    return jsonify({
        'logs': logs,
        'total_logs': len(agent_updates)
    })
    
if __name__ == '__main__':
    print("Starting Asynchronous Multi-Agent System on http://127.0.0.1:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)

@app.route('/api/files', methods=['GET'])
def list_files():
    """List all output files created by agents"""
    files = []
    
    if os.path.exists(OUTPUT_DIR):
        for agent_type in os.listdir(OUTPUT_DIR):
            agent_dir = os.path.join(OUTPUT_DIR, agent_type)
            if os.path.isdir(agent_dir):
                for file_name in os.listdir(agent_dir):
                    file_path = os.path.join(agent_dir, file_name)
                    if os.path.isfile(file_path):
                        # Get the relative path for the frontend
                        rel_path = os.path.join(agent_type, file_name).replace('\\', '/')
                        
                        files.append({
                            'name': file_name,
                            'agent': agent_type,
                            'path': rel_path,
                            'size': os.path.getsize(file_path),
                            'timestamp': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S"),
                            'type': os.path.splitext(file_name)[1][1:]  # Get extension without dot
                        })
    
    # Sort by timestamp (newest first)
    files.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify({'files': files})

@app.route('/api/files/<path:file_path>', methods=['GET'])
def download_file(file_path):
    """Download a specific file"""
    # Sanitize the path to prevent directory traversal
    safe_path = os.path.normpath(file_path).lstrip('./\\')
    full_path = os.path.join(OUTPUT_DIR, safe_path)
    
    if os.path.exists(full_path) and os.path.isfile(full_path):
        # Get the correct MIME type
        content_type = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
        
        # Serve the file
        return send_file(full_path, mimetype=content_type, as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/debug', methods=['GET'])
def debug_endpoints():
    """Debug endpoint to list all registered routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': [method for method in rule.methods if method != 'OPTIONS' and method != 'HEAD'],
            'path': str(rule)
        })
    
    # Check if OUTPUT_DIR exists and is accessible
    output_dir_exists = os.path.exists(OUTPUT_DIR)
    output_dir_files = []
    if output_dir_exists:
        for root, dirs, files in os.walk(OUTPUT_DIR):
            for file in files:
                output_dir_files.append(os.path.join(root, file).replace('\\', '/'))
    
    return jsonify({
        'routes': routes,
        'output_dir_exists': output_dir_exists,
        'output_dir_files': output_dir_files
    })