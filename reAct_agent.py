import os
from dotenv import load_dotenv
load_dotenv()

from langchain.agents import AgentType, initialize_agent
from langchain_experimental.tools import PythonREPLTool
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(openai_api_key=os.environ.get('OPENAI_API_KEY'), model='gpt-4o-mini')

tools = [PythonREPLTool()]

agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)

# Test ReAct on Wah queue
agent.run('Queue a task for Wah budget review: status ;WAITING FOR, effort medium')