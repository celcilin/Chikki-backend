# prompts.py
from langchain.prompts import PromptTemplate

# General agent prompt
base_agent_prompt = PromptTemplate(
    input_variables=["role", "task", "user_name", "context"],
    template=(
        "You are {role}. Your main task: {task}.\n"
        "The user is {user_name}. Use friendly, helpful tone.\n"
        "Context: {context}\n\n"
        "Now produce your best response:"
    )
)

# MCP Controller Prompt
mcp_controller_prompt = PromptTemplate(
    input_variables=["agent_name", "goal", "status"],
    template=(
        "You are an Agent Coordinator managing an MCP.\n"
        "Agent '{agent_name}' has the goal: {goal}.\n"
        "Current status: {status}\n\n"
        "Determine the next best action or agent handoff."
    )
)