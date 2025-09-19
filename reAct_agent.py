from langchain.agents import AgentType, initialize_agent
from langchain.tools import PythonREPLTool
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
load_dotenv()

llm = ChatGroq(groq_api_key=os.environ.get('GROQ_API_KEY'))
tools = [PythonREPLTool()]

agent = initialize_agent(tools, llm, agent=AgentType.REACT_DESCRIPTION, verbose=True)

# Test ReAct on Wah queue
agent.run('Queue a task for Wah budget review: status ;WAITING FOR, effort medium')
