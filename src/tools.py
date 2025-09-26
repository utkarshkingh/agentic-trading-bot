
import json
import pandas as pd
from typing import Literal, Optional
from langchain_core.tools import tool

# Global storage for dataframes
saved_dataframes: dict[str, pd.DataFrame] = {}

@tool
def json_to_dataframe(
    json_string: str,
    return_format: Literal["records", "summary", "csv"] = "records",
    set_date_index: bool = False,
    save_name: Optional[str] = None
) -> str:
    """Convert trading JSON (from get_historical_data) to DataFrame for analysis.
    
    Args:
        json_string: JSON string from get_historical_data
        return_format: Output format (records/summary/csv)
        set_date_index: Set 'date' column as DataFrame index
        save_name: Save DataFrame in memory under this name
    """
    try:
        # Parse JSON data
        data = json.loads(json_string)
        df = pd.DataFrame(data)
        
        # Handle date column
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        
        # Set date as index if requested
        if set_date_index and "date" in df.columns:
            df.set_index("date", inplace=True)
        
        # Save to memory if name provided
        if save_name:
            saved_dataframes[save_name] = df
        
        # Format output
        if return_format == "summary":
            summary = {
                "shape": df.shape,
                "columns": df.columns.tolist(),
                "date_range": {
                    "start": df["date"].min().isoformat() if "date" in df.columns else None,
                    "end": df["date"].max().isoformat() if "date" in df.columns else None,
                } if "date" in df.columns else None,
                "stats": df.describe().to_dict()
            }
            return json.dumps({"success": True, "structured": summary, "text": "Summary generated"})
            
        elif return_format == "csv":
            csv_str = df.to_csv(index=set_date_index)
            result = {
                "success": True,
                "structured": {"csv_content": csv_str, "rows": df.shape[0], "cols": df.shape[1]},
                "text": f"CSV generated with {df.shape[0]} rows"
            }
            return json.dumps(result)
            
        else:  # records
            if "date" in df.columns and not set_date_index:
                df["date"] = df["date"].dt.strftime("%Y-%m-%dT%H:%M:%S")
            records = df.to_dict(orient="records")
            result = {
                "success": True,
                "structured": {"data": records, "rows": df.shape[0], "cols": df.shape[1]},
                "text": f"Converted {df.shape[0]} records"
            }
            return json.dumps(result)
            
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

@tool
def list_saved_dataframes() -> str:
    """List all DataFrames saved in memory."""
    result = {}
    for name, df in saved_dataframes.items():
        result[name] = f"{df.shape[0]}x{df.shape[1]} DataFrame"
    
    return json.dumps({
        "success": True,
        "structured": {"dataframes": result},
        "text": f"Found {len(result)} saved DataFrames"
    })

@tool
def clear_dataframes() -> str:
    """Clear all saved DataFrames from memory."""
    count = len(saved_dataframes)
    saved_dataframes.clear()
    
    return json.dumps({
        "success": True,
        "structured": {"cleared_count": count},
        "text": f"Cleared {count} DataFrames"
    })

@tool
def get_dataframe_info(name: str) -> str:
    """Get detailed info about a saved DataFrame.
    
    Args:
        name: Name of the saved DataFrame
    """
    if name not in saved_dataframes:
        return json.dumps({
            "success": False,
            "error": f"DataFrame '{name}' not found"
        })
    
    df = saved_dataframes[name]
    info = {
        "shape": df.shape,
        "columns": df.columns.tolist(),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "memory_usage": int(df.memory_usage(deep=True).sum())
    }
    
    return json.dumps({
        "success": True,
        "structured": info,
        "text": f"DataFrame '{name}': {df.shape[0]} rows, {df.shape[1]} columns"
    })

# Get all tools as list for LangChain integration
def get_langchain_tools():
    """Get all tools as LangChain tool objects."""
    return [json_to_dataframe, list_saved_dataframes, clear_dataframes, get_dataframe_info]

# Bridge function for compatibility with existing openrouter_bridge.py
def get_all_bridge_tools() -> list:
    """Get all local bridge tools as LiteLLM-compatible schemas (for backwards compatibility)."""
    tools = []
    langchain_tools = get_langchain_tools()
    
    for tool in langchain_tools:
        # Convert LangChain tool to LiteLLM format
        tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.args_schema.schema() if tool.args_schema else {"type": "object", "properties": {}}
            }
        })
    
    return tools

def is_bridge_tool(tool_name: str) -> bool:
    """Check if tool is a bridge tool."""
    tool_names = [tool.name for tool in get_langchain_tools()]
    return tool_name in tool_names

async def execute_bridge_tool(tool_name: str, arguments: dict) -> dict:
    """Execute a local bridge tool (for backwards compatibility)."""
    tools_dict = {tool.name: tool for tool in get_langchain_tools()}
    
    if tool_name not in tools_dict:
        raise ValueError(f"Unknown bridge tool: {tool_name}")
    
    tool = tools_dict[tool_name]
    result_str = await tool.ainvoke(arguments) if hasattr(tool, 'ainvoke') else tool.invoke(arguments)
    
    # Parse JSON result back to dict for compatibility
    try:
        return json.loads(result_str)
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid JSON response from tool"}
