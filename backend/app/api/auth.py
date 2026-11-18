from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authentication.dependencies import get_current_user, require_admin
from app.authentication.security import create_access_token, hash_password, verify_password
from app.database.session import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserOut


router = APIRouter(prefix="/auth", tags=["Auth"])



@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where(or_(User.username == data.username, User.email == data.email))
    )
    if existing.first():
        raise HTTPException(status_code=409, detail="Username or email already registered")


    user_count = await db.scalar(select(func.count(User.id)))
    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role="admin" if user_count == 0 else "employee",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user



@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return Token(access_token=create_access_token(user.id, user.role))



@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user



@router.get("/users", response_model=list[UserOut])
async def list_users(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()