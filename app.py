"""
FastAPI Backend for Conversational Analytics System
Compatible with your SmartChartGenerator
"""
# main app.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pandas as pd
import json
from datetime import datetime
import os

# Import your existing modules
from intent_conversation import (
    detect_query_tags_cached,
    route_query_with_tags,
    build_conversation_context
)
from graph_generator import SmartChartGenerator

app = FastAPI(title="Analytics Chat API")

# Enable CORS for web interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (HTML, CSS, JS)
# Create a 'static' directory and put your frontend.html there
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory conversation storage (use Redis/DB in production)
conversations: Dict[str, List[Dict]] = {}


# Request/Response Models
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChartData(BaseModel):
    chart_type: str
    image_data: str
    title: str
    x_axis: Optional[str] = None
    y_axis: Optional[List[str]] = None


class ChatResponse(BaseModel):
    response: str
    results_table: Optional[str] = None
    results_data: Optional[List[Dict]] = None
    charts: List[ChartData] = []
    suggestions: List[str] = []
    metadata: Dict[str, Any] = {}  # This will contain chart_html


# Helper Functions
def dataframe_to_html(df: pd.DataFrame) -> str:
    """Convert DataFrame to HTML table with styling"""
    if df is None or df.empty:
        return ""
    
    # Add custom styling to the HTML table
    html = df.to_html(
        index=False, 
        classes="table table-striped table-hover",
        border=0
    )
    
    # Wrap in a styled container
    styled_html = f"""
    <div style="overflow-x: auto; margin: 10px 0;">
        <style>
            .table th {{
                background: #333;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: 600;
            }}
            .table td {{
                padding: 10px 12px;
                border-bottom: 1px solid #e0e0e0;
            }}
            .table tr:hover {{
                background: #f5f5f5;
            }}
        </style>
        {html}
    </div>
    """
    return styled_html


def dataframe_to_json(df: pd.DataFrame) -> List[Dict]:
    """Convert DataFrame to JSON-serializable list"""
    if df is None or df.empty:
        return []
    return df.to_dict(orient='records')


def generate_charts(results_df: pd.DataFrame, user_query: str, user_tags: dict, col_metadata: Dict = None, conversation_history: List[Dict] = None) -> List[ChartData]:
    """
    Generate charts using your SmartChartGenerator
    Returns list of ChartData objects
    
    NEW: Accepts conversation_history to extract previous metrics for continuation queries
    """
    try:
        generator = SmartChartGenerator()
        
        # FIX: Extract previous metrics from conversation history for continuation queries
        # The challenge: Query 1 has metrics=['SALE_QUANTITY', 'TOTAL_AMOUNT'] in tags
        # Query 2 "store wise?" has metrics=[] BUT same SQL columns (total_units, total_revenue)
        # We need to remember the INTENT, not just the tag names
        
        if conversation_history and len(conversation_history) > 0:
            # Look at the most recent query's tags
            last_entry = conversation_history[-1]
            
            # SMART: Check if current query has no metrics but previous did
            current_has_metrics = user_tags.get('metric') and len(user_tags.get('metric')) > 0
            
            if not current_has_metrics:
                # This is likely a continuation query - try to extract metrics from history
                # Look for common metric column names in the CURRENT DataFrame
                common_metric_cols = []
                for col in results_df.columns:
                    col_lower = col.lower()
                    if any(metric_keyword in col_lower for metric_keyword in [
                        'total_units', 'total_revenue', 'total_amount', 
                        'sale_quantity', 'quantity', 'revenue', 'amount',
                        'avg_sale', 'average'
                    ]):
                        # Exclude administrative columns
                        if not any(admin_keyword in col_lower for admin_keyword in [
                            'count', 'year', 'month', 'week', 'day', 'id', 'number'
                        ]):
                            common_metric_cols.append(col)
                
                if common_metric_cols:
                    generator.last_metrics = common_metric_cols
                    print(f"[CHART CONTEXT] Continuation query detected - using metrics from current DataFrame: {common_metric_cols}")
        
        # Use your existing chart generation logic
        chart_datas = generator.generate_charts_from_tags(
            results_df, 
            user_query, 
            user_tags,
            col_metadata=col_metadata
        )
        
        if not chart_datas:
            return []
        
        # Handle single chart returned as dict
        if isinstance(chart_datas, dict):
            chart_datas = [chart_datas]
        
        # Convert to ChartData models
        charts = []
        for chart_data in chart_datas:
            if isinstance(chart_data, dict) and 'image_data' in chart_data:
                charts.append(ChartData(
                    chart_type=chart_data.get('chart_type', 'unknown'),
                    image_data=chart_data.get('image_data', ''),
                    title=chart_data.get('title', 'Chart'),
                    x_axis=chart_data.get('x_axis'),
                    y_axis=chart_data.get('y_axis', [])
                ))
        
        return charts
    
    except Exception as e:
        print(f"[ERROR] Chart generation failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_or_create_conversation(session_id: str) -> List[Dict]:
    """Get or create conversation history for a session"""
    if session_id not in conversations:
        conversations[session_id] = []
    return conversations[session_id]


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint - serves the frontend HTML"""
    # Try to serve frontend.html from current directory
    if os.path.exists("frontend.html"):
        return FileResponse("frontend.html")
    elif os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    else:
        return {
            "message": "Analytics Chat API",
            "version": "1.0.0",
            "endpoints": {
                "chat": "/chat",
                "history": "/history/{session_id}",
                "clear": "/clear/{session_id}",
                "frontend": "Place frontend.html in root directory or static/index.html"
            }
        }

def generate_chart_html_from_charts(charts: List[ChartData]) -> str:
    """
    Generate HTML from chart data objects
    Fallback if chart_html not in response
    """
    if not charts:
        return None
    
    chart_htmls = []
    for chart in charts:
        html = f"""
        <div style="text-align: center; margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 10px; background-color: #f9f9f9;">
            <h3 style="color: #333; margin-bottom: 15px;">{chart.title}</h3>
            <img src="data:image/png;base64,{chart.image_data}" alt="{chart.title}" style="max-width: 100%; height: auto; border-radius: 5px;">
        </div>
        """
        chart_htmls.append(html)
    
    return "\n".join(chart_htmls)


@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    Main chat endpoint - processes user queries
    """
    try:
        session_id = message.session_id
        user_input = message.message.strip()
        
        if not user_input:
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        print(f"\n[CHAT] User: {user_input}")
        
        # Get conversation history
        conversation_history = get_or_create_conversation(session_id)
        
        # Build conversation context
        conversation_context = build_conversation_context(conversation_history, user_input)
        
        # Extract tags
        user_tags = detect_query_tags_cached(user_input)
        print(f"[TAGS] {user_tags}")
        
        # Route query
        response = route_query_with_tags(
            user_query=user_input,
            user_tags=user_tags,
            conversation_history=conversation_history,
            conversation_context=conversation_context
        )
        
        print(f"[RESPONSE] Action: {response.get('action')}")
        
        # Handle clarification requests
        if response.get("action") == "clarification_needed":
            return ChatResponse(
                response=response.get("clarification_prompt", "Please clarify your query."),
                suggestions=response.get("suggestions", []),
                metadata={"action": "clarification_needed"}
            )
        
        # Handle errors
        if response.get("action") == "error":
            error_msg = response.get("error", "Unknown error occurred")
            print(f"[ERROR] {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Process successful response
        results_df = response.get("results")
        
        # Remove duplicate columns if DataFrame exists
        if results_df is not None and isinstance(results_df, pd.DataFrame):
            results_df = results_df.loc[:, ~results_df.columns.duplicated()]
        
        insight = response.get("insight") or ""
        
        # Clean up insight text (remove markdown formatting)
        if insight:
            insight = insight.replace('**', '').replace('*', '').replace('#', '').strip()
            if not insight:
                insight = "Query executed successfully."
        else:
            insight = "Query executed successfully."
        
        suggestions = response.get("suggestions", [])
        
        # Convert results to HTML and JSON
        results_html = None
        results_json = None
        charts = []
        chart_html = None  # ← NEW: Initialize chart_html
        
        if results_df is not None and isinstance(results_df, pd.DataFrame) and not results_df.empty:
            print(f"[RESULTS] DataFrame with {len(results_df)} rows")
            
            results_html = dataframe_to_html(results_df)
            results_json = dataframe_to_json(results_df)
            
            # Generate charts using your SmartChartGenerator
            print("[CHARTS] Generating charts...")
            charts = generate_charts(results_df, user_input, user_tags)
            print(f"[CHARTS] Generated {len(charts)} chart(s)")
            
            # ← NEW: Get chart HTML from response if available
            chart_html = response.get("chart_html")
            if not chart_html and charts:
                # Fallback: Generate HTML from chart data if not in response
                chart_html = generate_chart_html_from_charts(charts)
        else:
            print("[RESULTS] No data returned")
        
        # Save to conversation history
        conversation_history.append({
            "user_input": user_input,
            "timestamp": datetime.now().isoformat(),
            "has_results": results_df is not None and not results_df.empty,
            "row_count": len(results_df) if results_df is not None else 0,
            "insight": insight,
            "suggestions": suggestions
        })
        
        # Keep only last 20 turns
        if len(conversation_history) > 20:
            conversation_history.pop(0)
        
        # ← RETURN HERE with chart_html included
        return ChatResponse(
            response=insight,
            results_table=results_html,
            results_data=results_json,
            charts=charts,
            suggestions=suggestions,
            metadata={
                "intent": response.get("intent"),
                "row_count": len(results_df) if results_df is not None else 0,
                "chart_count": len(charts),
                "chart_html": chart_html  # ← NEW: Include in metadata
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Chat endpoint failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/history/{session_id}")
async def get_history(session_id: str):
    """Get conversation history for a session"""
    if session_id not in conversations:
        return {"session_id": session_id, "messages": []}
    
    # Return serializable history
    history = []
    for entry in conversations[session_id]:
        history.append({
            "user_input": entry.get("user_input"),
            "timestamp": entry.get("timestamp"),
            "insight": entry.get("insight"),
            "suggestions": entry.get("suggestions", []),
            "has_results": entry.get("has_results", False),
            "row_count": entry.get("row_count", 0)
        })
    
    return {"session_id": session_id, "messages": history, "count": len(history)}


@app.delete("/clear/{session_id}")
async def clear_history(session_id: str):
    """Clear conversation history for a session"""
    if session_id in conversations:
        del conversations[session_id]
        return {"message": f"History cleared for session: {session_id}"}
    return {"message": f"No history found for session: {session_id}"}


@app.get("/export/{session_id}")
async def export_conversation(session_id: str):
    """Export conversation history as JSON"""
    if session_id not in conversations:
        raise HTTPException(status_code=404, detail="Session not found")
    
    history = conversations[session_id]
    
    export_data = {
        "session_id": session_id,
        "exported_at": datetime.now().isoformat(),
        "conversation_count": len(history),
        "conversation": []
    }
    
    for entry in history:
        export_entry = {
            "user_input": entry.get("user_input"),
            "timestamp": entry.get("timestamp"),
            "sql": entry.get("sql"),
            "insight": entry.get("insight"),
            "suggestions": entry.get("suggestions", []),
            "has_results": entry.get("has_results", False),
            "row_count": entry.get("row_count", 0)
        }
        export_data["conversation"].append(export_entry)
    
    return JSONResponse(content=export_data)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_sessions": len(conversations),
        "total_conversations": sum(len(conv) for conv in conversations.values())
    }


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("🚀 Starting Analytics Chat API Server")
    print("=" * 50)
    print("📍 API: http://localhost:8000")
    print("📍 Frontend: http://localhost:8000")
    print("📍 Docs: http://localhost:8000/docs")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")