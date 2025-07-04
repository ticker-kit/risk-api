""" Main application entry point for the risk metrics API. """
from fastapi import FastAPI
from .routes import router

app = FastAPI()
app.include_router(router)
