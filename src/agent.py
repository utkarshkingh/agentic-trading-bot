from langgraph.graph import StateGraph, END
from typing import Optional, Dict, Any, List,TypedDict,Annotated
from langchain_core.tools import tool
import operator
import asyncio
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage, ChatMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from dotenv import load_dotenv
from client import ZerodhaMCPClient

load_dotenv()

memory = SqliteSaver.from_conn_string(":memory:")




class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]


class Agent:
    def __init__(self, model, tools, checkpointer, system=""):
        self.system = system
        graph = StateGraph(AgentState)
        graph.add_node("llm", self.get_historical_data)
        graph.add_node("action", self.json_to_dataframe)
        graph.add_conditional_edges("llm", self.exists_action, {True: "action", False: END})
        graph.add_edge("action", "llm")
        graph.set_entry_point("llm")
        self.graph = graph.compile(checkpointer=checkpointer)
        self.tools = {t.name: t for t in tools}
        self.model = model.bind_tools(tools)
        

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call tools """
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
            
        try:
            result = await self.session.call_tool(tool_name, arguments)
            
            # Extract text content
            text_results = []
            for content in result.content:
                if hasattr(content, 'text'):
                    text_results.append(content.text)
            
            structured = getattr(result, 'structuredContent', None)
            
            return {
                "success": True,
                "text": "\n".join(text_results),
                "structured": structured,
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "text": None,
                "structured": None,
                "error": str(e)
            }
        

    def exists_action(self, state: AgentState):
        result = state['messages'][-1]
        return len(result.tool_calls) > 0






