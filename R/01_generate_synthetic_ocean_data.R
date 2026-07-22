# ==============================================================================
# 01_generate_synthetic_ocean_data.R
# Purpose : Generate synthetic multivariate oceanographic time-series with
#           deliberate multivariate anomaly injection (5% by default).
# Outputs : data/raw/ocean_synthetic.parquet
# Rules   : No magic numbers — all thresholds sourced from config.
# ==============================================================================

suppressPackageStartupMessages({
  library(arrow)     # parquet I/O
  library(yaml)      # config loader
  library(logger)    # structured logging
})

# ── Config ──────────────────────────────────────────────────────────────────
load_config <- function(path = "config/params.yml") {
  if (!file.exists(path)) stop(sprintf("Config not found: %s", path))
  yaml::read_yaml(path)
}

# ── Logging ──────────────────────────────────────────────────────────────────
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

# ── Normal Oceanographic Regime ───────────────────────────────────────────────
# Physics-informed synthetic distributions (North Atlantic surface layer):
#   Temperature : seasonal sinusoidal + Gaussian noise  (°C)
#   Salinity    : weakly correlated with temp, PSU scale
#   Pressure    : depth proxy, log-normal (dbar)
#   Oxygen      : inversely correlated with temp (mg/L)
#   Turbidity   : right-skewed, gamma distributed (NTU)
generate_normal_regime <- function(n, seed) {
  set.seed(seed)
  t_idx <- seq(0, 4 * pi, length.out = n)

  temp      <- 14 + 8 * sin(t_idx) + rnorm(n, sd = 0.8)
  salinity  <- 35.2 - 0.1 * (temp - 14) + rnorm(n, sd = 0.3)
  pressure  <- rlnorm(n, meanlog = log(50), sdlog = 0.6)          # dbar
  oxygen    <- 8.5 - 0.15 * (temp - 14) + rnorm(n, sd = 0.4)
  turbidity <- rgamma(n, shape = 2, rate = 1)

  data.frame(
    timestamp = seq.POSIXt(
      from = as.POSIXct("2020-01-01", tz = "UTC"),
      by   = "30 min",
      length.out = n
    ),
    temperature_c  = round(temp, 4),
    salinity_psu   = round(salinity, 4),
    pressure_dbar  = round(pressure, 4),
    oxygen_mgl     = round(oxygen, 4),
    turbidity_ntu  = round(turbidity, 4),
    is_anomaly     = FALSE
  )
}

# ── Anomaly Injection ─────────────────────────────────────────────────────────
# Injects 3 anomaly archetypes to test multivariate detection:
#   Type A – sensor spike (extreme value in one variable)
#   Type B – correlated breakdown (salinity/temp decoupled)
#   Type C – global drift (all variables shift simultaneously)
inject_anomalies <- function(df, fraction, seed) {
  set.seed(seed + 1L)
  n_anomalies <- as.integer(nrow(df) * fraction)
  if (n_anomalies < 1L) stop("anomaly_fraction too low: 0 anomalies selected")

  idx <- sample(nrow(df), n_anomalies, replace = FALSE)
  n_a <- as.integer(n_anomalies * 0.4)
  n_b <- as.integer(n_anomalies * 0.35)
  n_c <- n_anomalies - n_a - n_b

  idx_a <- idx[seq_len(n_a)]
  idx_b <- idx[n_a + seq_len(n_b)]
  idx_c <- idx[n_a + n_b + seq_len(n_c)]

  # Type A: sensor spike on temperature
  df$temperature_c[idx_a]  <- df$temperature_c[idx_a] + runif(n_a, 15, 25)
  df$turbidity_ntu[idx_a]  <- df$turbidity_ntu[idx_a] * runif(n_a, 8, 12)

  # Type B: salinity/temp physical decoupling
  df$salinity_psu[idx_b]   <- df$salinity_psu[idx_b] + runif(n_b, 8, 12)
  df$temperature_c[idx_b]  <- df$temperature_c[idx_b] - runif(n_b, 5, 8)

  # Type C: global sensor drift
  df$temperature_c[idx_c]  <- df$temperature_c[idx_c] * runif(n_c, 2.5, 3.5)
  df$salinity_psu[idx_c]   <- df$salinity_psu[idx_c]  * runif(n_c, 1.8, 2.2)
  df$oxygen_mgl[idx_c]     <- pmax(0, df$oxygen_mgl[idx_c] - runif(n_c, 5, 7))
  df$pressure_dbar[idx_c]  <- df$pressure_dbar[idx_c] * runif(n_c, 5, 10)

  df$is_anomaly[idx] <- TRUE
  log_info("Injected {n_anomalies} anomalies: TypeA={n_a}, TypeB={n_b}, TypeC={n_c}")
  df
}

# ── Export ────────────────────────────────────────────────────────────────────
export_parquet <- function(df, path) {
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  arrow::write_parquet(df, path)
  log_info("Exported {nrow(df)} rows → {path}")
}

# ── Entry Point ───────────────────────────────────────────────────────────────
main <- function() {
  cfg <- load_config()
  init_logger(cfg$log)

  log_info("=== Stage 01: Synthetic Data Generation ===")
  log_info("n={cfg$data$n_observations}, anomaly_fraction={cfg$data$anomaly_fraction}")

  df <- generate_normal_regime(cfg$data$n_observations, cfg$data$seed)
  df <- inject_anomalies(df, cfg$data$anomaly_fraction, cfg$data$seed)

  true_rate <- mean(df$is_anomaly)
  log_info("True anomaly rate: {round(true_rate * 100, 2)}%")

  export_parquet(df, cfg$data$output_file)
  log_info("Stage 01 complete.")
  invisible(df)
}

main()
