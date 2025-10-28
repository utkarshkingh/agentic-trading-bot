"""
Technical Analysis Tools for Agentic Trading Bot

This module provides a comprehensive set of tools for technical analysis using pandas-ta,
integrated with LangChain for AI agent workflows.

Features:
---------
1. DataFrame Management Tools:
   - json_to_dataframe: Convert trading data JSON to pandas DataFrame
   - list_saved_dataframes: List all DataFrames in memory
   - clear_dataframes: Clear all saved DataFrames
   - get_dataframe_info: Get detailed info about a DataFrame

2. Technical Analysis Indicators (161 tools):
   All pandas-ta indicators are automatically registered as tools:
   - Overlap: SMA, EMA, WMA, VWAP, etc.
   - Momentum: RSI, MACD, Stochastic, CCI, etc.
   - Volatility: ATR, Bollinger Bands, Keltner Channels, etc.
   - Volume: OBV, AD, CMF, MFI, etc.
   - Trend: ADX, Aroon, Supertrend, etc.
   - Statistics, Performance, Candle patterns, and more

Usage Example:
--------------
```python
from tools import get_langchain_tools, saved_dataframes
import pandas as pd

# Get all tools
tools = get_langchain_tools()  # Returns 165 tools (4 base + 161 TA)

# Create and save OHLCV data
df = pd.DataFrame({
    'open': [...], 'high': [...], 'low': [...], 
    'close': [...], 'volume': [...]
})
saved_dataframes['my_stock'] = df

# Use TA tools
sma_tool = [t for t in tools if t.name == 'ta_sma'][0]
result = sma_tool.invoke({
    'dataframe_name': 'my_stock',
    'length': 20
})
```

Best Practices:
---------------
1. All TA tools work on saved DataFrames - use json_to_dataframe first
2. Tools add indicator columns directly to the DataFrame
3. Use result_column_prefix to customize column names
4. All tools return structured JSON with success/error indicators
5. Tools validate required OHLCV columns automatically

Architecture:
-------------
- Dynamic tool registration using introspection
- Pydantic models for parameter validation
- Comprehensive error handling
- AI agent and MCP best practices compliant
- Memory-efficient DataFrame storage
"""

import json
import logging
import pandas as pd
import pandas_ta as ta
import inspect
from typing import Literal, Optional, Any, Dict, List
from langchain_core.tools import tool, StructuredTool
from pydantic import BaseModel, Field, create_model

# Configure logging
logger = logging.getLogger(__name__)

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

# ============================================================================
# Technical Analysis Tools - Dynamic Registration
# ============================================================================

def _create_ta_tool(indicator_name: str, indicator_func: callable) -> StructuredTool:
    """
    Dynamically create a LangChain tool for a pandas-ta indicator.
    
    This function introspects the indicator function signature and creates
    a tool that works with saved DataFrames, following AI agent best practices.
    
    Args:
        indicator_name: Name of the technical indicator (e.g., 'sma', 'rsi')
        indicator_func: The actual pandas-ta indicator function
        
    Returns:
        StructuredTool configured for the indicator
    """
    sig = inspect.signature(indicator_func)
    params = sig.parameters
    
    # Extract docstring for description
    doc = indicator_func.__doc__ or f"Calculate {indicator_name.upper()} technical indicator"
    description = doc.strip().split('\n')[0]  # First line as description
    
    # Determine which price columns are needed
    price_cols = []
    for param_name in ['open_', 'high', 'low', 'close', 'volume']:
        if param_name in params:
            price_cols.append(param_name.rstrip('_'))
    
    # Build dynamic Pydantic model for parameters
    field_definitions = {
        'dataframe_name': (str, Field(description="Name of the saved DataFrame to analyze")),
    }
    
    # Add optional parameters with defaults
    for param_name, param in params.items():
        if param_name in ['open_', 'high', 'low', 'close', 'volume', 'series', 'kwargs']:
            continue  # Skip price columns and kwargs - we'll extract from dataframe
            
        # Get default value and type hint
        default_val = param.default if param.default != inspect.Parameter.empty else None
        param_type = param.annotation if param.annotation != inspect.Parameter.empty else Any
        
        # Map types for better schema generation
        if param_type == inspect.Parameter.empty or 'Union' in str(param_type):
            param_type = Any
        
        # All parameters should be Optional with None as default if no default specified
        field_definitions[param_name] = (
            Optional[param_type], 
            Field(default=default_val, description=f"Parameter: {param_name}")
        )
    
    # Add return column name
    field_definitions['result_column_prefix'] = (
        Optional[str], 
        Field(default=None, description="Prefix for result column names in DataFrame (optional)")
    )
    
    InputModel = create_model(f'{indicator_name.upper()}Input', **field_definitions)
    
    def ta_tool_func(**kwargs) -> str:
        """Execute the technical analysis indicator on saved DataFrame."""
        dataframe_name = kwargs.pop('dataframe_name')
        result_prefix = kwargs.pop('result_column_prefix', None)
        
        # Validate DataFrame exists
        if dataframe_name not in saved_dataframes:
            return json.dumps({
                "success": False,
                "error": f"DataFrame '{dataframe_name}' not found. Use list_saved_dataframes to see available DataFrames."
            })
        
        df = saved_dataframes[dataframe_name]
        
        try:
            # Extract price data columns needed by this indicator
            # Map DataFrame column names to pandas-ta parameter names
            param_name_map = {
                'open': 'open_',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            }
            
            ta_kwargs = {}
            for col in price_cols:
                col_name = col.lower()
                # Try common column name variations
                for variant in [col_name, col_name.capitalize(), col_name.upper()]:
                    if variant in df.columns:
                        param_name = param_name_map.get(col, col)
                        ta_kwargs[param_name] = df[variant]
                        break
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Required column '{col}' not found in DataFrame. Available: {df.columns.tolist()}"
                    })
            
            # Add other parameters
            for key, value in kwargs.items():
                if value is not None:
                    ta_kwargs[key] = value
            
            # Calculate indicator
            result = indicator_func(**ta_kwargs)
            
            # Handle result (can be Series or DataFrame)
            if isinstance(result, pd.Series):
                col_name = result_prefix or indicator_name.upper()
                df[col_name] = result
                saved_dataframes[dataframe_name] = df
                
                return json.dumps({
                    "success": True,
                    "structured": {
                        "indicator": indicator_name,
                        "column_added": col_name,
                        "non_null_values": int(result.notna().sum()),
                        "stats": {
                            "min": float(result.min()) if result.notna().any() else None,
                            "max": float(result.max()) if result.notna().any() else None,
                            "mean": float(result.mean()) if result.notna().any() else None,
                        }
                    },
                    "text": f"Added {indicator_name.upper()} indicator as column '{col_name}' to DataFrame '{dataframe_name}'"
                })
            
            elif isinstance(result, pd.DataFrame):
                # Multiple columns returned (e.g., MACD, BBands)
                prefix = result_prefix or indicator_name.upper()
                new_cols = []
                for col in result.columns:
                    new_col_name = f"{prefix}_{col}" if not col.startswith(prefix) else col
                    df[new_col_name] = result[col]
                    new_cols.append(new_col_name)
                
                saved_dataframes[dataframe_name] = df
                
                return json.dumps({
                    "success": True,
                    "structured": {
                        "indicator": indicator_name,
                        "columns_added": new_cols,
                        "num_columns": len(new_cols)
                    },
                    "text": f"Added {indicator_name.upper()} indicator columns {new_cols} to DataFrame '{dataframe_name}'"
                })
            
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Unexpected result type: {type(result)}"
                })
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error calculating {indicator_name}: {str(e)}"
            })
    
    # Create the tool with proper metadata
    tool_name = f"ta_{indicator_name}"
    tool_description = f"{description}. Works on saved DataFrames with OHLCV data."
    
    return StructuredTool(
        name=tool_name,
        description=tool_description,
        func=ta_tool_func,
        args_schema=InputModel,
    )


def _get_ta_indicators() -> Dict[str, callable]:
    """
    Get all available pandas-ta indicator functions.
    
    Returns:
        Dictionary mapping indicator names to their functions
    """
    indicators = {}
    
    # Iterate through pandas-ta module
    for attr_name in dir(ta):
        if attr_name.startswith('_'):
            continue
            
        attr = getattr(ta, attr_name)
        if not inspect.isfunction(attr):
            continue
        
        # Check if it's an indicator function (has OHLCV parameters)
        try:
            sig = inspect.signature(attr)
            params = list(sig.parameters.keys())
            
            # Most indicators take open, high, low, close, volume, or series
            if any(p in params for p in ['open_', 'high', 'low', 'close', 'volume', 'series']):
                indicators[attr_name] = attr
        except:
            continue
    
    return indicators


def _register_ta_tools() -> List[StructuredTool]:
    """
    Register all pandas-ta indicators as LangChain tools.
    
    This follows best practices for AI agents:
    - Clear, descriptive tool names (ta_<indicator>)
    - Comprehensive docstrings
    - Proper error handling
    - Structured output format
    - Works with saved DataFrames for efficiency
    
    Returns:
        List of StructuredTool objects for all TA indicators
    """
    ta_tools = []
    indicators = _get_ta_indicators()
    
    for indicator_name, indicator_func in indicators.items():
        try:
            tool = _create_ta_tool(indicator_name, indicator_func)
            ta_tools.append(tool)
        except Exception as e:
            # Skip indicators that fail to register
            logger.warning(f"Could not register {indicator_name}: {e}")
            continue
    
    return ta_tools


# Get all tools as list for LangChain integration
def get_langchain_tools():
    """
    Get all tools as LangChain tool objects.
    
    This includes:
    - DataFrame management tools (json_to_dataframe, list_saved_dataframes, etc.)
    - All technical analysis indicator tools (SMA, EMA, RSI, MACD, etc.)
    
    Returns:
        List of all available LangChain tools
    """
    base_tools = [
        json_to_dataframe, 
        list_saved_dataframes, 
        clear_dataframes, 
        get_dataframe_info
    ]
    
    # Add all TA indicator tools
    ta_tools = _register_ta_tools()
    
    return base_tools + ta_tools

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
