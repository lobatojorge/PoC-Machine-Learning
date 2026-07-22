# ==============================================================================
# main.R — IEO Synthetic Ocean Anomaly Detector Orchestrator
# Usage  : Rscript main.R [--config path/to/params.yml]
# Purpose: Sequential pipeline controller with structured error handling.
# ==============================================================================

suppressPackageStartupMessages(library(logger))

# ── CLI args ──────────────────────────────────────────────────────────────────
parse_args <- function() {
  args   <- commandArgs(trailingOnly = TRUE)
  config <- "config/params.yml"
  i <- 1L
  while (i <= length(args)) {
    if (args[i] == "--config" && i < length(args)) {
      config <- args[i + 1L]
      i <- i + 2L
    } else {
      i <- i + 1L
    }
  }
  list(config = config)
}

# ── Orchestration logger bootstrap ────────────────────────────────────────────
# Uses a minimal logger before stage scripts initialise their own appenders.
bootstrap_logger <- function() {
  log_appender(appender_stdout())
  log_threshold(logger::INFO)
}

# ── Stage runner ──────────────────────────────────────────────────────────────
# Executes each stage script in an isolated environment via sys.source().
# tryCatch guarantees pipeline abort on any unhandled error in a stage.
run_stage <- function(stage_name, script_path) {
  if (!file.exists(script_path)) {
    log_error("Stage [{stage_name}] — script not found: {script_path}")
    stop(sprintf("Missing script: %s", script_path))
  }

  log_info(">>> Starting stage: {stage_name}")
  t_start <- proc.time()

  tryCatch(
    expr = {
      env <- new.env(parent = baseenv())
      sys.source(script_path, envir = env, chdir = FALSE)
      elapsed <- round((proc.time() - t_start)[["elapsed"]], 2)
      log_info("<<< Stage [{stage_name}] completed in {elapsed}s")
    },
    error = function(e) {
      elapsed <- round((proc.time() - t_start)[["elapsed"]], 2)
      log_error("Stage [{stage_name}] FAILED after {elapsed}s: {conditionMessage(e)}")
      stop(sprintf("Pipeline aborted at stage [%s]: %s", stage_name, conditionMessage(e)))
    },
    warning = function(w) {
      log_warn("Stage [{stage_name}] warning: {conditionMessage(w)}")
      invokeRestart("muffleWarning")
    }
  )
}

# ── Pipeline definition ───────────────────────────────────────────────────────
PIPELINE <- list(
  list(name = "01_generate_synthetic_data",  script = "R/01_generate_synthetic_ocean_data.R"),
  list(name = "02_isolation_forest",          script = "R/02_isolation_forest.R")
)

# ── Main ──────────────────────────────────────────────────────────────────────
main <- function() {
  bootstrap_logger()
  args <- parse_args()

  log_info("╔══════════════════════════════════════════════════════════════╗")
  log_info("║  IEO Synthetic Ocean Anomaly Detector — MLOps Orchestrator  ║")
  log_info("╚══════════════════════════════════════════════════════════════╝")
  log_info("Config: {args$config}")
  log_info("R version: {R.version$major}.{R.version$minor}")
  log_info("Stages in pipeline: {length(PIPELINE)}")

  t_global <- proc.time()

  for (stage in PIPELINE) {
    run_stage(stage$name, stage$script)
  }

  total_elapsed <- round((proc.time() - t_global)[["elapsed"]], 2)
  log_info("══════════════════════════════════════════════════════")
  log_info("Pipeline COMPLETE — total elapsed: {total_elapsed}s")
  log_info("══════════════════════════════════════════════════════")
}

main()
