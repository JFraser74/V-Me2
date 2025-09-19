import os
from dotenv import load_dotenv
load_dotenv()

from langchain.agents import AgentType, initialize_agent
from langchain_experimental.tools import PythonREPLTool
from langchain_groq import ChatGroq

llm = ChatGroq(groq_api_key=os.environ.get('GROQ_API_KEY'), model_name='llama-3.2-11b-vision-preview')

tools = [PythonREPLTool()]

agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)

# Test ReAct on Wah queue
agent.run('Queue a task for Wah budget review: status ;WAITING FOR, effort medium')
