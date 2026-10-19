"""Compatibility entry point for the example dataset builder."""

from .examples.build_test_dataset import *  # noqa: F401,F403

if __name__ == "__main__":
    from .examples.build_test_dataset import main

    main()
