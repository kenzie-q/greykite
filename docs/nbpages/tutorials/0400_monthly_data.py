"""
Example for monthly data
==============================

This is a basic example for monthly data using Silverkite.
Note that here we are fitting a few simple models and the goal is not to optimize
the results as much as possible.
"""

import warnings
from collections import defaultdict

import plotly
import pandas as pd

from greykite.framework.benchmark.data_loader_ts import DataLoaderTS
from greykite.framework.templates.autogen.forecast_config import EvaluationPeriodParam
from greykite.framework.templates.autogen.forecast_config import ForecastConfig
from greykite.framework.templates.autogen.forecast_config import MetadataParam
from greykite.framework.templates.autogen.forecast_config import ModelComponentsParam
from greykite.framework.templates.forecaster import Forecaster
from greykite.framework.utils.result_summary import summarize_grid_search_results
from greykite.framework.input.univariate_time_series import UnivariateTimeSeries

warnings.filterwarnings("ignore")

# %%
# Loads dataset into ``UnivariateTimeSeries``.
dl = DataLoaderTS()
agg_func = {"count": "sum"}
df = dl.load_bikesharing(agg_freq="monthly", agg_func=agg_func)
# In this monthly data the last month data is incomplete, therefore we drop it
df.drop(df.tail(1).index,inplace=True)
df.reset_index(drop=True)
ts = UnivariateTimeSeries()
ts.load_data(
    df=df,
    time_col="ts",
    value_col="count",
    freq="MS")

# %%
# Exploratory data analysis (EDA)
# --------------------------------
# After reading in a time series, we could first do some exploratory data analysis.
# The `~greykite.framework.input.univariate_time_series.UnivariateTimeSeries` class is
# used to store a timeseries and perform EDA.

# %%
# A quick description of the data can be obtained as follows.
print(ts.describe_time_col())
print(ts.describe_value_col())
print(df.head())

# %%
# Let's plot the original timeseries.
# (The interactive plot is generated by ``plotly``: **click to zoom!**)
fig = ts.plot()
plotly.io.show(fig)

# %%
# Exploratory plots can be plotted to reveal the time series's properties.
# Monthly overlay plot can be used to inspect the annual patterns.
# This plot overlays various years on top of each other.
fig = ts.plot_quantiles_and_overlays(
     groupby_time_feature="month",
     show_mean=False,
     show_quantiles=False,
     show_overlays=True,
     overlay_label_time_feature="year",
     overlay_style={"line": {"width": 1}, "opacity": 0.5},
     center_values=False,
     xlabel="month of year",
     ylabel=ts.original_value_col,
     title="yearly seasonality for each year (centered)",)
plotly.io.show(fig)

# %%
# Specify common metadata.
forecast_horizon = 4
time_col = "ts"
value_col = "count"
meta_data_params = MetadataParam(
    time_col=time_col,
    value_col=value_col,
    freq="MS",
)

# %%
# Specify common evaluation parameters.
# Set minimum input data for training.
cv_min_train_periods = 24
# Let CV use most recent splits for cross-validation.
cv_use_most_recent_splits = True
# Determine the maximum number of validations.
cv_max_splits = 5
evaluation_period_param = EvaluationPeriodParam(
    test_horizon=forecast_horizon,
    cv_horizon=forecast_horizon,
    periods_between_train_test=0,
    cv_min_train_periods=cv_min_train_periods,
    cv_expanding_window=True,
    cv_use_most_recent_splits=cv_use_most_recent_splits,
    cv_periods_between_splits=None,
    cv_periods_between_train_test=0,
    cv_max_splits=cv_max_splits,
)

# %%
# Fit a simple model without autoregression.
# The important modeling parameters for monthly data are as follows.
# These are plugged into ``ModelComponentsParam``.
# The ``extra_pred_cols`` is used to specify growth and annual seasonality
# Growth is modelled with both "ct_sqrt", "ct1" for extra flexibility as we have
# longterm data and ridge regularization will avoid over-fitting the trend.
# The annual seasonality is modelled categorically with "C(month)" instead of
# Fourier series. This is because in monthly data, the number of data points in
# year is rather small (12) as opposed to daily data where there are many points in
# the year, which makes categorical representation non-feasible.
# The categorical representation of monthly also is more explainable/interpretable in the model
# summary.
extra_pred_cols = ["ct_sqrt", "ct1", "C(month, levels=list(range(1, 13)))"]
autoregression = None

# Specify the model parameters
model_components = ModelComponentsParam(
    growth=dict(growth_term=None),
    seasonality=dict(
        yearly_seasonality=[False],
        quarterly_seasonality=[False],
        monthly_seasonality=[False],
        weekly_seasonality=[False],
        daily_seasonality=[False]
    ),
    custom=dict(
        fit_algorithm_dict=dict(fit_algorithm="ridge"),
        extra_pred_cols=extra_pred_cols
    ),
    regressors=dict(regressor_cols=None),
    autoregression=autoregression,
    uncertainty=dict(uncertainty_dict=None),
    events=dict(holiday_lookup_countries=None),
)

# Run the forecast model
forecaster = Forecaster()
result =  forecaster.run_forecast_config(
    df=df,
    config=ForecastConfig(
        model_template="SILVERKITE",
        coverage=0.95,
        forecast_horizon=forecast_horizon,
        metadata_param=meta_data_params,
        evaluation_period_param=evaluation_period_param,
        model_components_param=model_components
    )
)

# Get the useful fields from the forecast result
model = result.model[-1]
backtest = result.backtest
forecast = result.forecast
grid_search = result.grid_search

# Check model coefficients / variables
# Get model summary with p-values
print(model.summary())

# Get cross-validation results
cv_results = summarize_grid_search_results(
    grid_search=grid_search,
    decimals=2,
    cv_report_metrics=None,
    column_order=[
        "rank", "mean_test", "split_test", "mean_train", "split_train",
        "mean_fit_time", "mean_score_time", "params"])
# Transposes to save space in the printed output
print(cv_results.transpose())

# Check historical evaluation metrics (on the historical training/test set).
backtest_eval = defaultdict(list)
for metric, value in backtest.train_evaluation.items():
    backtest_eval[metric].append(value)
    backtest_eval[metric].append(backtest.test_evaluation[metric])
metrics = pd.DataFrame(backtest_eval, index=["train", "test"]).T
print(metrics)

# %%
# Fit/backtest plot:
fig = backtest.plot()
plotly.io.show(fig)

# %%
# Forecast plot:
fig = forecast.plot()
plotly.io.show(fig)

# %%
# The components plot:
fig = forecast.plot_components()
plotly.io.show(fig)

# %%
# Fit a simple model with autoregression.
# This is done by specifying the ``autoregression`` parameter in ``ModelComponentsParam``.
# Note that the auto-regressive structure can be customized further depending on your data.
extra_pred_cols = ["ct_sqrt", "ct1", "C(month, levels=list(range(1, 13)))"]
autoregression = {
    "autoreg_dict": {
        "lag_dict": {"orders": [1]},
        "agg_lag_dict": None
    }
}

# Specify the model parameters
model_components = ModelComponentsParam(
    growth=dict(growth_term=None),
    seasonality=dict(
        yearly_seasonality=[False],
        quarterly_seasonality=[False],
        monthly_seasonality=[False],
        weekly_seasonality=[False],
        daily_seasonality=[False]
    ),
    custom=dict(
        fit_algorithm_dict=dict(fit_algorithm="ridge"),
        extra_pred_cols=extra_pred_cols
    ),
    regressors=dict(regressor_cols=None),
    autoregression=autoregression,
    uncertainty=dict(uncertainty_dict=None),
    events=dict(holiday_lookup_countries=None),
)

# Run the forecast model
forecaster = Forecaster()
result =  forecaster.run_forecast_config(
    df=df,
    config=ForecastConfig(
        model_template="SILVERKITE",
        coverage=0.95,
        forecast_horizon=forecast_horizon,
        metadata_param=meta_data_params,
        evaluation_period_param=evaluation_period_param,
        model_components_param=model_components
    )
)

# Get the useful fields from the forecast result
model = result.model[-1]
backtest = result.backtest
forecast = result.forecast
grid_search = result.grid_search

# Check model coefficients / variables
# Get model summary with p-values
print(model.summary())

# Get cross-validation results
cv_results = summarize_grid_search_results(
    grid_search=grid_search,
    decimals=2,
    cv_report_metrics=None,
    column_order=[
        "rank", "mean_test", "split_test", "mean_train", "split_train",
        "mean_fit_time", "mean_score_time", "params"])
# Transposes to save space in the printed output
print(cv_results.transpose())

# Check historical evaluation metrics (on the historical training/test set).
backtest_eval = defaultdict(list)
for metric, value in backtest.train_evaluation.items():
    backtest_eval[metric].append(value)
    backtest_eval[metric].append(backtest.test_evaluation[metric])
metrics = pd.DataFrame(backtest_eval, index=["train", "test"]).T
print(metrics)

# %%
# Fit/backtest plot:
fig = backtest.plot()
plotly.io.show(fig)

# %%
# Forecast plot:
fig = forecast.plot()
plotly.io.show(fig)

# %%
# The components plot:
fig = forecast.plot_components()
plotly.io.show(fig)

# %%
# Fit a model with time-varying seasonality (month effect).
# This is achieved by adding ``"ct1*C(month)"`` to ``ModelComponentsParam``.
# Note that this feature may or may not be useful in your use case.
# We have included this for demonstration purposes only.
# In this example, while the fit has improved the backtest is inferior to the previous setting.
extra_pred_cols = ["ct_sqrt", "ct1", "C(month, levels=list(range(1, 13)))",
                   "ct1*C(month, levels=list(range(1, 13)))"]
autoregression = {
    "autoreg_dict": {
        "lag_dict": {"orders": [1]},
        "agg_lag_dict": None
    }
}

# Specify the model parameters
model_components = ModelComponentsParam(
    growth=dict(growth_term=None),
    seasonality=dict(
        yearly_seasonality=[False],
        quarterly_seasonality=[False],
        monthly_seasonality=[False],
        weekly_seasonality=[False],
        daily_seasonality=[False]
    ),
    custom=dict(
        fit_algorithm_dict=dict(fit_algorithm="ridge"),
        extra_pred_cols=extra_pred_cols
    ),
    regressors=dict(regressor_cols=None),
    autoregression=autoregression,
    uncertainty=dict(uncertainty_dict=None),
    events=dict(holiday_lookup_countries=None),
)

# Run the forecast model
forecaster = Forecaster()
result =  forecaster.run_forecast_config(
    df=df,
    config=ForecastConfig(
        model_template="SILVERKITE",
        coverage=0.95,
        forecast_horizon=forecast_horizon,
        metadata_param=meta_data_params,
        evaluation_period_param=evaluation_period_param,
        model_components_param=model_components
    )
)

# Get the useful fields from the forecast result
model = result.model[-1]
backtest = result.backtest
forecast = result.forecast
grid_search = result.grid_search

# Check model coefficients / variables
# Get model summary with p-values
print(model.summary())

# Get cross-validation results
cv_results = summarize_grid_search_results(
    grid_search=grid_search,
    decimals=2,
    cv_report_metrics=None,
    column_order=[
        "rank", "mean_test", "split_test", "mean_train", "split_train",
        "mean_fit_time", "mean_score_time", "params"])
# Transposes to save space in the printed output
print(cv_results.transpose())

# Check historical evaluation metrics (on the historical training/test set).
backtest_eval = defaultdict(list)
for metric, value in backtest.train_evaluation.items():
    backtest_eval[metric].append(value)
    backtest_eval[metric].append(backtest.test_evaluation[metric])
metrics = pd.DataFrame(backtest_eval, index=["train", "test"]).T
print(metrics)

# %%
# Fit/backtest plot:
fig = backtest.plot()
plotly.io.show(fig)

# %%
# Forecast plot:
fig = forecast.plot()
plotly.io.show(fig)

# %%
# The components plot:
fig = forecast.plot_components()
plotly.io.show(fig)

