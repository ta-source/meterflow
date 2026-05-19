from fastapi import APIRouter, Form, Depends
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.models import Meter

router = APIRouter()

@router.post("/add")
def add(value: float = Form(...), db: Session = Depends(get_db)):
    db.add(Meter(value=value, date=date.today()))
    db.commit()
    return {"msg": "added"}

@router.get("/data")
def data(db: Session = Depends(get_db)):
    rows = db.query(Meter).all()

    result = []
    prev = None
    for r in rows:
        usage = r.value - prev if prev else 0
        result.append({"value": r.value, "usage": usage})
        prev = r.value

    return result