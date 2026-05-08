import secrets
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# Mock user directory. Passwords are plaintext for development testing only.
USERS = {
    'omar': {
        'name': 'Omar Akaddah',
        'role': 'Admin',
        'password': 'admin123',
        'clearance': 'restricted',
    },
    'sara': {
        'name': 'Sara Hassan',
        'role': 'Senior Compliance',
        'password': 'compliance123',
        'clearance': 'confidential',
    },
    'ahmed': {
        'name': 'Ahmed Ali',
        'role': 'Compliance Analyst',
        'password': 'staff123',
        'clearance': 'internal',
    },
    'guest': {
        'name': 'Guest',
        'role': 'External',
        'password': 'guest',
        'clearance': 'public',
    },
}

SESSIONS = {}  # token -> username

bearer = HTTPBearer(auto_error=False)


def login(username, password):
    user = USERS.get(username)
    if not user or user['password'] != password:
        return None
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = username
    return token


def logout(token):
    SESSIONS.pop(token, None)


def userFromToken(token):
    username = SESSIONS.get(token)
    if not username:
        return None
    user = USERS.get(username)
    if not user:
        return None
    return {
        'username': username,
        'name': user['name'],
        'role': user['role'],
        'clearance': user['clearance'],
    }


def getCurrentUser(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not creds:
        raise HTTPException(status_code=401, detail='Missing credentials')
    user = userFromToken(creds.credentials)
    if not user:
        raise HTTPException(status_code=401, detail='Invalid or expired token')
    return user
