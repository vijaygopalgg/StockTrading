from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.database import get_db, User
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()

class RegisterIn(BaseModel):
    username: str
    email: EmailStr
    password: str

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str
    username: str
    must_change_pw: bool

@router.post("/register", status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(400, "Username already taken")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(400, "Email already registered")
    if len(payload.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_pw=hash_password(payload.password),
        is_active=True,
        must_change_pw=False,
    )
    db.add(user)
    db.commit()
    return {"message": "Account created. Please log in."}

@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_pw):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    token = create_access_token({"sub": user.username})
    return TokenOut(
        access_token=token,
        token_type="bearer",
        username=user.username,
        must_change_pw=user.must_change_pw,
    )

@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_pw):
        raise HTTPException(400, "Current password is incorrect")
    if len(payload.new_password) < 6:
        raise HTTPException(400, "New password must be at least 6 characters")
    current_user.hashed_pw = hash_password(payload.new_password)
    current_user.must_change_pw = False
    db.commit()
    return {"message": "Password changed successfully"}

@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email}