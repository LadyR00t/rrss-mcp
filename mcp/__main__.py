import uvicorn
import asyncio
import os
from multiprocessing import Process
from .scheduler import start_scheduler
from .api import app

def ensure_reports_dir():
    """Asegura que existe el directorio de reportes."""
    reports_dir = os.path.join(os.getcwd(), 'reports')
    os.makedirs(reports_dir, exist_ok=True)

def run_api():
    """Ejecuta el servidor API."""
    ensure_reports_dir()
    uvicorn.run(app, host="0.0.0.0", port=8000)

async def run_scheduler():
    """Ejecuta el scheduler en un event loop."""
    scheduler = start_scheduler()
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        scheduler.shutdown()

def main():
    """Punto de entrada principal."""
    # Crear directorio de reportes
    ensure_reports_dir()
    
    # Iniciar el API en un proceso separado
    api_process = Process(target=run_api)
    api_process.start()
    
    # Iniciar el scheduler en el event loop principal
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_scheduler())
    except KeyboardInterrupt:
        print("\nDeteniendo el sistema...")
        api_process.terminate()
        api_process.join()
        loop.close()

if __name__ == "__main__":
    main() 