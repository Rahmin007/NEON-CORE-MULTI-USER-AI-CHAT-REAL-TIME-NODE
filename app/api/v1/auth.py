from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserResponse
from app.services.activity_service import log_activity

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(or_(User.username == payload.username, User.email == payload.email)))
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already exists.")
    user = User(username=payload.username, email=str(payload.email), hashed_password=get_password_hash(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    log_activity(user.id, user.username, "REGISTER", "Account created", request.client.host if request.client else None)
    return user

@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == form_data.username))
    if not user or not verify_password(form_data.password, user.hashed_password):
        log_activity(user.id if user else None, user.username if user else form_data.username, "LOGIN_FAILED", f"Attempted username: {form_data.username}", request.client.host if request.client else None)
        raise HTTPException(status_code=401, detail="Incorrect username or password.", headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled.")
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    log_activity(user.id, user.username, "LOGIN_SUCCESS", None, request.client.host if request.client else None)
    return {"access_token": token, "token_type": "bearer"}
