# Route handlers module
from .config import AppConfig
from .models import UserRecord

def index_route(request):
    # Public health check
    return {"status": "ok", "debug": AppConfig.DEBUG}

def get_user_route(request, uid: int):
    # Return user record safely
    user = UserRecord(user_id=uid, username="alice", email="alice@example.com")
    return {"user": user.__dict__}
