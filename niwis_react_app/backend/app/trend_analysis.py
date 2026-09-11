"""
Advanced Trend Analysis for Climate Data
Supports multiple methods: moving averages, linear regression, Mann-Kendall test, LOWESS
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy.stats import linregress
import warnings

warnings.filterwarnings('ignore')

# Try to import pymannkendall for Mann-Kendall test
try:
    import pymannkendall as mk
    HAS_MK = True
except ImportError:
    HAS_MK = False

# Try to import statsmodels for LOWESS
try:
    from statsmodels.nonparametric.smoothers_lowess import lowess
    HAS_LOWESS = True
except ImportError:
    HAS_LOWESS = False


def safe_json_list(data):
    """Convert numpy/pandas data to JSON-safe list"""
    if data is None:
        return None
    if isinstance(data, (pd.Series, pd.Index)):
        data = data.tolist()
    if isinstance(data, np.ndarray):
        data = data.tolist()
    
    result = []
    for val in data:
        if pd.isna(val):
            result.append(None)
        elif isinstance(val, (np.integer, int)):
            result.append(int(val))
        elif isinstance(val, (np.floating, float)):
            result.append(float(val))
        else:
            result.append(val)
    return result


class TrendAnalyzer:
    """Comprehensive trend analyzer for climate time series"""
    
    def __init__(self, df: pd.DataFrame, province: Optional[str] = None, date_col: str = 'date'):
        """
        Initialize analyzer
        
        Parameters:
        -----------
        df : pd.DataFrame
            Full dataset with date and numeric columns
        province : str, optional
            Filter by province
        date_col : str
            Name of date column
        """
        self.df = df.copy()
        self.province = province
        self.date_col = date_col
        
        # Filter by province if specified
        if province:
            self.df = self.df[self.df['province'] == province].copy()
        
        # Ensure date column is datetime
        if date_col in self.df.columns:
            self.df[date_col] = pd.to_datetime(self.df[date_col])
            self.df = self.df.sort_values(date_col)
            self.df.set_index(date_col, inplace=True)
        
        self.climate_variables = [
            'daily_rainfall', 'rain_anomaly_mm', 'rain_intensity_mm_h',
            'daily_tmin', 'daily_tmax', 'daily_tmean', 'temp_anomaly_c',
            'daily_pet', 'daily_et0', 'daily_relative_humidity',
            'solar_radiation_w_m2', 'wind_speed_2m',
            'spi_1m', 'spi_3m', 'spi_6m', 'spi_12m', 'spi_24m',
            'spei_1m', 'spei_3m', 'spei_6m', 'spei_12m', 'spei_24m'
        ]
    
    def get_available_variables(self) -> List[str]:
        """Get list of available climate variables in dataset"""
        available = []
        for var in self.climate_variables:
            if var in self.df.columns and self.df[var].notna().sum() > 0:
                available.append(var)
        return available
    
    def raw_time_series(self, variable: str, resample_freq: Optional[str] = None) -> Dict:
        """
        Get raw time series data
        
        Parameters:
        -----------
        variable : str
            Climate variable to analyze
        resample_freq : str, optional
            Resample frequency (e.g., 'M' for monthly, 'Y' for yearly)
        """
        if variable not in self.df.columns:
            raise ValueError(f"Variable '{variable}' not found in dataset")
        
        series = self.df[variable].dropna()
        
        if resample_freq:
            series = series.resample(resample_freq).mean()
        
        return {
            'dates': safe_json_list(series.index.strftime('%Y-%m-%d').tolist()),
            'values': safe_json_list(series.values),
            'count': len(series),
            'mean': float(series.mean()),
            'std': float(series.std()),
            'min': float(series.min()),
            'max': float(series.max())
        }
    
    def moving_averages(self, variable: str, windows: List[int] = None) -> Dict:
        """
        Calculate moving averages
        
        Parameters:
        -----------
        variable : str
            Climate variable
        windows : List[int]
            Window sizes for moving average (default: [30, 90, 365])
        """
        if windows is None:
            windows = [30, 90, 365]
        
        if variable not in self.df.columns:
            raise ValueError(f"Variable '{variable}' not found")
        
        series = self.df[variable].dropna()
        dates = safe_json_list(series.index.strftime('%Y-%m-%d').tolist())
        
        result = {
            'dates': dates,
            'raw': safe_json_list(series.values),
            'moving_averages': {}
        }
        
        for window in windows:
            if len(series) >= window:
                ma = series.rolling(window=window, center=False).mean()
                result['moving_averages'][f'{window}d'] = safe_json_list(ma.values)
        
        return result
    
    def annual_trend(self, variable: str) -> Dict:
        """
        Compute annual averages and trend
        
        Parameters:
        -----------
        variable : str
            Climate variable
        """
        if variable not in self.df.columns:
            raise ValueError(f"Variable '{variable}' not found")
        
        series = self.df[variable]
        annual = series.resample('Y').mean()
        
        dates = safe_json_list(annual.index.strftime('%Y').tolist())
        values = safe_json_list(annual.values)
        
        return {
            'dates': dates,
            'annual_values': values,
            'count': len(annual),
            'mean': float(annual.mean()),
            'std': float(annual.std())
        }
    
    def linear_regression_trend(self, variable: str) -> Dict:
        """
        Fit linear regression trend line
        
        Parameters:
        -----------
        variable : str
            Climate variable
        """
        if variable not in self.df.columns:
            raise ValueError(f"Variable '{variable}' not found")
        
        series = self.df[variable]
        annual = series.resample('Y').mean()
        
        # Remove NaN values
        annual_clean = annual.dropna()
        
        if len(annual_clean) < 2:
            raise ValueError("Not enough data for regression")
        
        x = np.arange(len(annual_clean))
        y = annual_clean.values
        
        # Linear regression
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        
        # Calculate trend line
        trend_line = intercept + slope * x
        
        # Interpretation
        if p_value < 0.05:
            trend_direction = "Decreasing" if slope < 0 else "Increasing"
            significance = "Significant"
        else:
            trend_direction = "Stable"
            significance = "Not significant"
        
        result = {
            'dates': safe_json_list(annual_clean.index.strftime('%Y').tolist()),
            'values': safe_json_list(y),
            'trend_line': safe_json_list(trend_line),
            'slope': float(slope),
            'intercept': float(intercept),
            'r_squared': float(r_value ** 2),
            'p_value': float(p_value),
            'std_err': float(std_err),
            'trend_direction': trend_direction,
            'significance': significance
        }
        
        return result
    
    def mann_kendall_test(self, variable: str) -> Dict:
        """
        Perform Mann-Kendall trend test (non-parametric)
        
        Parameters:
        -----------
        variable : str
            Climate variable
        """
        if not HAS_MK:
            return {
                'error': 'pymannkendall not installed. Install with: pip install pymannkendall',
                'available': False
            }
        
        if variable not in self.df.columns:
            raise ValueError(f"Variable '{variable}' not found")
        
        series = self.df[variable]
        annual = series.resample('Y').mean().dropna()
        
        if len(annual) < 3:
            raise ValueError("Not enough data for Mann-Kendall test (need minimum 3 points)")
        
        # Perform Mann-Kendall test
        result_mk = mk.original_test(annual.values)
        
        result = {
            'available': True,
            'trend': result_mk.trend,
            'p_value': float(result_mk.p),
            'slope': float(result_mk.slope),
            'intercept': float(result_mk.intercept),
            'count': len(annual),
            'significance': 'Significant' if result_mk.p < 0.05 else 'Not significant',
            'interpretation': {
                'p_value_threshold': 0.05,
                'p_less_than_threshold': result_mk.p < 0.05,
                'trend_strength': 'Strong' if abs(result_mk.slope) > 0.1 else 'Weak'
            }
        }
        
        return result
    
    def lowess_trend(self, variable: str, frac: float = 0.05) -> Dict:
        """
        LOWESS (Locally Weighted Scatterplot Smoothing) non-linear trend
        
        Parameters:
        -----------
        variable : str
            Climate variable
        frac : float
            Fraction of data for LOWESS window (default: 0.05)
        """
        if not HAS_LOWESS:
            return {
                'error': 'statsmodels not installed. Install with: pip install statsmodels',
                'available': False
            }
        
        if variable not in self.df.columns:
            raise ValueError(f"Variable '{variable}' not found")
        
        series = self.df[variable].dropna()
        
        if len(series) < 3:
            raise ValueError("Not enough data for LOWESS")
        
        x = np.arange(len(series))
        y = series.values
        
        # Apply LOWESS
        smoothed = lowess(y, x, frac=frac)
        
        result = {
            'available': True,
            'dates': safe_json_list(series.index.strftime('%Y-%m-%d').tolist()),
            'raw_values': safe_json_list(y),
            'lowess_values': safe_json_list(smoothed[:, 1]),
            'frac': frac
        }
        
        return result
    
    def province_comparison(self, variable: str, provinces: Optional[List[str]] = None) -> Dict:
        """
        Compare trends across provinces
        
        Parameters:
        -----------
        variable : str
            Climate variable
        provinces : List[str], optional
            List of provinces to compare (if None, use all available)
        """
        if variable not in self.df.columns:
            raise ValueError(f"Variable '{variable}' not found")
        
        # Get original full dataset
        df_all = self.df if self.province is None else pd.read_csv(self.df.index.name or 'data.csv')
        if 'province' not in df_all.columns:
            return {'error': 'Province column not found in dataset'}
        
        if provinces is None:
            provinces = df_all['province'].unique()
        
        comparison_results = []
        
        for prov in provinces:
            df_prov = df_all[df_all['province'] == prov].copy()
            if 'date' in df_prov.columns:
                df_prov['date'] = pd.to_datetime(df_prov['date'])
                df_prov.set_index('date', inplace=True)
            
            series = df_prov[variable]
            annual = series.resample('Y').mean().dropna()
            
            if len(annual) >= 2:
                x = np.arange(len(annual))
                y = annual.values
                slope, intercept, r_value, p_value, std_err = linregress(x, y)
                
                comparison_results.append({
                    'province': prov,
                    'slope': float(slope),
                    'p_value': float(p_value),
                    'r_squared': float(r_value ** 2),
                    'n_years': len(annual),
                    'trend': 'Increasing' if slope > 0 else 'Decreasing',
                    'significant': p_value < 0.05
                })
        
        # Sort by slope (strongest trend first)
        comparison_results.sort(key=lambda x: abs(x['slope']), reverse=True)
        
        return {
            'variable': variable,
            'provinces': comparison_results,
            'count': len(comparison_results)
        }
    
    def comprehensive_analysis(self, variable: str) -> Dict:
        """
        Perform comprehensive trend analysis including all methods
        
        Parameters:
        -----------
        variable : str
            Climate variable to analyze
        """
        if variable not in self.df.columns:
            raise ValueError(f"Variable '{variable}' not found")
        
        result = {
            'variable': variable,
            'province': self.province or 'All',
            'data_points': len(self.df),
            'methods': {}
        }
        
        # Raw time series
        try:
            result['methods']['raw_series'] = self.raw_time_series(variable)
        except Exception as e:
            result['methods']['raw_series'] = {'error': str(e)}
        
        # Moving averages
        try:
            result['methods']['moving_averages'] = self.moving_averages(variable)
        except Exception as e:
            result['methods']['moving_averages'] = {'error': str(e)}
        
        # Annual trend
        try:
            result['methods']['annual_trend'] = self.annual_trend(variable)
        except Exception as e:
            result['methods']['annual_trend'] = {'error': str(e)}
        
        # Linear regression
        try:
            result['methods']['linear_regression'] = self.linear_regression_trend(variable)
        except Exception as e:
            result['methods']['linear_regression'] = {'error': str(e)}
        
        # Mann-Kendall test
        try:
            result['methods']['mann_kendall'] = self.mann_kendall_test(variable)
        except Exception as e:
            result['methods']['mann_kendall'] = {'error': str(e)}
        
        # LOWESS
        try:
            result['methods']['lowess'] = self.lowess_trend(variable)
        except Exception as e:
            result['methods']['lowess'] = {'error': str(e)}
        
        return result
