"""Lightweight ML forecasting layer for shortage-risk classification.

This package adds a forecasting/risk-classification layer on top of the existing
analytics and OR-Tools optimization systems. It predicts 48-72 hour shortage
severity risk for crisis zones using crisis/resource features and transparent
simulated (proxy) operational labels.

Important: labels are simulated/proxy labels because real NGO demand-outcome
labels are not publicly available. This component supports early planning and is
not an automated decision-maker.
"""
