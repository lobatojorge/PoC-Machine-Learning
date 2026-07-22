# ==============================================================================
# 02_isolation_forest.R
# Purpose : Load synthetic ocean parquet → train Isolation Forest →
#           score observations → label outliers → export results.
# Engine  : isotree::isolation.forest()
# Outputs : data/processed/ocean_scores.parquet, models/isolation_forest.rds
# ==============================================================================

suppressPackageStartupMessages({
  library(arrow)    # parquet I/O
  library(isotree)  # Isolation Forest (Sathe & Liu, 2017 + Extended IF)
  library(yaml)     # config
  library(logger)   # structured logging
})

# ── Config & Logger ──────────────────────────────────────────────────────────
load_config <- function(path = "config/params.yml") {
  if (!file.exists(path)) stop(sprintf("Config not found: %s", path))
  yaml::read_yaml(path)
}

init_logger <- function(log_cfg) {
  log_file <- log_cfg$file
  dir.create(dirname(log_file), showWarnings = FALSE, recursive = TRUE)
  log_appender(appender_tee(log_file))
  log_threshold(switch(log_cfg$level,
    INFO  = logger::INFO,
    DEBUG = logger::DEBUG,
    WARN  = logger::WARN,
    ERROR = logger::ERROR,
    logger::INFO
  ))
}

# ── Data Loader ──────────────────────────────────────────────────────────────
load_ocean_data <- function(path) {
  if (!file.exists(path)) stop(sprintf("Input not found: %s", path))
  df <- arrow::read_parquet(path)
  required_cols <- c("temperature_c", "salinity_psu", "pressure_dbar",
                      "oxygen_mgl", "turbidity_ntu")
  missing <- setdiff(required_cols, names(df))
  if (length(missing) > 0L) stop(sprintf("Missing columns: %s", paste(missing, collapse = ", ")))
  log_info("Loaded {nrow(df)} rows from {path}")
  df
}

# ── Feature Matrix ───────────────────────────────────────────────────────────
# Isolation Forest is distance-free: no scaling required.
# Columns selected = physical sensor dimensions only; metadata excluded.
build_feature_matrix <- function(df) {
  feature_cols <- c("temperature_c", "salinity_psu", "pressure_dbar",
                    "oxygen_mgl", "turbidity_ntu")
  X <- df[, feature_cols]
  n_na <- sum(is.na(X))
  if (n_na > 0L) {
    log_warn("{n_na} NA values in feature matrix — imputing with column medians")
    for (col in feature_cols) {
      med <- median(X[[col]], na.rm = TRUE)
      X[[col]][is.na(X[[col]])] <- med
    }
  }
  log_info("Feature matrix: {nrow(X)} x {ncol(X)}")
  X
}

# ── Model Training ────────────────────────────────────────────────────────────
# Extended Isolation Forest (ndim > 1) generalises standard IF by using
# hyperplanes instead of axis-aligned cuts → better for correlated features.
train_isolation_forest <- function(X, model_cfg, seed) {
  log_info("Training Extended Isolation Forest: ntrees={model_cfg$num_trees}, ",
           "sample_size={model_cfg$sample_size}, max_depth={model_cfg$max_depth}")

  model <- isotree::isolation.forest(
    data        = X,
    ntrees      = model_cfg$num_trees,
    sample_size = model_cfg$sample_size,
    max_depth   = model_cfg$max_depth,
    ndim        = 2L,          # Extended IF: 2-D hyperplane cuts
    scoring_metric = "depth",  # Average path length → anomaly score in [0,1]
    seed        = seed,
    nthreads    = parallel::detectCores() - 1L
  )
  log_info("Model trained.")
  model
}

# ── Scoring & Labelling ───────────────────────────────────────────────────────
# score ∈ [0, 1]: higher = more anomalous.
# Threshold = percentile from config (no hardcoded 0.5 default).
score_and_label <- function(model, X, threshold_pct) {
  scores <- predict(model, X, type = "score")
  cutoff <- quantile(scores, probs = threshold_pct / 100, na.rm = TRUE)
  labels <- scores >= cutoff
  log_info("Score stats: min={round(min(scores),4)}, median={round(median(scores),4)}, ",
           "max={round(max(scores),4)}")
  log_info("Threshold @p{threshold_pct}: {round(cutoff,4)} → {sum(labels)} flagged anomalies")
  list(scores = scores, labels = labels, cutoff = cutoff)
}

# ── Evaluation (Supervised, because we injected ground truth) ────────────────
evaluate_detection <- function(true_labels, pred_labels) {
  tp <- sum( true_labels &  pred_labels)
  fp <- sum(!true_labels &  pred_labels)
  fn <- sum( true_labels & !pred_labels)
  tn <- sum(!true_labels & !pred_labels)

  precision <- if ((tp + fp) == 0L) NA_real_ else tp / (tp + fp)
  recall    <- if ((tp + fn) == 0L) NA_real_ else tp / (tp + fn)
  f1        <- if (is.na(precision) || is.na(recall) || (precision + recall) == 0) NA_real_
               else 2 * precision * recall / (precision + recall)

  log_info("Evaluation vs ground truth — Precision: {round(precision,4)}, ",
           "Recall: {round(recall,4)}, F1: {round(f1,4)}")
  log_info("Confusion — TP:{tp} FP:{fp} FN:{fn} TN:{tn}")
  list(precision = precision, recall = recall, f1 = f1)
}

# ── Persistence ───────────────────────────────────────────────────────────────
save_model <- function(model, path) {
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  saveRDS(model, path)
  log_info("Model serialised → {path}")
}

export_scores <- function(df, scores, labels, path) {
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  df$anomaly_score   <- round(scores, 6)
  df$predicted_anomaly <- labels
  arrow::write_parquet(df, path)
  log_info("Scored dataset exported → {path} ({nrow(df)} rows)")
}

# ── Entry Point ───────────────────────────────────────────────────────────────
main <- function() {
  cfg <- load_config()
  init_logger(cfg$log)
  log_info("=== Stage 02: Isolation Forest Training & Scoring ===")

  df     <- load_ocean_data(cfg$data$output_file)
  X      <- build_feature_matrix(df)
  model  <- train_isolation_forest(X, cfg$model, cfg$data$seed)
  result <- score_and_label(model, X, cfg$model$threshold_percentile)

  if ("is_anomaly" %in% names(df)) {
    evaluate_detection(df$is_anomaly, result$labels)
  } else {
    log_warn("No ground-truth column 'is_anomaly' found — skipping evaluation")
  }

  save_model(model, cfg$model$output_model)
  export_scores(df, result$scores, result$labels, cfg$model$output_scores)
  log_info("Stage 02 complete.")
  invisible(list(model = model, scores = result$scores, labels = result$labels))
}

main()
