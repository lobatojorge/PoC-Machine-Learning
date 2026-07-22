# IEO Synthetic Ocean Anomaly Detector

> **MLOps portfolio case study — multivariate anomaly detection in oceanographic sensor streams using Extended Isolation Forest.**

[![R ≥ 4.3](https://img.shields.io/badge/R-%E2%89%A54.3-276DC3?logo=r)](https://www.r-project.org/)
[![isotree](https://img.shields.io/badge/engine-isotree-orange)](https://cran.r-project.org/package=isotree)
[![Parquet](https://img.shields.io/badge/storage-Apache%20Parquet-blue)](https://parquet.apache.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Problem Statement

Marine sensor networks (CTD buoys, Argo floats, moored arrays) generate continuous multivariate time-series across temperature, salinity, pressure, dissolved oxygen, and turbidity channels. **Sensor failures, biofouling, calibration drift, and marine debris impacts** produce anomalous readings that corrupt downstream oceanographic models if undetected.

This repository implements a **production-grade anomaly detection pipeline** replicating the architecture of a real-world data orchestrator, using 100% synthetic data to protect client IP.

## Executive Summary

**What it does:** 
This Proof of Concept (PoC) automates the detection of anomalies in multivariate oceanographic data using an Extended Isolation Forest model. It simulates realistic marine conditions (temperature, salinity, depth/pressure, oxygen, turbidity) and deliberately injects various failure archetypes (sensor spikes, uncoupled physical relationships, and global drifts). The pipeline processes the synthetic data in a reproducible, modular way, trains the anomaly detector, scores the observations, and exports the flagged outliers for downstream review—all orchestrated via a centralized YAML configuration.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    main.R  (Orchestrator)                   │
│   ┌─────────────┐        ┌──────────────────────────────┐  │
│   │  parse_args │──cfg──▶│         run_stage()           │  │
│   └─────────────┘        │  ┌────────────────────────┐  │  │
│                           │  │ Stage 01: Data Gen     │  │  │
│   config/params.yml ─────▶│  │ Stage 02: IF Model     │  │  │
│                           │  └────────────────────────┘  │  │
│                           │  tryCatch + sys.source()      │  │
│                           └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  logs/orchestrator.log      data/processed/ocean_scores.parquet
                             models/isolation_forest.rds
```

### Stage 01 — Synthetic Data Generator (`R/01_generate_synthetic_ocean_data.R`)

| Component | Design Decision |
|-----------|----------------|
| Temperature | Seasonal sinusoidal + Gaussian noise (North Atlantic profile) |
| Salinity | Physically correlated with temperature (halocline dynamics) |
| Pressure | Log-normal (depth distribution, dbar) |
| Oxygen | Inversely correlated with temperature (solubility law) |
| Turbidity | Gamma-distributed (right-skewed, realistic NTU) |
| **Anomaly injection** | 3 archetypes: sensor spike, S/T decoupling, global drift |

**5% of observations are labelled anomalies** — ground truth enables supervised evaluation.

### Stage 02 — Extended Isolation Forest (`R/02_isolation_forest.R`)

Standard Isolation Forest uses axis-aligned binary splits. For correlated oceanographic variables (e.g., temperature–salinity coupling), this is suboptimal.

**Extended IF** (`ndim=2`, `isotree`) uses random hyperplane cuts in 2D feature subspaces, yielding superior separation of physically-coupled anomalies without feature engineering or scaling.

```
Score ∈ [0, 1]:  0 = deep in forest (normal) | 1 = isolated quickly (anomaly)
Threshold       : configurable percentile (default p95) — no hardcoded cutoffs
```

Evaluation metrics computed against injected ground truth: **Precision / Recall / F1**.

---

## Repository Structure

```
IEO-Orchestrator/
├── main.R                                 # Pipeline controller (entry point)
├── install.R                              # Idempotent dependency installer
├── config/
│   └── params.yml                         # All hyperparameters & paths
├── R/
│   ├── 01_generate_synthetic_ocean_data.R # Stage 01: Synthetic data + anomaly injection
│   └── 02_isolation_forest.R              # Stage 02: EIF training, scoring, export
├── data/
│   ├── raw/                               # ocean_synthetic.parquet (generated)
│   └── processed/                         # ocean_scores.parquet (output)
├── models/
│   └── isolation_forest.rds              # Serialised EIF model artifact
├── logs/
│   └── orchestrator.log                  # Tee'd structured log (stdout + file)
└── docs/
```

---

## Quickstart

```bash
# 1. Install R dependencies (idempotent — safe to re-run)
Rscript install.R

# 2. Run the full pipeline
Rscript main.R

# 3. Override config path if needed
Rscript main.R --config config/params.yml
```

**Expected terminal output (abbreviated):**
```
INFO [main.R] ╔══════════════════════════════════════════════════╗
INFO [main.R] ║  IEO Synthetic Ocean Anomaly Detector            ║
INFO [main.R] ╚══════════════════════════════════════════════════╝
INFO [main.R] >>> Starting stage: 01_generate_synthetic_data
INFO [01] Injected 250 anomalies: TypeA=100, TypeB=87, TypeC=63
INFO [01] Exported 5000 rows → data/raw/ocean_synthetic.parquet
INFO [01] <<< Stage completed in 1.43s
INFO [main.R] >>> Starting stage: 02_isolation_forest
INFO [02] Training Extended Isolation Forest: ntrees=200 ...
INFO [02] Threshold @p95: 0.6341 → 250 flagged anomalies
INFO [02] Evaluation — Precision: 0.912, Recall: 0.884, F1: 0.898
INFO [02] <<< Stage completed in 4.21s
INFO [main.R] Pipeline COMPLETE — total elapsed: 5.64s
```

---

## Configuration Reference (`config/params.yml`)

```yaml
data:
  n_observations: 5000         # Dataset size
  anomaly_fraction: 0.05       # Injection rate — drives ground truth density
  seed: 42

model:
  num_trees: 200               # More trees = stable scores, diminishing returns >300
  max_depth: 8                 # Controls isolation granularity
  sample_size: 256             # Sub-sampling per tree (Liu et al. 2012 default)
  threshold_percentile: 95     # Anomaly decision boundary
```

> **Rule**: No threshold is hardcoded in source. Change behaviour via YAML only.

---

## Design Principles

- **No magic numbers** — all statistical thresholds in `config/params.yml`
- **Single Responsibility** — each function in each script does exactly one thing
- **No swallowed exceptions** — all errors logged with stage context before re-throw
- **Reproducibility** — `seed` propagated through all stochastic operations
- **Isolated execution** — each stage runs in a dedicated `new.env(parent = baseenv())` preventing cross-stage state bleed

---

## Dependencies

| Package | Version | Role |
|---------|---------|------|
| `isotree` | ≥ 0.6 | Extended Isolation Forest engine |
| `arrow` | ≥ 14.0 | Apache Parquet columnar I/O |
| `yaml` | ≥ 2.3 | Config file parsing |
| `logger` | ≥ 0.3 | Structured logging (tee: stdout + file) |

---

## References

- Liu, F.T., Ting, K.M., Zhou, Z.H. (2008). *Isolation Forest*. ICDM 2008.
- Sathe, S., Aggarwal, C.C. (2017). *Subspace Outlier Detection in Linear Time with Randomized Hashing*. ICDM.
- `isotree` implementation: D. Cortes (2021). [CRAN](https://cran.r-project.org/package=isotree)

---

*Synthetic dataset. No real oceanographic observations or client data are present in this repository.*
