from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import account, addresses, admin, ai, auth, cart, catalog, health, orders, reviews, seller
from app.services.uploads import UPLOAD_DIR

app = FastAPI(title="Cartium API", version="0.7.0")

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
app.include_router(seller.router)
app.include_router(admin.router)
app.include_router(ai.router)

# Seller photo uploads. (On hosts with temporary disks, use object storage instead; see README.)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/")
def root():
    return {"name": "Cartium API", "docs": "/docs"}
