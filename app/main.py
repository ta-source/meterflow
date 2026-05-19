
import httpx
import requests
import secrets
import razorpay
from requests import api
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.extension import _rate_limit_exceeded_handler
from datetime import datetime
from jose import jwt, JWTError
from fastapi import FastAPI, Request, Form, Depends, Response
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Header, HTTPException
from sqlalchemy.orm import Session
from app.models import API
from sqlalchemy import func
from app.database import SessionLocal, engine, Base
from app.models import User, Reading, APIKey, APILog, UsageLog, Billing

from app.auth import (hash_password,verify_password,create_access_token,verify_token)
from dotenv import load_dotenv
import os

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET").strip()

client = razorpay.Client(
    auth=(
        RAZORPAY_KEY_ID,
        RAZORPAY_KEY_SECRET
    )
)
# JWT SETTINGS
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
# =========================
# APP
# =========================

app = FastAPI()

limiter = Limiter(
    key_func=get_remote_address
)

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

app.add_middleware(SlowAPIMiddleware)

Base.metadata.create_all(bind=engine)

# =========================
# STATIC + TEMPLATES
# =========================

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# =========================
# DATABASE
# =========================

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()

# 👇 PASTE JWT USER FUNCTION HERE
def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):

    token = request.cookies.get(
        "access_token"
    )

    if not token:

        return None

    try:

        # REMOVE "Bearer "
        token = token.replace(
            "Bearer ",
            ""
        )

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get(
            "user_id"
        )

        if not user_id:

            return None

    except JWTError:

        return None

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    return user
# VERIFY API KEY
async def verify_api_key(
    x_api_key: str = Header(None),
    db: Session = Depends(get_db)
):

    if not x_api_key:

        raise HTTPException(
            status_code=401,
            detail="API Key missing"
        )

    api_key = db.query(APIKey).filter(
        APIKey.api_key == x_api_key
    ).first()

    if not api_key:

        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )

    return api_key
# =========================
# HOME
# =========================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):

    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request}
    )

# =========================
# SIGNUP PAGE
# =========================

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):

    return templates.TemplateResponse(
        request,
        "signup.html",
        {"request": request}
    )

# =========================
# SIGNUP
# =========================

@app.post("/signup")
async def signup(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    existing_user = db.query(User).filter(
        User.email == email
    ).first()

    if existing_user:

        return templates.TemplateResponse(
            request,
            "signup.html",
            {
                "request": request,
                "error": "User already exists"
            }
        )

    if len(password.encode("utf-8")) > 72:

        return templates.TemplateResponse(
            request,
            "signup.html",
            {
                "request": request,
                "error": "Password must be under 72 characters"
            }
        )

    new_user = User(
        email=email,
        password=hash_password(password)
    )

    db.add(new_user)
    db.commit()

    return RedirectResponse(
        url="/login",
        status_code=302
    )

# =========================
# LOGIN PAGE
# =========================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):

    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request}
    )

# =========================
# LOGIN
# =========================

@app.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.email == email
    ).first()

    if not user:

        return RedirectResponse(
            "/login",
            status_code=302
        )

    valid = verify_password(
        password,
        user.password
    )

    if not valid:

        return RedirectResponse(
            "/login",
            status_code=302
        )

    # JWT TOKEN
    token = create_access_token(
        data={
            "user_id": user.id
        }
    )

    response = RedirectResponse(
        "/dashboard",
        status_code=303
    )

    # STORE COOKIE
    response.set_cookie(
        key="user_id",
        value=str(user.id)
    )

    # STORE JWT
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True
    )

    return response
# =========================
# DASHBOARD
# =========================

@app.get("/dashboard")
async def dashboard(
    request: Request,
    db: Session = Depends(get_db)
):

    user_id = request.cookies.get("user_id")

    if not user_id:

        return RedirectResponse(
            "/login",
            status_code=302
        )

    readings = db.query(Reading).filter(
        Reading.user_id == int(user_id)
    ).all()

    api_keys = db.query(APIKey).filter(
        APIKey.user_id == int(user_id)
    ).all()
    apis = db.query(API).filter(
        API.owner_id == int(user_id)
    ).all()

    logs = db.query(APILog).order_by(
        APILog.id.desc()
    ).limit(5).all()

    total_units = sum(
        r.units for r in readings
    )

    revenue = total_units * 5

    total_requests = db.query(
        APILog
    ).count()

    labels = [
        r.reading_date.strftime("%d %b")
        for r in readings
    ]

    values = [
        r.units
        for r in readings
    ]

    for r in readings:

        labels.append(
            r.reading_date.strftime("%d %b")
        )

        values.append(r.units)
    billing = None

    if api_keys:
        billing = db.query(Billing).filter(
            Billing.api_key == api_keys[0].api_key
        ).first()
    apis = db.query(API).all()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "readings": readings,
            "api_keys": api_keys,
            "logs": logs,
            "revenue": revenue,
            "total_requests": total_requests,
            "total_units": total_units,
            "labels": labels,
            "values": values,
            "billing": billing,
            "apis": apis,
        }
    )
@app.get("/plans")
async def plans_page(request: Request):

    plans = [

        {
            "name": "Free",
            "price": 0,
            "limit": 100
        },

        {
            "name": "Starter",
            "price": 199,
            "limit": 10000
        },

        {
            "name": "Pro",
            "price": 999,
            "limit": 100000
        }

    ]

    return templates.TemplateResponse(
        request,
        "plans.html",
        {
            "request": request,
            "razorpay_key_id": RAZORPAY_KEY_ID

        }
    )


# =========================
# ADD READING
# =========================

@app.post("/add-reading")
async def add_reading(
    request: Request,
    reading_date: str = Form(...),
    units: float = Form(...),
    db: Session = Depends(get_db)
):

    user_id = request.cookies.get("user_id")

    if not user_id:

        return RedirectResponse(
            "/login",
            status_code=302
        )

    # Convert string → Python date object
    parsed_date = datetime.strptime(
        reading_date,
        "%Y-%m-%d"
    ).date()

    reading = Reading(
        user_id=int(user_id),
        reading_date=parsed_date,
        units=units
    )

    db.add(reading)

    db.commit()

    return RedirectResponse(
        "/dashboard",
        status_code=303
    )


@app.get("/gateway/{route_name}")
async def gateway_proxy(
    route_name: str,
    x_api_key: str = Header(None)
):

    db = SessionLocal()

    # =========================
    # VALIDATE API KEY
    # =========================

    api_key = db.query(APIKey).filter(
        APIKey.api_key == x_api_key
    ).first()

    if not api_key:

        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )

    # =========================
    # FIND API ROUTE FROM DATABASE
    # =========================

    api_route = db.query(API).filter(
        API.route == route_name
    ).first()

    if not api_route:

        raise HTTPException(
            status_code=404,
            detail="Route not found"
        )

    target_url = api_route.upstream_url

    try:

        # =========================
        # FORWARD REQUEST
        # =========================

        response = requests.get(target_url)

        # =========================
        # STORE API LOG
        # =========================

        log = APILog(
            api_key=x_api_key,
            endpoint=route_name,
            method="GET",
            status_code=response.status_code
        )

        db.add(log)

        # =========================
        # STORE USAGE LOG
        # =========================

        usage_log = UsageLog(
            api_key=x_api_key,
            endpoint=route_name,
            method="GET",
            status_code=response.status_code
        )

        db.add(usage_log)

        # =========================
        # BILLING SYSTEM
        # =========================

        billing = db.query(Billing).filter(
            Billing.api_key == x_api_key
        ).first()

        if not billing:

            billing = Billing(
                api_key=x_api_key,
                total_requests=0,
                total_cost=0,
                plan="Free"
            )

            db.add(billing)

        # COUNT REQUEST
        billing.total_requests += 1

        # =========================
        # PLAN LIMITS
        # =========================

        plan_limits = {
            "Free": 5,
            "Starter": 100,
            "Pro": 999999
        }

        current_limit = plan_limits.get(
            billing.plan,
            5
        )

        # BLOCK IF LIMIT EXCEEDED

        if billing.total_requests > current_limit:

            raise HTTPException(
                status_code=403,
                detail="Plan limit exceeded. Upgrade your subscription."
            )

        # =========================
        # BILLING AMOUNT
        # =========================

        if billing.plan == "Starter":

            billing.total_cost = 199

        elif billing.plan == "Pro":

            billing.total_cost = 499

        else:

            billing.total_cost = 0

        db.commit()

        # =========================
        # RETURN REAL API RESPONSE
        # =========================

        return response.json()

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/create-api")
async def create_api(

    request: Request,

    name: str = Form(...),

    route: str = Form(...),

    upstream_url: str = Form(...),

    db: Session = Depends(get_db)

):

    user_id = request.cookies.get("user_id")

    if not user_id:

        return RedirectResponse(
            "/login",
            status_code=302
        )
    existing_route = db.query(API).filter(
        API.route == route
    ).first()

    if existing_route:
        raise HTTPException(
            status_code=400,
            detail="Route already exists"
        )
    new_api = API(

        name=name,

        route=route,

        upstream_url=upstream_url,

        owner_id=int(user_id)

    )

    db.add(new_api)

    db.commit()

    return RedirectResponse(
        "/dashboard",
        status_code=303
    )
# =========================
# DELETE READING
# =========================

@app.post("/delete-reading/{id}")
async def delete_reading(
    id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    user_id = request.cookies.get("user_id")

    reading = db.query(Reading).filter(
        Reading.id == id,
        Reading.user_id == int(user_id)
    ).first()

    if reading:

        db.delete(reading)
        db.commit()

    return RedirectResponse(
        "/dashboard",
        status_code=302
    )

# =========================
# API KEYS PAGE
# =========================

@app.get("/api-keys")
async def api_keys_page(
    request: Request,
    db: Session = Depends(get_db)
):

    user_id = request.cookies.get("user_id")

    if not user_id:

        return RedirectResponse(
            "/login",
            status_code=302
        )

    api_keys = db.query(APIKey).filter(
        APIKey.user_id == int(user_id)
    ).all()


    return templates.TemplateResponse(
        request,
        "api_keys.html",
        {"request": request, "api_keys": api_keys})
# =========================
# GENERATE API KEY
# =========================

import secrets


@app.post("/generate-api-key")
async def generate_api_key(
    request: Request,
    db: Session = Depends(get_db)
):

    user_id = request.cookies.get(
        "user_id"
    )

    if not user_id:

        return RedirectResponse(
            "/login",
            status_code=302
        )

    generated_key = secrets.token_hex(24)

    new_key = APIKey(
        user_id=int(user_id),
        api_key=generated_key
    )

    db.add(new_key)

    db.commit()

    db.refresh(new_key)

    return RedirectResponse(
        "/api-keys",
        status_code=303
    )
@app.post("/delete-api-key/{key_id}")

async def delete_api_key(

    key_id: int,

    db: Session = Depends(get_db)

):

    api_key = db.query(APIKey).filter(
        APIKey.id == key_id
    ).first()

    if api_key:

        db.delete(api_key)

        db.commit()

    return RedirectResponse(
        "/api-keys",
        status_code=303
    )

# Protected API
# -----------------------------
@app.get("/api/data")
@limiter.limit("5/minute")
async def api_data(
    request: Request,
    x_api_key: str = Header(None),
    db: Session = Depends(get_db)
):

    api_key = db.query(APIKey).filter(
        APIKey.api_key == x_api_key
    ).first()

    # INVALID API KEY
    if not api_key:

        failed_log = APILog(
            api_key=x_api_key,
            endpoint="/api/data",
            method="GET",
            status_code=401
        )

        db.add(failed_log)

        db.commit()

        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )
    # SUCCESS LOG

    success_log = APILog(
        api_key=x_api_key,
        endpoint="/api/data",
        method="GET",
        status_code=200
    )

    db.add(success_log)
    db.commit()

    return {
        "message": "API Access Granted",
        "status": "success"
    }

# =========================
# LOGS PAGE
# =========================

@app.get("/logs")
async def logs(
    request: Request,
    db: Session = Depends(get_db)
):

    user_id = request.cookies.get("user_id")

    if not user_id:

        return RedirectResponse(
            "/login",
            status_code=302
        )

    logs = db.query(APILog).order_by(
        APILog.id.desc()
    ).all()
    return templates.TemplateResponse(
        request,
        "logs.html",
        {"request": request,"logs": logs})
# =========================
# BILLING
# =========================

@app.get("/billing")
async def billing_page(
    request: Request,
    db: Session = Depends(get_db)
):

    bills = db.query(Billing).all()

    return templates.TemplateResponse(
        request,
        "billing.html",
        {
            "request": request,
            "bills": bills

        }
    )





# =========================
# LOGOUT
# =========================

@app.get("/logout")
async def logout():

    response = RedirectResponse(
        "/login",
        status_code=302
    )

    response.delete_cookie("user_id")

    response.delete_cookie("access_token")

    return response
@app.post("/create-payment/{amount}")
async def create_payment(amount: int):

    payment = client.order.create({

        "amount": amount * 100,

        "currency": "INR",

        "payment_capture": 1
    })

    return {

        "order_id": payment["id"],

        "amount": payment["amount"]
    }
@app.post("/upgrade-plan")
async def upgrade_plan(
    request: Request,
    plan: str = Form(...),
    db: Session = Depends(get_db)
):

    user_id = request.cookies.get("user_id")

    if not user_id:

        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    api_key = db.query(APIKey).filter(
        APIKey.user_id == int(user_id)
    ).first()

    if not api_key:

        raise HTTPException(
            status_code=404,
            detail="Generate API key first"
        )

    billing = db.query(Billing).filter(
        Billing.api_key == api_key.api_key
    ).first()

    if not billing:

        billing = Billing(
            api_key=api_key.api_key,
            total_requests=0,
            total_cost=0,
            plan=plan
        )

        db.add(billing)

    billing.plan = plan

    # RESET REQUEST COUNT
    billing.total_requests = 0

    # PLAN PRICE

    if plan == "Starter":

        billing.total_cost = 199

    elif plan == "Pro":

        billing.total_cost = 499

    else:

        billing.total_cost = 0

    db.commit()

    return {
        "message": f"{plan} Plan Activated Successfully"
    }
@app.get("/playground")
async def playground(
    request: Request
):

    return templates.TemplateResponse(
        request,
        "playground.html",
        {
            "request": request
        }
    )