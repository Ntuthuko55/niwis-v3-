"""
Example Usage of TrendAnalyzer Class

This script demonstrates how to use the TrendAnalyzer class
directly in Python scripts for batch processing or analysis.
"""

import pandas as pd
from backend.app.trend_analysis import TrendAnalyzer

# Load your climate data
df = pd.read_csv('niwis_daily_climate_master.csv')

# Convert date to datetime
df['date'] = pd.to_datetime(df['date'])

# ============================================================================
# Example 1: Analyze a single province
# ============================================================================

print("=" * 70)
print("EXAMPLE 1: Single Province Analysis")
print("=" * 70)

analyzer = TrendAnalyzer(df, province="Eastern Cape")

# Get available variables
variables = analyzer.get_available_variables()
print(f"\nAvailable variables: {len(variables)}")
print(variables[:5], "...")  # Show first 5

# Analyze rainfall
print("\n" + "-" * 70)
print("Rainfall Trend Analysis for Eastern Cape")
print("-" * 70)

result = analyzer.linear_regression_trend('daily_rainfall')
print(f"Slope: {result['slope']:.6f}")
print(f"P-value: {result['p_value']:.4f}")
print(f"R²: {result['r_squared']:.4f}")
print(f"Trend: {result['trend_direction']}")
print(f"Significance: {result['significance']}")

# ============================================================================
# Example 2: Multiple variables analysis
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 2: Multiple Variables for One Province")
print("=" * 70)

variables_to_analyze = [
    'daily_rainfall',
    'daily_tmean',
    'daily_pet',
    'spi_12m'
]

results_dict = {}

for var in variables_to_analyze:
    try:
        result = analyzer.comprehensive_analysis(var)
        methods = result.pop('methods')
        results_dict[var] = methods
        
        # Extract key metrics
        regression = methods.get('regression', {})
        mk = methods.get('mann_kendall', {})
        
        print(f"\n{var.upper()}")
        print(f"  Linear Regression: slope={regression.get('slope', 'N/A'):.6f}, "
              f"p={regression.get('p_value', 'N/A'):.4f}")
        if mk.get('available'):
            print(f"  Mann-Kendall: trend={mk.get('trend')}, p={mk.get('p_value', 'N/A'):.4f}")
    
    except Exception as e:
        print(f"\nERROR analyzing {var}: {e}")

# ============================================================================
# Example 3: Province comparison
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 3: Province Comparison")
print("=" * 70)

# Compare rainfall trends across all provinces
analyzer_all = TrendAnalyzer(df)  # No province filter
comparison = analyzer_all.province_comparison('daily_rainfall')

print(f"\nRainfall Trend Comparison Across Provinces:")
print("-" * 70)
print(f"{'Province':<25} {'Slope':<12} {'P-value':<12} {'Trend':<15}")
print("-" * 70)

for prov_data in comparison['provinces']:
    print(f"{prov_data['province']:<25} "
          f"{prov_data['slope']:>11.6f} "
          f"{prov_data['p_value']:>11.4f} "
          f"{prov_data['trend']:<15} "
          f"{'*' if prov_data['significant'] else ''}")

# ============================================================================
# Example 4: Extract time series data
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 4: Extract Time Series Data for Plotting")
print("=" * 70)

# Get raw and moving averages
ma_data = analyzer.moving_averages('daily_rainfall', windows=[30, 90, 365])

print(f"\nMoving Average Data:")
print(f"- Dates: {len(ma_data['dates'])} points")
print(f"- Raw values available: {ma_data.get('raw') is not None}")
print(f"- Moving averages: {list(ma_data['moving_averages'].keys())}")

# Get annual aggregates
annual = analyzer.annual_trend('daily_rainfall')
print(f"\nAnnual Aggregate Data:")
print(f"- Years: {len(annual['dates'])}")
print(f"- Mean annual rainfall: {annual['mean']:.2f} mm")
print(f"- Std dev: {annual['std']:.2f} mm")

# ============================================================================
# Example 5: Generate summary report
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 5: Summary Report Generation")
print("=" * 70)

def generate_summary_report(analyzer, variables, province=None):
    """Generate a summary report of trends"""
    
    report = []
    report.append("=" * 80)
    if province:
        report.append(f"TREND ANALYSIS REPORT - {province.upper()}")
    else:
        report.append("TREND ANALYSIS REPORT")
    report.append("=" * 80)
    report.append("")
    
    # Header row
    report.append(f"{'Variable':<25} {'Slope':<12} {'P-value':<12} {'Trend':<20} {'Sig':<5}")
    report.append("-" * 80)
    
    for var in variables:
        try:
            result = analyzer.linear_regression_trend(var)
            sig = "Yes*" if result['p_value'] < 0.05 else "No"
            
            report.append(
                f"{var:<25} "
                f"{result['slope']:>11.6f} "
                f"{result['p_value']:>11.4f} "
                f"{result['trend_direction']:<20} "
                f"{sig:<5}"
            )
        except Exception as e:
            report.append(f"{var:<25} ERROR: {str(e)[:40]}")
    
    report.append("")
    report.append("* Significant at α = 0.05")
    report.append("")
    
    return "\n".join(report)

# Generate report
report_text = generate_summary_report(
    analyzer,
    ['daily_rainfall', 'daily_tmean', 'daily_pet', 'spi_12m'],
    province="Eastern Cape"
)
print(report_text)

# ============================================================================
# Example 6: Process multiple provinces
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 6: Batch Processing Multiple Provinces")
print("=" * 70)

provinces = df['province'].unique()
summary_results = []

print(f"\nProcessing {len(provinces)} provinces...")

for province in provinces:
    try:
        prov_analyzer = TrendAnalyzer(df, province=province)
        
        # Analyze rainfall for this province
        regression = prov_analyzer.linear_regression_trend('daily_rainfall')
        
        summary_results.append({
            'Province': province,
            'Slope': regression['slope'],
            'P_value': regression['p_value'],
            'R_Squared': regression['r_squared'],
            'Significant': regression['p_value'] < 0.05
        })
        
        print(f"  ✓ {province}: slope={regression['slope']:.4f}")
    
    except Exception as e:
        print(f"  ✗ {province}: {str(e)[:30]}")

# Create DataFrame from results
summary_df = pd.DataFrame(summary_results)
summary_df = summary_df.sort_values('Slope')

print("\n" + "-" * 70)
print("SUMMARY TABLE (sorted by slope):")
print("-" * 70)
print(summary_df.to_string(index=False))

# ============================================================================
# Example 7: Export results to CSV
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 7: Export Results to CSV")
print("=" * 70)

# Save summary table
summary_df.to_csv('rainfall_trends_by_province.csv', index=False)
print("\nSaved: rainfall_trends_by_province.csv")

# Save detailed results for one province
detailed = analyzer.comprehensive_analysis('daily_rainfall')
print(f"\nSaved detailed analysis results for {analyzer.province}")
print(f"Available methods: {list(detailed['methods'].keys())}")

# ============================================================================
# Example 8: Time series for visualization
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 8: Extracting Data for Matplotlib/Plotly Visualization")
print("=" * 70)

# Get data suitable for plotting
raw_data = analyzer.raw_time_series('daily_rainfall')
annual_data = analyzer.annual_trend('daily_rainfall')
regression_data = analyzer.linear_regression_trend('daily_rainfall')

print(f"\nRaw time series: {len(raw_data['dates'])} points")
print(f"Annual aggregates: {len(annual_data['dates'])} years")

# Example: Create a simple matplotlib plot
try:
    import matplotlib.pyplot as plt
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8))
    
    # Plot annual trend with regression line
    import datetime
    years = [int(d) for d in annual_data['dates']]
    values = annual_data['annual_values']
    
    ax1.plot(years, values, 'o-', label='Annual Average', markersize=6)
    ax1.set_title('Annual Rainfall Trend')
    ax1.set_ylabel('Rainfall (mm)')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Plot regression line
    years_reg = regression_data['dates']
    trend_line = regression_data['trend_line']
    ax1.plot(years_reg, trend_line, 'r--', linewidth=2, label='Linear Trend')
    ax1.legend()
    
    # Summary text
    ax2.axis('off')
    summary_text = f"""
    Rainfall Trend Analysis - {analyzer.province}
    
    Linear Regression:
      Slope: {regression_data['slope']:.6f} mm/year
      P-value: {regression_data['p_value']:.4f}
      R²: {regression_data['r_squared']:.4f}
      Trend: {regression_data['trend_direction']}
      Significance: {regression_data['significance']}
    """
    ax2.text(0.5, 0.5, summary_text, fontsize=12, family='monospace',
             verticalalignment='center', horizontalalignment='center',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig('rainfall_trend_analysis.png', dpi=150, bbox_inches='tight')
    print(f"\nSaved visualization: rainfall_trend_analysis.png")
    
except ImportError:
    print("\nNote: matplotlib not installed. Install with: pip install matplotlib")

print("\n" + "=" * 70)
print("Examples complete!")
print("=" * 70)
