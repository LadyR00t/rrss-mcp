import os
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader
from .models import Tweet, Report, get_session

class ReportGenerator:
    """Generador de informes HTML con gráficos."""
    
    def __init__(self):
        self.template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.reports_dir = os.path.join(os.getcwd(), 'reports')
        
        # Crear directorio de reportes si no existe
        os.makedirs(self.reports_dir, exist_ok=True)
        
        # Configurar Jinja2
        self.env = Environment(loader=FileSystemLoader(self.template_dir))

    def _create_category_chart(self, df: pd.DataFrame) -> str:
        """Crea un gráfico de barras por categoría."""
        fig = px.bar(
            df.groupby('category').size().reset_index(name='count'),
            x='category',
            y='count',
            title='Incidentes por Categoría',
            labels={'category': 'Categoría', 'count': 'Número de Incidentes'}
        )
        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def _create_timeline_chart(self, df: pd.DataFrame) -> str:
        """Crea un gráfico de línea temporal."""
        daily_counts = df.groupby(['category', pd.Grouper(key='created_at', freq='D')]).size().reset_index(name='count')
        fig = px.line(
            daily_counts,
            x='created_at',
            y='count',
            color='category',
            title='Tendencia Temporal de Incidentes',
            labels={'created_at': 'Fecha', 'count': 'Número de Incidentes', 'category': 'Categoría'}
        )
        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def _create_relevance_chart(self, df: pd.DataFrame) -> str:
        """Crea un gráfico de caja para mostrar la distribución de relevancia."""
        fig = px.box(
            df,
            x='category',
            y='relevance_score',
            title='Distribución de Relevancia por Categoría',
            labels={'category': 'Categoría', 'relevance_score': 'Puntuación de Relevancia'}
        )
        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def generate_daily_report(self, date: datetime = None) -> str:
        """Genera el informe diario."""
        if date is None:
            date = datetime.utcnow()
            
        # Obtener tweets del día
        session = get_session()
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        tweets = session.query(Tweet).filter(
            Tweet.created_at >= start_date,
            Tweet.created_at < end_date
        ).all()
        
        if not tweets:
            return None
            
        # Crear DataFrame
        df = pd.DataFrame([{
            'category': t.category,
            'created_at': t.created_at,
            'relevance_score': t.relevance_score,
            'content': t.content,
            'author': t.author
        } for t in tweets])
        
        # Generar gráficos
        category_chart = self._create_category_chart(df)
        timeline_chart = self._create_timeline_chart(df)
        relevance_chart = self._create_relevance_chart(df)
        
        # Calcular estadísticas
        total_tweets = len(tweets)
        categories_count = df['category'].value_counts().to_dict()
        
        # Ejemplos más relevantes por categoría
        top_examples = {}
        for category in df['category'].unique():
            cat_tweets = df[df['category'] == category].nlargest(3, 'relevance_score')
            top_examples[category] = cat_tweets.to_dict('records')
        
        # Generar HTML
        template = self.env.get_template('daily_report.html')
        report_html = template.render(
            date=date.strftime('%Y-%m-%d'),
            total_tweets=total_tweets,
            categories_count=categories_count,
            category_chart=category_chart,
            timeline_chart=timeline_chart,
            relevance_chart=relevance_chart,
            top_examples=top_examples
        )
        
        # Guardar reporte
        report_filename = f"report_{date.strftime('%Y%m%d')}.html"
        report_path = os.path.join(self.reports_dir, report_filename)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_html)
            
        # Guardar metadata en la base de datos
        report = Report(
            date=date,
            total_tweets=total_tweets,
            categories_count=categories_count,
            summary=f"Análisis de {total_tweets} tweets sobre incidentes de seguridad",
            report_path=report_filename
        )
        session.add(report)
        session.commit()
        
        return report_path 