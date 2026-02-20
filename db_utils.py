from sqlalchemy import func
from models import db, Class # Assuming your models/db are imported from 'app'

def get_class_by_name_safe(class_name_input: str):
    """
    Safely retrieves a Class object using a name, ignoring case and leading/trailing spaces.

    This function is crucial for robust lookups, especially when reading class
    names from external files or student records (where minor data entry
    inconsistencies often occur).
    """
    if not class_name_input:
        return None

    # 1. Strip external spaces from the input string
    cleaned_input = class_name_input.strip()

    # 2. Query the Class model using a case-insensitive search (ilike)
    #    and also ensure the name in the database is trimmed (func.trim)
    #    before comparison, just in case a database record has trailing spaces.
    
    # NOTE: The Class model and db must be accessible (imported from app)
    class_obj = db.session.query(Class).filter(
        func.lower(func.trim(Class.name)) == func.lower(cleaned_input)
    ).first()
    
    return class_obj

# You can also add other utility functions here, like:
def get_user_by_role_and_name_safe(role: str, name: str):
    """Safely finds a user by role and full name."""
    # ... implementation
    pass
