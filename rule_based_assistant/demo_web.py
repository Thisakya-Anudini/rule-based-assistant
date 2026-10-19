"""Compatibility entry point for the browser demo."""

from .examples.demo_web import *  # noqa: F401,F403

if __name__ == "__main__":
    from .examples.demo_web import router

    import uvicorn

    uvicorn.run(router, host="127.0.0.1", port=8000)
