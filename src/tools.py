"""
Local bridge tools to complement the remote MCP server.
These tools handle DataFrame processing that the remote server doesn't provide.
"""

import json
import pandas as pd
from typing import Dict, Any, Literal, Optional

# Global storage for dataframes
saved_dataframes: dict[str, pd.DataFrame] = {}

def get_all_bridge_tools() -> list:
    """Get all local bridge tools as LiteLLM-compatible schemas"""
    return [
        {
            "type": "function",
            "function": {
                "name": "json_to_dataframe",
                "description": "Convert trading JSON (from get_historical_data) to DataFrame for analysis",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "json_string": {
                            "type": "string",
                            "description": "JSON string from get_historical_data"
                        },
                        "return_format": {
                            "type": "string",
                            "enum": ["records", "summary", "csv"],
                            "description": "Output format",
                            "default": "records"
                        },
                        "set_date_index": {
                            "type": "boolean",
                            "description": "Set 'date' column as DataFrame index",
                            "default": False
                        },
                        "save_name": {
                            "type": "string",
                            "description": "Save DataFrame in memory under this name"
                        }
                    },
                    "required": ["json_string"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_saved_dataframes",
                "description": "List all DataFrames saved in memory",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "clear_dataframes",
                "description": "Clear all saved DataFrames from memory",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_dataframe_info",
                "description": "Get detailed info about a saved DataFrame",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the saved DataFrame"
                        }
                    },
                    "required": ["name"]
                }
            }
        }
    ]

async def execute_bridge_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a local bridge tool"""
    
    if tool_name == "json_to_dataframe":
        return await json_to_dataframe(**arguments)
    elif tool_name == "list_saved_dataframes":
        return list_saved_dataframes()
    elif tool_name == "clear_dataframes":
        return clear_dataframes()
    elif tool_name == "get_dataframe_info":
        return get_dataframe_info(**arguments)
    else:
        raise ValueError(f"Unknown bridge tool: {tool_name}")

def is_bridge_tool(tool_name: str) -> bool:
    """Check if tool is a bridge tool"""
    return tool_name in ["json_to_dataframe", "list_saved_dataframes", "clear_dataframes", "get_dataframe_info"]

# Tool implementations
async def json_to_dataframe(
    json_string: str,
    return_format: Literal["records", "summary", "csv"] = "records",
    set_date_index: bool = False,
    save_name: Optional[str] = None
) -> Dict[str, Any]:
    """Convert trading JSON to DataFrame for analysis"""
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
            return {"success": True, "structured": summary, "text": "Summary generated"}
        
        elif return_format == "csv":
            csv_str = df.to_csv(index=set_date_index)
            return {
                "success": True,
                "structured": {"csv_content": csv_str, "rows": df.shape[0], "cols": df.shape[1]},
                "text": f"CSV generated with {df.shape[0]} rows"
            }
        
        else:  # records
            if "date" in df.columns and not set_date_index:
                df["date"] = df["date"].dt.strftime("%Y-%m-%dT%H:%M:%S")
            
            records = df.to_dict(orient="records")
            return {
                "success": True,
                "structured": {"data": records, "rows": df.shape[0], "cols": df.shape[1]},
                "text": f"Converted {df.shape[0]} records"
            }
    
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_saved_dataframes() -> Dict[str, Any]:
    """List all saved DataFrames"""
    result = {}
    for name, df in saved_dataframes.items():
        result[name] = f"{df.shape[0]}x{df.shape[1]} DataFrame"
    
    return {
        "success": True,
        "structured": {"dataframes": result},
        "text": f"Found {len(result)} saved DataFrames"
    }

def clear_dataframes() -> Dict[str, Any]:
    """Clear all saved DataFrames"""
    count = len(saved_dataframes)
    saved_dataframes.clear()
    return {
        "success": True,
        "structured": {"cleared_count": count},
        "text": f"Cleared {count} DataFrames"
    }

def get_dataframe_info(name: str) -> Dict[str, Any]:
    """Get info about a saved DataFrame"""
    if name not in saved_dataframes:
        return {
            "success": False,
            "error": f"DataFrame '{name}' not found"
        }
    
    df = saved_dataframes[name]
    info = {
        "shape": df.shape,
        "columns": df.columns.tolist(),
        "dtypes": df.dtypes.to_dict(),
        "memory_usage": df.memory_usage(deep=True).sum()
    }
    
    return {
        "success": True,
        "structured": info,
        "text": f"DataFrame '{name}': {df.shape[0]} rows, {df.shape[1]} columns"
    }
