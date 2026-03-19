import uvicorn
import os
from app.main import app

if __name__ == "__main__":
    # Get port from environment or default to 8000
    port = int(os.environ.get("PORT", 8000))
    # In production, reload should be False
    reload = os.environ.get("DEBUG", "true").lower() == "true"
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload)
