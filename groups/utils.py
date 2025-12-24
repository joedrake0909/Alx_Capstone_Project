# groups/utils.py

def is_admin(user):
    """
    Checks if a user is a superuser or specifically marked as a group admin.
    """
    return user.is_authenticated and (user.is_superuser or getattr(user, 'is_group_admin', False))