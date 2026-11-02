from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import account, addresses, auth, cart, catalog, health, orders, reviews

app = FastAPI(title="Cartium API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(account.router)
app.include_router(reviews.router)
app.include_router(cart.router)
app.include_router(addresses.router)
app.include_router(orders.router)


@app.get("/")
def root():
    return {"name": "Cartium API", "docs": "/docs"}
