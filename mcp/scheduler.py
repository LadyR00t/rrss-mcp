from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import asyncio

from .api import process_tweets, cleanup_old_data
from .reporter import ReportGenerator

class TaskScheduler:
    """Programador de tareas para el sistema MCP."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.report_generator = ReportGenerator()
        
    def start(self):
        """Inicia el programador de tareas."""
        # Recolectar tweets cada hora
        self.scheduler.add_job(
            process_tweets,
            CronTrigger(minute=0),  # Cada hora en punto
            id='collect_tweets',
            name='Recolección de tweets'
        )
        
        # Generar informe diario a las 00:05
        self.scheduler.add_job(
            self.generate_daily_report,
            CronTrigger(hour=0, minute=5),
            id='generate_report',
            name='Generación de informe diario'
        )
        
        # Limpiar datos antiguos a las 00:30
        self.scheduler.add_job(
            cleanup_old_data,
            CronTrigger(hour=0, minute=30),
            id='cleanup_data',
            name='Limpieza de datos antiguos'
        )
        
        self.scheduler.start()
        return self.scheduler
        
    async def generate_daily_report(self):
        """Genera el informe diario."""
        try:
            yesterday = datetime.utcnow()
            await self.report_generator.generate_daily_report(yesterday)
        except Exception as e:
            print(f"Error al generar el informe diario: {str(e)}")

    def shutdown(self):
        """Detiene el scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()

def start_scheduler():
    """Inicia el programador de tareas."""
    scheduler = TaskScheduler()
    return scheduler
    
    try:
        # Mantener el programa en ejecución
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass 