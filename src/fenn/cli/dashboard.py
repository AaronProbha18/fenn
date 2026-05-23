"""fenn dashboard — launch the Fenn log-browser web UI."""

DASHBOARD_HOST = "127.0.0.1"


def execute(args) -> None:
    """Import and start the dashboard server directly from the installed package."""
    try:
        from fenn.dashboard.app import run
    except ImportError as exc:
        raise SystemExit(
            "ERROR: Could not import the Fenn dashboard.\n"
            "Make sure Flask is installed:  pip install flask\n"
            f"Details: {exc}"
        )

    try:
        run(
            host=DASHBOARD_HOST,
            port=args.port,
            debug=args.debug,
            log_dirs=args.log_dir,
        )
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
