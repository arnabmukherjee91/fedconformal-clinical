"""
fedconformal -- Federated conformal prediction for cross-site clinical data.

A teaching-oriented toolkit accompanying the workshop
"Beyond Interoperability: Hands-On Federated ML for Research Data Curation
Infrastructure."

It implements split conformal prediction (Angelopoulos & Bates, 2022) on top of a
transparent NumPy FedAvg simulator, and adds diagnostics for distinguishing true
distributional shift from measurement-induced heterogeneity across hospital
sites, using the naturally-federated UCI Heart Disease dataset.
"""

from . import data, conformal, evaluate, federated, heterogeneity, viz

__all__ = ["data", "conformal", "evaluate", "federated", "heterogeneity", "viz"]
__version__ = "0.1.0"
