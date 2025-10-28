#!/usr/bin/env python3
"""
Example: Using Technical Analysis Tools

This script demonstrates how to use the dynamically registered
pandas-ta indicators with LangChain tools.
"""

import json
import pandas as pd
from tools import get_langchain_tools, saved_dataframes


def main():
    """Demonstrate TA tool usage."""
    
    # 1. Get all available tools
    tools = get_langchain_tools()
    print(f"✓ Loaded {len(tools)} tools")
    print(f"  - Base tools: 4")
    print(f"  - TA indicator tools: {len(tools) - 4}")
    print()
    
    # 2. Create sample OHLCV data
    sample_data = {
        'date': pd.date_range('2024-01-01', periods=100, freq='D'),
        'open': [100 + i * 0.5 for i in range(100)],
        'high': [101 + i * 0.5 for i in range(100)],
        'low': [99 + i * 0.5 for i in range(100)],
        'close': [100.5 + i * 0.5 for i in range(100)],
        'volume': [1000000 + i * 1000 for i in range(100)]
    }
    df = pd.DataFrame(sample_data)
    saved_dataframes['example_stock'] = df
    print("✓ Created sample OHLCV DataFrame")
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {df.columns.tolist()}")
    print()
    
    # 3. Apply SMA (Simple Moving Average)
    sma_tool = [t for t in tools if t.name == 'ta_sma'][0]
    result = json.loads(sma_tool.invoke({
        'dataframe_name': 'example_stock',
        'length': 20
    }))
    print("✓ Applied SMA (20-period)")
    print(f"  {result['text']}")
    print()
    
    # 4. Apply RSI (Relative Strength Index)
    rsi_tool = [t for t in tools if t.name == 'ta_rsi'][0]
    result = json.loads(rsi_tool.invoke({
        'dataframe_name': 'example_stock',
        'length': 14
    }))
    print("✓ Applied RSI (14-period)")
    print(f"  {result['text']}")
    print(f"  Stats: {result['structured']['stats']}")
    print()
    
    # 5. Apply MACD (Moving Average Convergence Divergence)
    macd_tool = [t for t in tools if t.name == 'ta_macd'][0]
    result = json.loads(macd_tool.invoke({
        'dataframe_name': 'example_stock'
    }))
    print("✓ Applied MACD")
    print(f"  {result['text']}")
    print(f"  Columns: {result['structured']['columns_added']}")
    print()
    
    # 6. Apply Bollinger Bands
    bbands_tool = [t for t in tools if t.name == 'ta_bbands'][0]
    result = json.loads(bbands_tool.invoke({
        'dataframe_name': 'example_stock',
        'length': 20,
        'result_column_prefix': 'BB'
    }))
    print("✓ Applied Bollinger Bands")
    print(f"  {result['text']}")
    print()
    
    # 7. Show final DataFrame info
    final_df = saved_dataframes['example_stock']
    print("✓ Final DataFrame")
    print(f"  Shape: {final_df.shape}")
    print(f"  Columns: {final_df.columns.tolist()}")
    print()
    print("Sample data (last 5 rows):")
    print(final_df[['close', 'SMA', 'RSI']].tail())
    print()
    
    # 8. List some popular indicators available
    print("Popular TA indicators available:")
    popular = ['ta_sma', 'ta_ema', 'ta_rsi', 'ta_macd', 'ta_bbands', 
               'ta_atr', 'ta_adx', 'ta_stoch', 'ta_cci', 'ta_obv']
    for tool_name in popular:
        tool = [t for t in tools if t.name == tool_name]
        if tool:
            print(f"  ✓ {tool_name}: {tool[0].description}")


if __name__ == '__main__':
    main()
