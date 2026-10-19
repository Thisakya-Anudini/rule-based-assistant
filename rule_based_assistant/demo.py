"""Compatibility entry point for the example demo."""

from .examples.demo import *  # noqa: F401,F403

if __name__ == "__main__":
    from .examples.demo import main

    main()
