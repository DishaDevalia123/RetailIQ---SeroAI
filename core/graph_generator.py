# graph_generator.py

import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
import re
import numpy as np
from typing import Dict, List, Optional
import webbrowser
import tempfile
import os
import calendar
from utils import get_df_col_case_insensitive, build_col_metadata

class SmartChartGenerator:
    """
    Enhanced chart generator that uses intent-based routing for automatic visualization selection.
    Now supports multi-chart generation based on the "Smart Charting Rules" discussed.
    """
    def __init__(self):
        self.supported_chart_types = ['line', 'bar', 'pie', 'scatter', 'grouped_bar', 'stacked_bar']
        self.intent_chart_mapping = {
            'comparison': 'bar',
            'comparison_trend': 'grouped_bar',
            'trend': 'line',
            'segment': 'bar',
            'segmentation': 'bar',
            'distribution': 'pie',
            'correlation': 'scatter',
            'analyze': 'bar',
            'performance': 'line',
            'growth': 'line'
        }
        self.chart_keywords = {
            'line': ['trend', 'over time', 'growth', 'change', 'timeline', 'progression'],
            'bar': ['compare', 'versus', 'vs', 'against', 'ranking', 'top', 'bottom'],
            'pie': ['share', 'percentage', 'proportion', 'distribution', 'breakdown', 'composition'],
            'scatter': ['relationship', 'correlation', 'association', 'pattern']
        }
        self.festival_colors = {
            'diwali': '#FF6B35',
            'christmas': '#228B22',
            'holi': '#FF1493',
            'eid': '#4169E1',
            'new year': '#FFD700',
            'valentine': '#FF69B4'
        }
        plt.style.use('default')
        self.default_figsize = (12, 7)
        self.default_dpi = 100
        self.last_metrics: Optional[List[str]] = None

    def create_chart_title(self, entity_col=None, entity_value=None, metric=None, group_by=None, is_temporal=False):
        """Create a descriptive title for charts with better formatting"""
        title_parts = []
        
        # Add specific entity value (most important for filtered charts)
        if entity_value is not None and entity_col:
            entity_label = entity_col.replace('_', ' ').replace('Name', '').strip().title()
            # Clean up entity value for display
            clean_entity_value = str(entity_value).strip()
            title_parts.append(f"{entity_label}: {clean_entity_value}")
        
        # Add metric information
        if metric:
            if isinstance(metric, list):
                if len(metric) == 1:
                    metric_name = metric[0].replace('_', ' ').replace('TOTAL', '').replace('SALE', 'Sales').strip().title()
                    title_parts.append(metric_name)
                elif len(metric) <= 3:
                    metric_names = []
                    for m in metric:
                        clean_name = m.replace('_', ' ').replace('TOTAL', '').replace('SALE', 'Sales').strip().title()
                        metric_names.append(clean_name)
                    title_parts.append(" & ".join(metric_names))
                else:
                    title_parts.append("Performance Metrics")
            else:
                metric_name = metric.replace('_', ' ').replace('TOTAL', '').replace('SALE', 'Sales').strip().title()
                title_parts.append(metric_name)
        
        # Add temporal context
        if is_temporal:
            if 'month' in str(group_by).lower() if group_by else False:
                title_parts.append("Monthly Trend")
            elif 'week' in str(group_by).lower() if group_by else False:
                title_parts.append("Weekly Trend")
            elif 'day' in str(group_by).lower() if group_by else False:
                title_parts.append("Daily Trend")
            else:
                title_parts.append("Trend Analysis")
        
        # Add grouping context
        if group_by and not entity_value:
            group_label = group_by.replace('_', ' ').replace('Name', '').strip().title()
            title_parts.append(f"by {group_label}")
        
        # Create final title
        if title_parts:
            title = " - ".join(title_parts)
            # Ensure title isn't too long
            if len(title) > 60:
                title = title[:57] + "..."
            return title
        else:
            return "Performance Analysis"

    
    
    def detect_chart_hierarchy(self, df, user_tags=None):
        """
        LAYER 2: Data-driven hierarchy detection
        
        Returns:
            dict with 'temporal', 'top_entity', 'secondary_entity', 'all_entities', 'metrics'
        """
        # Step 1: Detect temporal column
        temporal_col = None
        temporal_keywords = ['month', 'week', 'day', 'date', 'time', 'year', 'quarter']
        print(f"[HIERARCHY DEBUG] DataFrame columns and types:")
        for col in df.columns:
            print(f"  {col}: {df[col].dtype} (numeric={pd.api.types.is_numeric_dtype(df[col])})")
            col_lower = col.lower()
            if any(term in col_lower for term in temporal_keywords):
                # Prefer month over year, week over day (more granular)
                if not temporal_col or 'month' in col_lower:
                    temporal_col = col
        
        # Step 2: Detect entity columns (categorical with business meaning)
        entity_keywords = ['store', 'brand', 'sub_brand', 'pattern', 'color', 'division', 'size', 'sleeve']
        entity_cols = []
        
        for col in df.columns:
            col_lower = col.lower()
            # Must match entity keyword AND be categorical
            if any(keyword in col_lower for keyword in entity_keywords):
                if df[col].dtype == 'object' or df[col].nunique() < 20:
                    unique_count = df[col].nunique()
                    entity_cols.append({
                        'name': col,
                        'unique_count': unique_count,
                        'values': df[col].unique().tolist()
                    })
        
        # Sort by unique count (ascending) - fewer values = higher hierarchy
        entity_cols.sort(key=lambda x: x['unique_count'])
        
        # Step 3: Detect metrics (numeric columns, excluding temporal)
        # Step 3: Detect metrics (numeric columns, excluding temporal and entities)
        metrics = []
        entity_col_names = [e['name'] for e in entity_cols]
        for col in df.columns:
            # Skip temporal columns
            if col == temporal_col:
                continue
            
            # Skip entity columns
            if col in entity_col_names:
                continue
            
            # Check if numeric
            if pd.api.types.is_numeric_dtype(df[col]):
                col_lower = col.lower()
                
                # RELAXED exclusion: only exclude obvious non-metrics
                exclude_keywords = ['_id', 'bill_no', 'barcode', 'contact', 'rank']
                
                # IMPORTANT: Don't exclude 'count' - it might be transaction_count which IS a metric
                if not any(exclude in col_lower for exclude in exclude_keywords):
                    metrics.append(col)
                    print(f"  [METRIC FOUND] {col}")
                else:
                    print(f"  [METRIC EXCLUDED] {col} (matched exclusion keyword)")
            else:
                print(f"  [NOT NUMERIC] {col} (dtype={df[col].dtype})")
        
        print(f"[HIERARCHY] Final metrics detected: {metrics}")
        
        # Build hierarchy structure
        hierarchy = {
            'temporal': temporal_col,
            'top_entity': entity_cols[0] if entity_cols else None,
            'secondary_entity': entity_cols[1] if len(entity_cols) > 1 else None,
            'all_entities': entity_cols,
            'metrics': metrics
        }
        
        print(f"[HIERARCHY DETECTION]")
        print(f"  Temporal: {temporal_col}")
        print(f"  Top Entity: {hierarchy['top_entity']['name'] if hierarchy['top_entity'] else None} "
            f"({hierarchy['top_entity']['unique_count']} values)" if hierarchy['top_entity'] else "None")
        print(f"  Secondary: {hierarchy['secondary_entity']['name'] if hierarchy['secondary_entity'] else None}")
        print(f"  Metrics: {metrics}")
        
        return hierarchy
    
    def decide_chart_strategy(self, hierarchy, df):
        """
        LAYER 3: Fixed rules for chart generation based on hierarchy
        
        Returns:
            dict with 'strategy', 'chart_count', 'chart_type', 'plans'
        """
        temporal = hierarchy['temporal']
        top_entity = hierarchy['top_entity']
        secondary_entity = hierarchy['secondary_entity']
        metrics = hierarchy['metrics']
        
        if not metrics:
            print("[STRATEGY] No metrics found - cannot generate charts")
            return {'strategy': 'no_charts', 'chart_count': 0, 'plans': []}
        
        # RULE 1: Top entity with ≤6 unique values → SEPARATE CHARTS
        if top_entity and top_entity['unique_count'] <= 6:
            print(f"[STRATEGY] Separate charts per {top_entity['name']} (≤6 entities)")
            
            plans = []
            for entity_value in top_entity['values']:
                # Determine chart type
                # Determine chart type based on metrics and data characteristics
                if temporal:
                    x_axis = temporal
                    
                    # SMART CHART TYPE SELECTION
                    if len(metrics) == 1:
                        chart_type = 'line'  # Single metric → line chart for trends
                    elif len(metrics) >= 2:
                        chart_type = 'grouped_bar'
                    else:
                        # 3+ metrics + temporal = GROUPED BAR (too many lines get messy)
                        chart_type = 'grouped_bar'
                elif secondary_entity:
                    x_axis = secondary_entity['name']
                    
                    # SMART CHART TYPE for categorical data
                    if len(metrics) == 1:
                        # Single metric = BAR CHART
                        chart_type = 'bar'
                    elif len(metrics) <= 3:
                        # 2-3 metrics = GROUPED BAR
                        chart_type = 'grouped_bar'
                    else:
                        # 4+ metrics = GROUPED BAR (but might need stacking in future)
                        chart_type = 'grouped_bar'
                else:
                    x_axis = 'metric_name'
                    chart_type = 'bar'  # Pivot metrics to x-axis, show as bars
                
                # Create title
                title = self.create_chart_title(
                    entity_col=top_entity['name'],
                    entity_value=str(entity_value),
                    metric=metrics,
                    is_temporal=bool(temporal)
                )
                
                plans.append({
                    'chart_type': chart_type,
                    'x': x_axis,
                    'y': metrics,
                    'group': None,
                    'filter_by': {top_entity['name']: entity_value},
                    'title_suffix': title
                })
            
            return {
                'strategy': 'separate_per_entity',
                'chart_count': len(plans),
                'plans': plans
            }
        
        # RULE 2: Top entity with >6 unique values → SINGLE GROUPED CHART
        # RULE 2: Top entity with >6 unique values → SINGLE GROUPED CHART
        elif top_entity and top_entity['unique_count'] > 6:
            print(f"[STRATEGY] Single grouped chart (>6 entities)")
            
            if temporal:
                x_axis = temporal
                grouping = top_entity['name']
                
                # SMART: Line chart for temporal trends with single metric
                if len(metrics) == 1:
                    chart_type = 'line'  # Multiple lines (one per entity)
                else:
                    chart_type = 'grouped_bar'
            else:
                x_axis = top_entity['name']
                grouping = secondary_entity['name'] if secondary_entity else None
                chart_type = 'grouped_bar'  # Always bar for categorical
            
            title = self.create_chart_title(
                metric=metrics,
                group_by=top_entity['name'],
                is_temporal=bool(temporal)
            )
            
            plans = [{
                'chart_type': chart_type,
                'x': x_axis,
                'y': metrics[0] if len(metrics) == 1 else metrics,
                'group': grouping,
                'filter_by': None,
                'title_suffix': title
            }]
            
            return {
                'strategy': 'single_grouped',
                'chart_count': 1,
                'plans': plans
            }
        
        # RULE 3: Temporal only (no entities)
        elif temporal and not top_entity:
            print(f"[STRATEGY] Simple temporal chart")
            
            chart_type = 'grouped_bar' if len(metrics) > 1 else 'line'
            title = self.create_chart_title(metric=metrics, is_temporal=True)
            
            plans = [{
                'chart_type': chart_type,
                'x': temporal,
                'y': metrics,
                'group': None,
                'filter_by': None,
                'title_suffix': title
            }]
            
            return {
                'strategy': 'simple_temporal',
                'chart_count': 1,
                'plans': plans
            }
        
        # RULE 4: Fallback - generic bar chart
        else:
            print(f"[STRATEGY] Fallback bar chart")
            
            x_axis = df.columns[0]
            title = self.create_chart_title(metric=metrics)
            
            plans = [{
                'chart_type': 'grouped_bar' if len(metrics) > 1 else 'bar',
                'x': x_axis,
                'y': metrics,
                'group': None,
                'filter_by': None,
                'title_suffix': title
            }]
            
            return {
                'strategy': 'fallback',
                'chart_count': 1,
                'plans': plans
            }
    

    def _validate_and_map_metrics(self, df, llm_metrics, detected_metrics):
        """
        Map LLM metric names to actual DataFrame columns
        Handles cases like: LLM says 'SALE_QUANTITY' but df has 'total_units'
        """
        METRIC_ALIASES = {
            'SALE_QUANTITY': ['total_units', 'units', 'quantity', 'sale_quantity'],
            'TOTAL_AMOUNT': ['total_revenue', 'revenue', 'total_amount', 'amount'],
            'AVG_SALE': ['avg_sale', 'avg_transaction_value', 'average_sale'],
            'DISCOUNT_AMOUNT': ['total_discount', 'discount', 'discount_amount']
        }
        
        actual_metrics = []
        
        # First, try to map LLM metrics
        if llm_metrics:
            for llm_metric in llm_metrics:
                # Try exact match (case-insensitive)
                for df_col in df.columns:
                    if df_col.lower() == llm_metric.lower():
                        actual_metrics.append(df_col)
                        break
                else:
                    # Try aliases
                    metric_upper = llm_metric.upper()
                    if metric_upper in METRIC_ALIASES:
                        for alias in METRIC_ALIASES[metric_upper]:
                            for df_col in df.columns:
                                if df_col.lower() == alias.lower():
                                    actual_metrics.append(df_col)
                                    break
                            if df_col in actual_metrics:
                                break
        
        # If no match, use detected metrics from DataFrame
        if not actual_metrics:
            actual_metrics = detected_metrics
        
        print(f"[METRIC MAPPING] LLM: {llm_metrics} → Actual: {actual_metrics}")
        return actual_metrics
    
    def generate_charts_from_tags(self, df: pd.DataFrame, user_query: str, user_tags: Dict, col_metadata: Dict = None) -> Optional[List[Dict]]:
        """
        ENTRY POINT: Generate charts using 3-layer system
        """
        if df.empty or (len(df) == 1 and len(df.columns) == 1):
            print("[CHARTS] DataFrame too small for charting")
            return None
        
        # LAYER 1: Get LLM intent (from tags)
        llm_metrics = user_tags.get('metric', []) if user_tags else []
        
        # LAYER 2: Detect hierarchy from actual data
        hierarchy = self.detect_chart_hierarchy(df, user_tags)
        
        # Validate and fix metrics
        actual_metrics = self._validate_and_map_metrics(df, llm_metrics, hierarchy['metrics'])
        hierarchy['metrics'] = actual_metrics  # Update with validated metrics
        
        if not actual_metrics:
            print("[CHARTS] No valid metrics found after validation")
            return None
        
        # LAYER 3: Decide chart strategy
        strategy = self.decide_chart_strategy(hierarchy, df)
        
        if strategy['chart_count'] == 0:
            print("[CHARTS] Strategy returned 0 charts")
            return None
        
        # Execute chart plans
        results = []
        for plan in strategy['plans']:
            try:
                chart = self._execute_chart_plan(df, plan, user_query, user_tags)
                if chart:
                    results.append(chart)
            except Exception as e:
                print(f"[CHART ERROR] Failed to generate chart: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"[CHARTS] Successfully generated {len(results)} chart(s)")
        return results if results else None
    
    def _execute_chart_plan(self, df, plan, user_query, user_tags):
        """
        Execute a single chart plan (with filtering if needed)
        """
        # Apply filter if specified
        if plan.get('filter_by'):
            filter_col, filter_value = list(plan['filter_by'].items())[0]
            filtered_df = df[df[filter_col] == filter_value].copy()
            
            if filtered_df.empty:
                print(f"[CHART SKIP] No data for {filter_col}={filter_value}")
                return None
        else:
            filtered_df = df.copy()
        
        chart_type = plan['chart_type']
        x = plan['x']
        y = plan['y']
        group = plan.get('group')
        title = plan.get('title_suffix', '')
        
        # Route to appropriate chart generator
        if chart_type == 'line':
            return self._generate_line_chart(filtered_df, user_query, user_tags, x=x, y=y, group=group, title_suffix=title)
        elif chart_type == 'grouped_bar':
            return self._generate_grouped_bar_chart(filtered_df, user_query, user_tags, x=x, y=y, group=group, title_suffix=title)
        elif chart_type == 'bar':
            return self._generate_bar_chart(filtered_df, user_query, user_tags, x=x, y=y, group=group, title_suffix=title)
        else:
            print(f"[CHART ERROR] Unknown chart type: {chart_type}")
            return None

        
    def detect_x_axis_col(df: pd.DataFrame, user_tags: dict = None) -> str:

        # 1. Prefer temporal columns if present
        temporal_names = ['month', 'BILL_DATE', 'date', 'year', 'week', 'day']
        for col in df.columns:
            if any(t in col.lower() for t in temporal_names):
                return col
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                return col
        # 2. If no temporal, use entity columns (brand, store, etc.)
        entity_names = ['brand', 'sub_brand', 'store', 'pattern', 'item_division', 'color', 'size', 'sleeve']
        if user_tags:
            for ent in entity_names:
                values = user_tags.get(ent, [])
                if values and ent.replace('_', ' ').title() in df.columns:
                    return ent.replace('_', ' ').title()
        # 3. Else just use first categorical column
        for col in df.columns:
            if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_categorical_dtype(df[col]):
                return col
        # 4. Fallback: first column
        return df.columns[0]

    def _generate_line_chart(self, df, user_query, user_tags, x=None, y=None, group=None, title_suffix=""):
        """
        Generate a line chart for trends and time series.
        """
        if not x:
            x = df.columns[0]
        if not y:
            y = self._identify_numeric_columns(df)[0]
        if isinstance(y, list):
            # Multiple metrics, plot all
            y_cols = y
        else:
            y_cols = [y]
        plot_x = self._format_time_x_axis(df, x)

        # NEW: Support for grouped line charts (multiple series)
        if group and group in df.columns:
            # Multiple lines - one per group value
            fig, ax = plt.subplots(figsize=self.default_figsize, dpi=self.default_dpi)
            
            group_values = df[group].unique()
            colors = plt.cm.tab10(np.linspace(0, 1, len(group_values)))
            
            for i, group_val in enumerate(group_values):
                group_df = df[df[group] == group_val]
                plot_x_grouped = self._format_time_x_axis(group_df, x)
                
                for y_col in y_cols:
                    label = f"{group_val}" if len(y_cols) == 1 else f"{group_val} - {y_col}"
                    ax.plot(plot_x_grouped, group_df[y_col], 
                        marker='o', linestyle='-', 
                        label=label, 
                        linewidth=2, markersize=5,
                        color=colors[i % len(colors)])
            
            ax.set_xlabel(x)
            ax.set_ylabel(' & '.join(y_cols))
            
            if title_suffix:
                chart_title = title_suffix
            else:
                chart_title = self._generate_smart_title(user_query, user_tags, 'Trend')
            
            ax.set_title(chart_title, fontsize=14, fontweight='bold')
            ax.legend(loc='best', fontsize=9)
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            img_data = self._fig_to_base64(fig)
            plt.close(fig)
            
            return {
                'chart_type': 'line',
                'image_data': img_data,
                'title': ax.get_title(),
                'x_axis': x,
                'y_axis': y_cols
            }
        
        # ORIGINAL CODE: Simple line chart (no grouping)
        fig, ax = plt.subplots(figsize=self.default_figsize, dpi=self.default_dpi)
        for col in y_cols:
            ax.plot(plot_x, df[col], marker='o', linestyle='-', label=col, linewidth=2, markersize=6)
            for x_val, y_val in zip(plot_x, df[col]):
                ax.annotate(f"{y_val:.0f}", (x_val, y_val), textcoords="offset points", xytext=(0,7), ha='center', fontsize=10)
        ax.set_xlabel(x)
        ax.set_ylabel(' & '.join(y_cols))
        # ax.set_title(self._generate_smart_title(user_query, user_tags, title_suffix or 'Trend'), fontsize=14, fontweight='bold')
        if title_suffix:
            chart_title = title_suffix
        else:
            chart_title = self._generate_smart_title(user_query, user_tags, 'Trend')
        ax.set_title(chart_title, fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        img_data = self._fig_to_base64(fig)
        plt.close(fig)
        return {
            'chart_type': 'line',
            'image_data': img_data,
            'title': ax.get_title(),
            'x_axis': x,
            'y_axis': y_cols
        }

    def _generate_grouped_bar_chart(
    self, df, user_query, user_tags, x=None, y=None, group=None, title_suffix=""
):
        plot_df = df.copy()
        
        # If Store_Name in columns, make 1 chart per store
        if "Store_Name" in plot_df.columns:
            results = []
            store_vals = plot_df["Store_Name"].unique()
            
            # Determine the best x-axis column from remaining categorical columns
            remaining_cols = [col for col in plot_df.columns if col != "Store_Name"]
            categorical_cols = [col for col in remaining_cols if col.upper() in [
                'Brand', 'Sub_brand', 'Pattern', 'Color', 'Item_division', 
                'Size', 'Sleeve'
            ]]
            
            # Choose the best x-axis column
            if x and x in remaining_cols:
                x_axis_col = x
            elif categorical_cols:
                # Priority order for categorical columns
                priority_order = ['Brand', 'Sub_brand', 'Pattern', 'Color', 'Item_division', 
                'Size', 'Sleeve']
                x_axis_col = None
                for prio_col in priority_order:
                    matching_col = next((col for col in categorical_cols if col.upper() == prio_col), None)
                    if matching_col:
                        x_axis_col = matching_col
                        break
                if not x_axis_col:
                    x_axis_col = categorical_cols[0]
            else:
                x_axis_col = remaining_cols[0]
            
            for store in store_vals:
                store_df = plot_df[plot_df["Store_Name"] == store]
                chart_title = f"Store: {store} - {title_suffix or self._generate_smart_title(user_query, user_tags, 'Grouped Bar')}"
                results.append(
                    self._generate_grouped_bar_chart(
                        store_df.drop(columns="Store_Name"),
                        user_query,
                        user_tags,
                        x=x_axis_col,  # Use dynamically determined column
                        y=y,
                        group=None,
                        title_suffix=chart_title,
                    )
                )
            return results if len(results) > 1 else results[0]

        # Determine x-axis column with flexible matching
        if x:
            x_col = get_df_col_case_insensitive(plot_df, x) if x else plot_df.columns[0]
        else:
            # Auto-detect best categorical column for x-axis
            categorical_cols = [col for col in plot_df.columns if col.upper() in [
                'BRAND', 'SUB_BRAND', 'PATTERN', 'COLOR', 'COLOUR', 'ITEM_DIVISION', 
                'SIZE', 'SLEEVE', 'CATEGORY', 'SUBCATEGORY'
            ]]
            
            if categorical_cols:
                priority_order = ['SUB_BRAND', 'BRAND', 'PATTERN', 'COLOR', 'COLOUR', 'ITEM_DIVISION', 'SIZE', 'SLEEVE']
                x_col = None
                for prio_col in priority_order:
                    matching_col = next((col for col in categorical_cols if col.upper() == prio_col), None)
                    if matching_col:
                        x_col = matching_col
                        break
                if not x_col:
                    x_col = categorical_cols[0]
            else:
                x_col = plot_df.columns[0]
        
        # Handle multiple metrics case
        if isinstance(y, list) and len(y) > 1:
            # FIX: Find actual columns in DataFrame that match the metric intent
            actual_y_cols = []
            METRIC_ALIASES = {
                'SALE_QUANTITY': ['total_units', 'units', 'quantity', 'sale_quantity'],
                'TOTAL_AMOUNT': ['total_revenue', 'revenue', 'total_amount', 'amount'],
            }
            
            for metric in y:
                # Try exact match first
                if metric in df.columns:
                    actual_y_cols.append(metric)
                else:
                    # Try aliases
                    metric_upper = metric.upper()
                    found = False
                    for canonical, aliases in METRIC_ALIASES.items():
                        if metric_upper == canonical:
                            for alias in aliases:
                                matching_col = get_df_col_case_insensitive(plot_df, alias)
                                if matching_col:
                                    actual_y_cols.append(matching_col)
                                    found = True
                                    break
                        if found:
                            break
                    
                    # If still not found, try partial match
                    if not found:
                        for col in plot_df.columns:
                            if metric.lower() in col.lower() or col.lower() in metric.lower():
                                actual_y_cols.append(col)
                                break
            
            if not actual_y_cols:
                # Fallback: use all numeric columns
                actual_y_cols = [col for col in plot_df.columns if pd.api.types.is_numeric_dtype(plot_df[col])]
            
            # Now melt with actual column names
            plot_df = pd.melt(
                plot_df,
                id_vars=[x_col],
                value_vars=actual_y_cols,  # ← Use actual column names
                var_name="metric_name",
                value_name="value"
            )
            group_col = "metric_name"
            y_col = "value"
        else:
            # Single metric case
            y_col = y[0] if isinstance(y, list) else y
            group_col = get_df_col_case_insensitive(plot_df, group) if group else None

        # Get unique values for grouping
        x_labels = plot_df[x_col].unique()
        groups = plot_df[group_col].unique() if group_col and group_col in plot_df.columns else ["all"]
        
        # Set up the bar chart
        x_pos = np.arange(len(x_labels))
        bar_width = 0.8 / len(groups)
        fig, ax = plt.subplots(figsize=self.default_figsize, dpi=self.default_dpi)
        colors = plt.cm.Paired(np.linspace(0, 1, len(groups)))

        # Create bars for each group
        for i, group_name in enumerate(groups):
            if group_col and group_col in plot_df.columns:
                data = plot_df[plot_df[group_col] == group_name]
            else:
                data = plot_df
                
            y_vals = []
            for x_val in x_labels:
                row = data[data[x_col] == x_val]
                y_val = row[y_col].values[0] if not row.empty else 0
                y_vals.append(y_val)
                
            offset = (i - len(groups) / 2 + 0.5) * bar_width
            bars = ax.bar(x_pos + offset, y_vals, bar_width, label=str(group_name), color=colors[i % len(colors)])
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.annotate(f"{height:.0f}", (bar.get_x() + bar.get_width() / 2, height),
                                ha="center", va="bottom", fontsize=10)

        # Set labels and title
        ax.set_xticks(x_pos)
        ax.set_xticklabels(x_labels, rotation=45, ha="right")
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_title(title_suffix or self._generate_smart_title(user_query, user_tags, "Grouped Bar"), fontsize=14, fontweight="bold")
        
        # Add legend if there are multiple groups
        if len(groups) > 1:
            ax.legend(title=group_col)
        
        ax.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        
        img_data = self._fig_to_base64(fig)
        plt.close(fig)
        
        return {
            "chart_type": "grouped_bar",
            "image_data": img_data,
            "title": ax.get_title(),
            "x_axis": x_col,
            "y_axis": [y_col],
            "legend": group_col,
        }


    def _generate_bar_chart(self, df, user_query, user_tags, x=None, y=None, group=None, title_suffix=""):
        """
        Generate a simple bar chart.
        """
        plot_df = df.copy()
        if not x:
            x = df.columns[0]
        if not y:
            y = self._identify_numeric_columns(df)[0]
        x_vals = self._format_time_x_axis(plot_df, x) if x else np.arange(len(plot_df))
        y_vals = plot_df[y]
        fig, ax = plt.subplots(figsize=self.default_figsize, dpi=self.default_dpi)
        bars = ax.bar(x_vals, y_vals, color='#1f77b4')
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(f"{height:.0f}", (bar.get_x() + bar.get_width() / 2, height),
                            ha='center', va='bottom', fontsize=10)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        #ax.set_title(self._generate_smart_title(user_query, user_tags, title_suffix or 'Bar'), fontsize=14, fontweight='bold')
        if title_suffix:
            chart_title = title_suffix
        else:
            chart_title = self._generate_smart_title(user_query, user_tags, 'Bar')
        ax.set_title(chart_title, fontsize=14, fontweight='bold')

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        img_data = self._fig_to_base64(fig)
        plt.close(fig)
        return {
            'chart_type': 'bar',
            'image_data': img_data,
            'title': ax.get_title(),
            'x_axis': x,
            'y_axis': [y]
        }

    def _format_time_x_axis(self, df: pd.DataFrame, x_column: str):
        """
        Format temporal columns for better display
        Handles: month numbers, dates, weeks, etc.
        """
        if pd.api.types.is_datetime64_any_dtype(df[x_column]):
            return df[x_column].dt.strftime("%b")
        
        col_lower = x_column.lower()
        
        # MONTH FORMATTING
        if "month" in col_lower:
            month_names = {
                1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
                '1': 'Jan', '2': 'Feb', '3': 'Mar', '4': 'Apr', '5': 'May', '6': 'Jun',
                '7': 'Jul', '8': 'Aug', '9': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
            }
            
            def format_month(val):
                try:
                    # Handle integer months
                    if isinstance(val, (int, np.integer)):
                        return month_names.get(val, str(val))
                    
                    # Handle string months
                    if isinstance(val, str):
                        val_stripped = val.strip()
                        # Already a month name?
                        if val_stripped in month_names.values():
                            return val_stripped
                        # Numeric string?
                        if val_stripped.isdigit():
                            return month_names.get(val_stripped, val_stripped)
                        # YYYY-MM format?
                        m = re.match(r"\s*\d{4}[-/](\d{1,2})\s*$", val_stripped)
                        if m:
                            month_num = m.group(1)
                            return month_names.get(int(month_num), val_stripped)
                    
                    # Fallback
                    return str(val)
                except:
                    return str(val)
            
            return df[x_column].apply(format_month)
        
        # WEEK FORMATTING
        if "week" in col_lower:
            return df[x_column].apply(lambda w: f"Wk{int(w)}" if pd.notna(w) else str(w))
        
        # DATE/DAY FORMATTING
        if "day" in col_lower or "date" in col_lower:
            if pd.api.types.is_datetime64_any_dtype(df[x_column]):
                return df[x_column].dt.strftime("%d-%b")
            return df[x_column].astype(str)
        
        # QUARTER FORMATTING
        if "quarter" in col_lower:
            return df[x_column].apply(lambda q: f"Q{int(q)}" if pd.notna(q) else str(q))
        
        # Default: return as-is
        return df[x_column]



    def _generate_smart_title(self, user_query: str, user_tags: Dict, default_prefix: str) -> str:
        """Generate contextually appropriate title."""
        title_parts = []
        if user_tags.get('festival_present'):
            festivals = user_tags.get('festivals', [])
            festival_names = [f['festival'].title() for f in festivals]
            if len(festival_names) > 1:
                title_parts.append(' vs '.join(festival_names))
            else:
                title_parts.append(festival_names[0])
        metrics = user_tags.get('metric', [])
        if metrics:
            if 'SALE_QUANTITY' in metrics and 'TOTAL_AMOUNT' in metrics:
                title_parts.append('Sales Performance')
            elif 'SALE_QUANTITY' in metrics:
                title_parts.append('Sales Quantity')
            elif 'TOTAL_AMOUNT' in metrics:
                title_parts.append('Revenue')
        entities = []
        for entity_type in ['brand', 'sub_brand', 'store']:
            if user_tags.get(f'{entity_type}_present'):
                entities.extend(user_tags.get(entity_type, []))
        if entities:
            title_parts.append('by ' + ', '.join(entities[:2]))
        if title_parts:
            title = ' - '.join(title_parts)
        else:
            clean_query = re.sub(r'[^\w\s]', '', user_query).strip()
            words = clean_query.split()[:6]
            title = ' '.join(words).title() if words else default_prefix
        return title

    def _fig_to_base64(self, fig):
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        return img_str

    def _identify_numeric_columns(self, df: pd.DataFrame) -> List[str]:
        return [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]

    def _identify_categorical_columns(self, df: pd.DataFrame) -> List[str]:
        categorical_columns = []
        for col in df.columns:
            if (pd.api.types.is_categorical_dtype(df[col]) or 
                pd.api.types.is_object_dtype(df[col]) or
                (pd.api.types.is_integer_dtype(df[col]) and len(df[col].unique()) < min(20, len(df) / 2))):
                categorical_columns.append(col)
        return categorical_columns

    def display_chart_html(self, chart_data: Dict) -> str:
        if not chart_data or 'image_data' not in chart_data:
            return "<p>No chart could be generated for this data.</p>"
        img_data = chart_data['image_data']
        title = chart_data.get('title', 'Chart')
        html = f"""
        <div style="text-align: center; margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 10px; background-color: #f9f9f9;">
            <h2 style="color: #333; margin-bottom: 15px;">{title}</h2>
            <img src="data:image/png;base64,{img_data}" alt="{title}" style="max-width: 100%; height: auto; border-radius: 5px;">
            <p style="color: #666; font-size: 12px; margin-top: 10px;">
                Chart Type: {chart_data.get('chart_type', 'Unknown').title()}
            </p>
        </div>
        """
        return html

    def show_chart_in_browser(self, chart_datas: List[Dict]):
        if not chart_datas:
            print("No chart data to display.")
            return None
        chart_htmls = "\n".join([self.display_chart_html(cd) for cd in chart_datas])
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Chart Visualization</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                .container {{ max-width: 1000px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            </style>
        </head>
        <body>
            <div class="container">
                {chart_htmls}
            </div>
        </body>
        </html>
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        temp_file.write(html_content.encode('utf-8'))
        temp_file.close()
        webbrowser.open('file://' + os.path.abspath(temp_file.name))
        return os.path.abspath(temp_file.name)

# Helper function for easy integration
def generate_chart_for_query_result(df: pd.DataFrame, user_query: str, user_tags: Dict, col_metadata: Dict = None, chart_context: Dict = None) -> Optional[List[Dict]]:
    generator = SmartChartGenerator()
    # Inject conversation memory if provided
    if chart_context and chart_context.get('last_metrics'):
        generator.last_metrics = chart_context.get('last_metrics')
    return generator.generate_charts_from_tags(df, user_query, user_tags, col_metadata=col_metadata)

def display_chart_for_query_result(df: pd.DataFrame, user_query: str, user_tags: Dict, col_metadata: Dict = None, show_in_browser: bool = True, return_html: bool = False, chart_context: Dict = None, conversation_history: List[Dict] = None):
    """
    NEW PARAMETER:
        return_html (bool): If True, returns HTML string instead of opening browser
    """
    chart_datas = generate_chart_for_query_result(df, user_query, user_tags, col_metadata=col_metadata)
    
    if not chart_datas:
        print("\n📊 No suitable chart could be generated for this data.")
        return None if return_html else None
    
    generator = SmartChartGenerator()
    
    # NEW: inject context if given
    if chart_context and chart_context.get('last_metrics'):
        generator.last_metrics = chart_context.get('last_metrics')

    
    # NEW: Return HTML for embedding in web interface
    if return_html:
        chart_htmls = "\n".join([generator.display_chart_html(cd) for cd in chart_datas])
        full_html = f"""
        <div class="charts-container" style="max-width: 1000px; margin: 20px auto;">
            {chart_htmls}
        </div>
        """
        return full_html
    
    # OLD: Open in browser
    if show_in_browser:
        temp_file = generator.show_chart_in_browser(chart_datas)
        print(f"\n📊 Chart(s) displayed in browser: {temp_file}")
    else:
        for chart_data in chart_datas:
            html = generator.display_chart_html(chart_data)
            print(f"\n📊 Chart HTML generated:")
            print(html)
    
    return None

if __name__ == "__main__":
    # Test the chart generator
    test_data = {
        'month': ['2024-02', '2024-03', '2024-04', '2024-05', '2024-06'],
        'Brand': ['Blackberrys', 'Park Avenue', 'Blackberrys', 'Park Avenue', 'Blackberrys'],
        'sale_qty': [3, 1, 3, 1, 1],
        'total_sales': [5312.28, 912, 5753.55, 1567, 736.11]
    }
    test_df = pd.DataFrame(test_data)
    test_query = "monthly sale trend of blackberry and parc avene"
    test_tags = {
        'metric': ['sale_qty', 'total_sales'],
        'brand_present': True,
        'brand': ['Blackberrys', 'Park Avenue'],
        'brand_count': 2,
        'intent': 'comparison_trend'
    }
    display_chart_for_query_result(test_df, test_query, test_tags, show_in_browser=True)