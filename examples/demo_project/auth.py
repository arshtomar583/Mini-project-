from database import find_user


def login(username):
    """Demo lookup only; this does not implement real authentication."""
    return find_user(username)
