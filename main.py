from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from core.database import init_db_pool, close_db_pool
# Import payment router for Airtel integration
from routers import auth, books, library, admin, upload_book, airtel, currency

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    yield
    await close_db_pool()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://litn.vercel.app","https://litnfrontend.vercel.app","https://bookappfrontend-five.vercel.app"],
    allow_origin_regex=r"http://(?:localhost|127\.0\.0\.1)(?::[0-9]+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(library.router)
app.include_router(admin.router)
app.include_router(upload_book.router)
# Register Airtel payments router (handles initiation and webhook callbacks)
app.include_router(airtel.router)
# Currency rates endpoints for frontend currency detection and conversion
app.include_router(currency.router)
