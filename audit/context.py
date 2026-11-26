from contextvars import ContextVar

# Holds the user who is making the current request
current_user = ContextVar("current_user", default=None)