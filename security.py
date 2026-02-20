# security.py
from functools import wraps
from flask import request, jsonify, current_app
import jwt
from datetime import datetime, timedelta
import hashlib
import secrets

class SecurityManager:
    @staticmethod
    def generate_api_key():
        """Generate API key for external integrations"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_api_key(api_key):
        """Hash API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def verify_api_key(provided_key, stored_hash):
        """Verify API key"""
        return hashlib.sha256(provided_key.encode()).hexdigest() == stored_hash
    
    @staticmethod
    def generate_jwt_token(user_id, expires_in=3600):
        """Generate JWT token for API access"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(seconds=expires_in),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
    
    @staticmethod
    def verify_jwt_token(token):
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            return payload['user_id']
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

def require_api_key(f):
    """Decorator to require API key for endpoint access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        # Verify API key (implement your verification logic)
        if not SecurityManager.verify_api_key(api_key, 'stored_hash'):
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def require_jwt_token(f):
    """Decorator to require JWT token for API access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token required'}), 401
        
        try:
            token = token.split(' ')[1]  # Remove 'Bearer ' prefix
        except IndexError:
            return jsonify({'error': 'Invalid token format'}), 401
        
        user_id = SecurityManager.verify_jwt_token(token)
        if not user_id:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        request.current_user_id = user_id
        return f(*args, **kwargs)
    return decorated_function
