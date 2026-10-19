"""Compatibility entry point for the demo preflight checks."""

from .examples.demo_check import *  # noqa: F401,F403

if __name__ == "__main__":
    from .examples.demo_check import main

    main()
