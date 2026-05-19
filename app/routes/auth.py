from fastapi import APIRouter, Form, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

pwd = CryptContext(schemes=["bcrypt"])

@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@router.post("/signup")
def signup(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == email).first():
        return JSONResponse({"message": "User exists"}, status_code=400)

    user = User(email=email, password=pwd.hash(password))
    db.add(user)
    db.commit()

    return {"message": "Signup successful"}

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()

    if not user or not pwd.verify(password, user.password):
        return {"message": "Invalid login"}

    return {"message": "Login success"}