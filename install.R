# ── IEO Synthetic Ocean Anomaly Detector ─────────────────────────────────────
# install.R — Idempotent dependency installer.
# Run once before executing main.R.

required_packages <- c(
  "arrow",      # Parquet columnar I/O
  "isotree",    # Isolation Forest (Sathe-Liu 2017 + Extended IF)
  "yaml",       # Config loader
  "logger",     # Structured logging (tee: stdout + file)
  "parallel"    # detectCores() — stdlib, no install needed
)

install_if_missing <- function(pkgs) {
  missing_pkgs <- pkgs[!vapply(pkgs, requireNamespace, logical(1L), quietly = TRUE)]
  if (length(missing_pkgs) == 0L) {
    message("All dependencies satisfied.")
    return(invisible(NULL))
  }
  message(sprintf("Installing: %s", paste(missing_pkgs, collapse = ", ")))
  install.packages(missing_pkgs, repos = "https://cloud.r-project.org", quiet = FALSE)
}

install_if_missing(required_packages)
message("Dependency check complete.")
