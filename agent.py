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

# Define the agent types and their capabilities
AGENT_TYPES = {
    "ProjectManager": {
        "role": "Project Manager",
        "skills": ["planning", "coordination", "delegation", "evaluation"],
        "system_prompt": """You are a Project Manager AI assistant. Your responsibilities include:
1. Breaking down projects into manageable tasks
2. Assigning tasks to appropriate specialists
3. Tracking project progress
4. Coordinating between team members
5. Ensuring all requirements are met

When creating tasks, be specific about what needs to be done. Assign priorities (1-5, where 1 is highest) 
and identify the most suitable agent type for each task."""
    },
    "FrontendDev": {
        "role": "Frontend Developer",
        "skills": ["HTML", "CSS", "JavaScript", "UI design", "responsive design"],
        "system_prompt": """You are a Frontend Developer AI assistant. Your responsibilities include:
1. Creating user interfaces with HTML, CSS, and JavaScript
2. Implementing responsive designs that work on all devices
3. Developing interactive web components
4. Ensuring good user experience and accessibility
5. Working with the backend developer to integrate with APIs

Focus on writing clean, maintainable code and providing detailed explanations of your implementation choices."""
    },
    "BackendDev": {
        "role": "Backend Developer",
        "skills": ["API design", "database", "server logic", "authentication", "security"],
        "system_prompt": """You are a Backend Developer AI assistant. Your responsibilities include:
1. Designing and implementing APIs
2. Creating database schemas and queries
3. Implementing server-side business logic
4. Setting up authentication and authorization
5. Ensuring data security and performance

Focus on writing robust, secure code and providing detailed explanations of your implementation choices."""
    },
    "ContentWriter": {
        "role": "Content Writer",
        "skills": ["copywriting", "SEO", "storytelling", "product descriptions", "marketing"],
        "system_prompt": """You are a Content Writer AI assistant. Your responsibilities include:
1. Creating engaging and persuasive marketing copy
2. Writing SEO-optimized content
3. Developing product descriptions
4. Crafting brand stories and narratives
5. Editing and proofreading content

Focus on writing clear, compelling content that resonates with the target audience and achieves the project goals."""
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

def call_llm(messages, model="llama2:13b", timeout=120):
    """Call the local Ollama API with extended timeout"""
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
    
    # Call the Ollama API
    try:
        response = requests.post('http://localhost:11434/api/generate',
                        json={
                            'model': model,
                            'prompt': prompt,
                            'stream': False
                        }, timeout=timeout)
        
        if response.status_code == 200:
            return response.json()['response']
        else:
            return f"Error calling Ollama API: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Error connecting to Ollama: {str(e)}"

def parse_llm_response(response: str, expecting_json=False):
    """Parse the LLM response for actions or JSON content"""
    # Check for tool usage
    if "ACTION:" in response:
        action_part = response.split("ACTION:")[1].strip()
        tool_name = action_part.split("\n")[0].strip()
        
        # Only proceed if we find an INPUT section
        if "INPUT:" in action_part:
            input_part = action_part.split("INPUT:")[1].strip()
            
            # Only process valid inputs
            if input_part:
                return {
                    "type": "action",
                    "tool": tool_name,
                    "input": input_part
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
    """Save agent output as a file that can be downloaded later"""
    # Create agent-specific folder if it doesn't exist
    agent_dir = os.path.join(OUTPUT_DIR, agent_type)
    if not os.path.exists(agent_dir):
        os.makedirs(agent_dir)
    
    # Sanitize file name (remove spaces and special characters)
    safe_name = "".join([c for c in file_name if c.isalnum() or c in "._-"]).strip()
    if not safe_name:
        safe_name = "output"
    
    # Add timestamp to prevent overwriting
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Determine file extension based on content and type
    extension = ".txt"  # Default
    
    # Extract code blocks if present
    code_block_pattern = r'```(?:\w+)?\s*([\s\S]+?)\s*```'
    code_blocks = re.findall(code_block_pattern, content)
    
    # If we found code blocks, use the first one as content (if appropriate)
    extracted_content = content
    if code_blocks and ('html' in file_type.lower() or 'css' in file_type.lower() or 'js' in file_type.lower()):
        extracted_content = code_blocks[0]
    
    # Use proper extension based on file_type or content detection
    if file_type == 'html' or content.strip().startswith('<') and ('</html>' in content or '</body>' in content):
        extension = ".html"
    elif file_type == 'css' or content.find('@media') > 0 or content.find('{') > 0 and content.find('}') > 0:
        extension = ".css"
    elif file_type == 'js' or 'function(' in content or 'const ' in content or 'let ' in content:
        extension = ".js"
    elif file_type == 'json' or (content.strip().startswith('{') and content.strip().endswith('}')):
        extension = ".json"
    
    # Create full file name with timestamp and extension
    full_name = f"{timestamp}_{safe_name}{extension}"
    file_path = os.path.join(agent_dir, full_name)
    
    # Write content to file (use the extracted content if available)
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

def process_task(task):
    """Process a single task using the appropriate agent"""
    agent_type = task.agent_type
    if not agent_type:
        log_update("System", f"No agent type specified for task: {task.description}. Defaulting to ProjectManager.")
        agent_type = "ProjectManager"
    
    # Get appropriate prompt for this agent and task
    system_prompt = get_agent_prompt(agent_type, task.description)
    
    # Create context for the LLM
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Complete this task: {task.description}"}
    ]
    
    # Add information about available tools
    tools_description = "Available tools:\n"
    # Add common tools
    for tool_name, tool in COMMON_TOOLS.items():
        tools_description += f"- {tool}\n"
    
    # Add agent-specific tools
    if agent_type in AGENT_TOOLS:
        for tool_name, tool in AGENT_TOOLS[agent_type].items():
            tools_description += f"- {tool}\n"
    
    messages[0]["content"] += f"\n\n{tools_description}"
    
    # Update task status
    task.update_status("in_progress", f"Task started by {agent_type}")
    log_update(agent_type, f"Working on: {task.description}")
    
    # Call the LLM with an increased timeout
    response = call_llm(messages, timeout=240)
    
    # Parse the response
    parsed = parse_llm_response(response)
    
    if parsed["type"] == "action":
        # Agent wants to use a tool
        tool_name = parsed["tool"]
        tool_input = parsed["input"]
        
        tool_result = None
        found_tool = False
        
        # Look for tool in common tools with case-insensitive matching
        if tool_name.lower() in [t.lower() for t in COMMON_TOOLS.keys()]:
            # Find the actual key with correct casing
            for key in COMMON_TOOLS.keys():
                if key.lower() == tool_name.lower():
                    tool_result = COMMON_TOOLS[key].run(tool_input)
                    found_tool = True
                    break
        
        # Look for tool in agent-specific tools with case-insensitive matching
        elif agent_type in AGENT_TOOLS:
            for key in AGENT_TOOLS[agent_type].keys():
                if key.lower() == tool_name.lower():
                    tool_result = AGENT_TOOLS[agent_type][key].run(tool_input)
                    found_tool = True
                    break
        
        # If tool not found, log the error and provide a helpful message
        if not found_tool:
            available_tools = list(COMMON_TOOLS.keys())
            if agent_type in AGENT_TOOLS:
                available_tools.extend(list(AGENT_TOOLS[agent_type].keys()))
            
            error_msg = f"Tool '{tool_name}' not found. Available tools: {', '.join(available_tools)}"
            log_update("System", error_msg)
            tool_result = error_msg
        
        # Log the tool usage
        log_update(agent_type, f"Used tool: {tool_name} with input: {tool_input}")
        log_update("System", f"Tool result: {tool_result}")
        
        # Add the tool result to the conversation
        messages.append({"role": "assistant", "content": f"I'll use the {tool_name} tool with input: {tool_input}"})
        messages.append({"role": "system", "content": f"Tool result: {tool_result}"})
        
        # Ask the agent to provide its final result
        messages.append({"role": "user", "content": "Now that you have the tool result, please complete the task and provide your final output."})
        
        # Get the final response
        final_response = call_llm(messages, timeout=240)
        task.result = final_response
    else:
        # Agent provided a direct response
        task.result = response
    
    # Mark task as completed
    task.update_status("completed", f"Task completed by {agent_type}")
    log_update(agent_type, f"Completed task: {task.description}")
    
    # Enhanced file saving functionality
    if task.result:
        # Check task description for clues about file type
        desc_lower = task.description.lower()
        file_type = 'text'
        
        # More aggressive file type detection
        if any(term in desc_lower for term in ['html', 'webpage', 'web page', 'landing page', 'site']):
            file_type = 'html'
        elif any(term in desc_lower for term in ['css', 'style', 'stylesheet']):
            file_type = 'css'
        elif any(term in desc_lower for term in ['javascript', 'js', 'script', 'interactive']):
            file_type = 'js'
        elif any(term in desc_lower for term in ['json', 'api response', 'data format']):
            file_type = 'json'
        
        # Also check content for patterns if type still undetermined
        content = task.result
        if file_type == 'text':  # Only do content detection if type not already determined
            if content.strip().startswith('<') and ('</html>' in content or '</body>' in content):
                file_type = 'html'
            elif '{' in content and '}' in content and (':' in content or '@media' in content or '@keyframes' in content):
                file_type = 'css'
            elif ('function(' in content or 'const ' in content or 'let ' in content or 'var ' in content) and (';' in content):
                file_type = 'js'
            elif content.strip().startswith('{') and content.strip().endswith('}'):
                file_type = 'json'
        
        # Extract code blocks if present
        code_block_pattern = r'```(?:\w+)?\s*([\s\S]+?)\s*```'
        code_blocks = re.findall(code_block_pattern, content)
        
        # Use the extracted content if appropriate
        extracted_content = content
        if code_blocks and file_type != 'text':
            extracted_content = code_blocks[0]
            
            # Clean up any remaining markdown code fences
            extracted_content = re.sub(r'^```\w*\s*', '', extracted_content)
            extracted_content = re.sub(r'\s*```$', '', extracted_content)
        
        # Create a suitable filename from the task description
        file_name = re.sub(r'[^\w\s.-]', '', task.description[:40]).strip()
        file_name = re.sub(r'\s+', '_', file_name)
        
        # Save the output as a file
        file_info = save_output_file(task.agent_type, file_name, extracted_content, file_type)
        task.file_info = file_info
        
        log_update(agent_type, f"Output saved as file: {file_info['name']}")
        
        # Also check for additional code blocks to save as separate files
        code_block_pattern = r'```(\w+)\s*([\s\S]+?)\s*```'
        code_blocks = re.findall(code_block_pattern, task.result)
        
        for i, (language, code) in enumerate(code_blocks):
            # Skip if this is likely the main file we already saved
            if i == 0 and file_type != 'text' and language.lower() in file_type:
                continue
                
            # Determine file type from language
            block_file_type = 'text'
            if language.lower() in ['html', 'xml']:
                block_file_type = 'html'
            elif language.lower() in ['css']:
                block_file_type = 'css'
            elif language.lower() in ['javascript', 'js']:
                block_file_type = 'js'
            elif language.lower() in ['json']:
                block_file_type = 'json'
                
            # Save this code block as a separate file
            block_file_name = f"{file_name}_part{i+1}"
            block_file_info = save_output_file(task.agent_type, block_file_name, code, block_file_type)
            
            log_update(agent_type, f"Additional output saved: {block_file_info['name']}")
    
    # Return the result
    return task.result

def create_project_plan(description):
    """Create an initial project plan using the project manager agent"""
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
    system_prompt = AGENT_TYPES["ProjectManager"]["system_prompt"]
    prompt = f"""
{system_prompt}

You need to create a detailed project plan for the following project:

{description}

Break down this project into specific tasks that can be assigned to our team of specialists:
- ProjectManager (you): Planning, coordination, delegation
- FrontendDev: HTML, CSS, JavaScript, UI design, responsive design
- BackendDev: API design, database, server logic, authentication, security
- ContentWriter: Copywriting, SEO, storytelling, product descriptions, marketing

For each task, specify:
1. A clear, specific description
2. The agent type who should handle it
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
            task = Task(
                description=task_data.get("description", "Undefined task"),
                agent_type=task_data.get("agent_type", "ProjectManager"),
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
                agent_match = re.search(r'(ProjectManager|FrontendDev|BackendDev|ContentWriter)', line)
                agent_type = agent_match.group(1) if agent_match else "ProjectManager"
                
                # Create a new task
                description = re.sub(r'^\s*[-*]\s*', '', line)
                description = re.sub(r'\(.*?\)', '', description).strip()
                
                task = Task(description=description, agent_type=agent_type)
                tasks.append(task)
    
    # If we still have no tasks, create a generic one
    if not tasks:
        task = Task(description=f"Implement project: {description}", agent_type="ProjectManager")
        tasks.append(task)
    
    # Sort tasks by priority
    tasks.sort(key=lambda t: getattr(t, 'priority', 3))
    
    # Update project status
    for task in tasks:
        project_status["tasks"].append(task.to_dict())
    
    # Log the plan creation
    log_update("ProjectManager", f"Created project plan with {len(tasks)} tasks")
    for task in tasks:
        log_update("ProjectManager", f"Task: {task.description} (Assigned to: {task.agent_type})")
    
    return tasks

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
    """Get the next task to be processed based on priority and dependencies"""
    pending_tasks = []
    
    for t in project_status["tasks"]:
        if t["status"] == "pending":
            # Create a task with only the basic required fields
            task = Task(
                description=t["description"],
                agent_type=t.get("agent_type"),
                priority=t.get("priority", 3)
            )
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

def worker_thread():
    """Background worker thread that processes tasks"""
    global system_running
    
    while system_running:
        try:
            # If there are no tasks in the queue, check if we need to get a new one
            if task_queue.empty():
                next_task = get_next_task()
                if next_task:
                    task_queue.put(next_task)
            
            # Try to get a task with a 5-second timeout
            task = task_queue.get(timeout=5)
            
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
            # Log any errors
            log_update("System", f"Error in worker thread: {str(e)}")
            time.sleep(5)  # Sleep longer after an error to avoid rapid error loops

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