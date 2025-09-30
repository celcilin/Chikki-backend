# api.py
from agents import AgentManager

class APIManager:
    def __init__(self, gemini_api_key):
        self.agent_manager = AgentManager(gemini_api_key)

        # Register sample specialized agents
        self.agent_manager.create_agent("scheduler", "Calendar Assistant", "Manage user calendar and set reminders")
        self.agent_manager.create_agent("study_coach", "Study Mentor", "Encourage focus and break-study balance")
        self.agent_manager.create_agent("wellness", "Wellness Buddy", "Suggest exercises, food, and calming habits")

    def handle_request(self, agent_name, user_name, context):
        """Route request to the right agent"""
        return self.agent_manager.run_agent(agent_name, user_name, context)

    def manage_mcp(self, agent_name, goal, status):
        """Coordinate agents in a MCP pipeline (handoffs, next step)"""
        return self.agent_manager.coordinate_mcp(agent_name, goal, status)

    # Example external APIs stubs
    def add_event(self, title, time):
        print(f"[CalendarAPI] Event Added: {title} at {time}")
        return {"status": "success", "title": title, "time": time}