from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import traceback

from database import Base, engine, run_migrations, check_migrations
from config import settings
from api.accounts import router as accounts_router
from api.transfers import router as transfers_router
from api.deposits_withdrawals import router as deposits_withdrawals_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Financial Ledger API with Double-Entry Bookkeeping",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Run migrations on startup
@app.on_event("startup")
async def startup_event():
    """Run database migrations on application startup"""
    try:
        # Check if migrations are needed
        if check_migrations():
            logger.info("Running database migrations...")
            run_migrations()
            logger.info("Database migrations completed")
        
        # Create tables (for development only - migrations handle production)
        if settings.DEBUG:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created (development mode)")
            
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )

@app.get("/health")
async def health_check():
    """Health check endpoint with database status"""
    try:
        # Check database connection
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            db_status = "connected" if result else "disconnected"
        
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "database": db_status,
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": settings.APP_NAME,
            "database": "disconnected",
            "error": str(e)
        }

@app.get("/migrations/status")
async def migration_status():
    """Check migration status"""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        
        alembic_cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(alembic_cfg)
        head_revision = script.get_current_head()
        
        return {
            "status": "ok",
            "head_revision": head_revision,
            "message": "Migrations are up-to-date"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

# Include routers
app.include_router(accounts_router, prefix=settings.API_PREFIX)
app.include_router(transfers_router, prefix=settings.API_PREFIX)
app.include_router(deposits_withdrawals_router, prefix=settings.API_PREFIX)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
