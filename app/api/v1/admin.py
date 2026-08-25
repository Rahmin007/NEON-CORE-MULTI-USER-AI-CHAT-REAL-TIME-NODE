from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import RequireRole, get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import AdminUserCreate, UserResponse, UserRoleUpdate, UserStatusUpdate
from app.services.activity_service import log_activity
from app.core.security import get_password_hash

router = APIRouter(prefix="/admin", tags=["Administration"])
admin_only = RequireRole([UserRole.ADMIN])

@router.get("/users", response_model=list[UserResponse], dependencies=[Depends(admin_only)])
def get_all_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()

@router.post("/users", response_model=UserResponse, status_code=201, dependencies=[Depends(admin_only)])
def create_user(payload: AdminUserCreate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.scalar(select(User).where((User.username == payload.username) | (User.email == str(payload.email)))):
        raise HTTPException(status_code=409, detail="Username or email already exists.")
    user = User(username=payload.username, email=str(payload.email), hashed_password=get_password_hash(payload.password), role=payload.role)
    db.add(user); db.commit(); db.refresh(user)
    log_activity(db, current_user.id, "ADMIN_CREATE_USER", f"Created user {user.username} as {user.role.value}", request.client.host if request.client else None)
    return user

@router.patch("/users/{user_id}/role", response_model=UserResponse, dependencies=[Depends(admin_only)])
def update_role(user_id: int, payload: UserRoleUpdate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found.")
    user.role = payload.role
    db.commit(); db.refresh(user)
    log_activity(db, current_user.id, "ADMIN_CHANGE_ROLE", f"User {user.username} -> {user.role.value}", request.client.host if request.client else None)
    return user

@router.patch("/users/{user_id}/status", response_model=UserResponse, dependencies=[Depends(admin_only)])
def update_status(user_id: int, payload: UserStatusUpdate, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found.")
    user.is_active = payload.is_active
    db.commit(); db.refresh(user)
    log_activity(db, current_user.id, "ADMIN_CHANGE_STATUS", f"User {user.username} active={user.is_active}", request.client.host if request.client else None)
    return user
