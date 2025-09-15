from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from app.database import Base, engine, get_db_session
from app.models import Task

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="./static"), name="static")
templates = Jinja2Templates(directory="./templates")

# Create DB tables
Base.metadata.create_all(bind=engine)


@app.get("/")
def read_tasks(request: Request, db: Session = Depends(get_db_session)):
    tasks = db.query(Task).order_by(Task.id.desc()).all()
    return templates.TemplateResponse("index.html", {"request": request, "tasks": tasks})


@app.get("/create")
def create_task_form(request: Request):
    return templates.TemplateResponse("create.html", {"request": request})


@app.post("/create")
def create_task(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db_session),
):
    new_task = Task(title=title, description=description)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/edit/{task_id}")
def edit_task_form(request: Request, task_id: int, db: Session = Depends(get_db_session)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return templates.TemplateResponse("edit.html", {"request": request, "task": task})


@app.post("/edit/{task_id}")
def edit_task(
    request: Request,
    task_id: int,
    title: str = Form(...),
    description: str = Form(""),
    completed: str = Form(None),
    db: Session = Depends(get_db_session),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.title = title
    task.description = description
    task.completed = bool(completed)
    db.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.delete("/delete/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db_session)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}


@app.get("/download/pdf")
def download_pdf(db: Session = Depends(get_db_session)):
    tasks = db.query(Task).order_by(Task.id.desc()).all()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph("Task List", styles["Title"]))
    elements.append(Spacer(1, 12))

    # Table data (header + rows)
    data = [["ID", "Title", "Description", "Status"]]
    for task in tasks:
        data.append([
            task.id,
            task.title,
            task.description,
            "Completed" if task.completed else "Pending"
        ])

    # Create table
    table = Table(data, colWidths=[50, 150, 250, 100])

    # Style the table
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ])
    table.setStyle(style)

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=tasks.pdf"},
    )