import os
import json
from typing import List, Dict, Any
import requests
import re

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

class Memory:
    """Simple memory system for the agent"""
    
    def __init__(self, max_entries: int = 10):
        self.conversations = []
        self.max_entries = max_entries
        
    def add(self, role: str, content: str):
        """Add an entry to memory"""
        self.conversations.append({"role": role, "content": content})
        if len(self.conversations) > self.max_entries:
            self.conversations.pop(0)
    
    def get_context(self) -> List[Dict[str, str]]:
        """Get the current context from memory"""
        return self.conversations.copy()

class Agent:
    """AI agent that can use tools and maintain context"""
    
    def __init__(self, model: str = "llama2:13b"):
        self.model = model
        self.memory = Memory()
        self.tools = []
        self.system_prompt = """You are a helpful AI assistant. When you need to perform an action, use one of the available tools by responding in this exact format:
ACTION: tool_name
INPUT: input for the tool

If you don't need to use a tool, just respond normally."""
    
    def add_tool(self, tool: Tool):
        """Add a tool that the agent can use"""
        self.tools.append(tool)
        
    def set_system_prompt(self, prompt: str):
        """Set the system prompt for the agent"""
        self.system_prompt = prompt
    
    def _get_available_tools_description(self) -> str:
        """Get a description of all available tools"""
        if not self.tools:
            return "No tools available."
        
        return "Available tools:\n" + "\n".join([str(tool) for tool in self.tools])
    
    def _call_llm(self, messages):
        """Call the local Ollama API"""
        import requests
        
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
            elif role == "assistant":
                prompt += f" {content} </s>"
        
        # Call the Ollama API
        try:
            response = requests.post('http://localhost:11434/api/generate',
                            json={
                                'model': self.model,
                                'prompt': prompt,
                                'stream': False
                            }, timeout=60)  # Longer timeout for larger model
            
            if response.status_code == 200:
                return response.json()['response']
            else:
                return f"Error calling Ollama API: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error connecting to Ollama: {str(e)}"
    
    def _parse_response(self, response: str):
        """Parse the LLM response to extract any action and input"""
        # Check for the formal ACTION structure
        if "ACTION:" in response:
            action_part = response.split("ACTION:")[1].strip()
            tool_name = action_part.split("\n")[0].strip()
            
            # Only proceed if we find an INPUT section
            if "INPUT:" in action_part:
                input_part = action_part.split("INPUT:")[1].strip()
                
                # Only process valid inputs
                if input_part:
                    return {
                        "use_tool": True,
                        "tool_name": tool_name,
                        "input": input_part
                    }
        
        # If we get here, no valid tool usage was detected
        return {
            "use_tool": False,
            "response": response
        }
    
    def _execute_tool(self, tool_name: str, input_str: str) -> str:
        """Execute a tool by name"""
        for tool in self.tools:
            if tool.name.lower() == tool_name.lower():
                return tool.run(input_str)
        
        return f"Error: Tool '{tool_name}' not found."
    
    def run(self, user_input: str) -> str:
        """Run the agent with a user input"""
        # Direct handling for simple calculations - only if the input is clearly a calculation
        if re.match(r'^\s*\d+\s*[\+\-\*\/]\s*\d+\s*$', user_input):
            calculation = user_input.strip()
            result = self._execute_tool("calculator", calculation)
            return f"The result of {calculation} is {result.split(': ')[1]}"
            
        # Add user input to memory
        self.memory.add("user", user_input)
        
        # Prepare messages for the LLM with clear instructions
        system_message = f"""
{self.system_prompt}

{self._get_available_tools_description()}

IMPORTANT RULES:
1. Only use a tool when the user explicitly asks for information that requires that tool.
2. For general conversation, questions about yourself, or any non-tool tasks, just respond normally without using tools.
3. Use the calculator tool only for mathematical calculations.
4. Use the weather tool only when asked about weather in a specific location.
5. Use the search tool only when asked to find or search for specific information.
"""
        
        messages = [
            {"role": "system", "content": system_message}
        ]
        messages.extend(self.memory.get_context())
        
        # Get response from LLM
        response = self._call_llm(messages)
        
        # Parse the response for possible tool usage
        parsed = self._parse_response(response)
        
        # If a tool should be used
        if parsed["use_tool"]:
            tool_name = parsed["tool_name"]
            tool_input = parsed["input"]
            
            print(f"Using tool: {tool_name} with input: {tool_input}")
            
            # Execute the tool
            tool_output = self._execute_tool(tool_name, tool_input)
            
            # For simple calculations, return the result directly
            if tool_name.lower() == "calculator":
                result = tool_output.split(": ")[1] if ": " in tool_output else tool_output
                return f"The result of {tool_input} is {result}"
            
            # Add tool usage to memory
            self.memory.add("assistant", f"I'll help you with that using the {tool_name} tool.")
            self.memory.add("system", f"Tool result: {tool_output}")
            
            # Get final response with the tool result
            messages = [
                {"role": "system", "content": f"You are a helpful assistant. The user asked: '{user_input}'. You used the {tool_name} tool and got this result: '{tool_output}'. Now provide a helpful response based on this information."}
            ]
            
            final_response = self._call_llm(messages)
            self.memory.add("assistant", final_response)
            
            return final_response
        else:
            # No tool needed, just return the response
            self.memory.add("assistant", parsed["response"])
            return parsed["response"]

# Example implementation - Creating tools

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

# Example usage
if __name__ == "__main__":
    # Create an agent with llama2:13b
    agent = Agent(model="llama2:13b")
    
    # Add tools
    agent.add_tool(Tool("search", "Search the web for information", search_web))
    agent.add_tool(Tool("weather", "Get the current weather for a location", get_weather))
    agent.add_tool(Tool("calculator", "Perform mathematical calculations", calculate))
    
    # Set a custom system prompt
    agent.set_system_prompt("""You are a helpful AI assistant with access to tools.
When asked for information that requires using a tool, use the appropriate tool.
For general questions or conversation, respond directly without using tools.
Keep your responses concise and directly address what the user is asking.""")
    
    # Interactive loop
    print("AI Agent initialized with llama2:13b model. Type 'exit' to quit.")
    print("This model is much more powerful, but may be slower to respond.")
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == 'exit':
            break
        
        print("Thinking...")
        response = agent.run(user_input)
        print(f"\nAgent: {response}")