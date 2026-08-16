"""Small package-installed smoke check for QWeSDK."""

import argparse


def main(argv=None):
    """Verify that the lightweight SDK import boundary is available."""
    parser = argparse.ArgumentParser(description="Check the QWeSDK import boundary")
    parser.parse_args(argv)

    import m

    # Keep this command dependency-light; full strategy tests belong to CI.
    print("QWeSDK import check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
