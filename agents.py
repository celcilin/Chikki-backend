# agents.py
from langchain_google_genai import ChatGoogleGenerativeAI
from prompts import base_agent_prompt, mcp_controller_prompt

class AgentManager:
    def __init__(self, gemini_api_key: str):
        # Wrap Gemini as an LLM for LangChain
        self.llm = ChatGoogleGenerativeAI(
            model="models/gemini-1.5-pro",   # or flash for cheaper
            google_api_key=gemini_api_key
        )
        self.agents = {}

    def create_agent(self, name, role, task):
        """Registers an agent with a specific role/task"""
        chain = self.llm | base_agent_prompt
        # chain.verbose = True
        self.agents[name] = {
            "role": role,
            "task": task,
            "chain": chain
        }
        print(f"[AGENT] Created agent '{name}' with role={role}")

    def run_agent(self, name, user_name, context):
        """Executes prompt chain for agent"""
        if name not in self.agents:
            raise ValueError(f"Agent {name} not found")
        agent = self.agents[name]
        response = agent["chain"].invoke(
            role=agent["role"],
            task=agent["task"],
            user_name=user_name,
            context=context
        )
        return response

    def coordinate_mcp(self, agent_name, goal, status):
        """Uses LLM to decide MCP orchestration steps"""
        chain = self.llm | mcp_controller_prompt
        response = chain.invoke(
            agent_name=agent_name,
            goal=goal,
            status=status
        )
        return response