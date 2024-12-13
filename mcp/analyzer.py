import spacy
from typing import Dict, Tuple
import os

class ContentAnalyzer:
    """Analizador de contenido usando spaCy."""
    
    def __init__(self):
        # Cargamos los modelos de spaCy para español e inglés
        self.nlp_es = spacy.load("es_core_news_sm")
        self.nlp_en = spacy.load("en_core_web_sm")
        
        # Palabras clave por categoría
        self.categories = {
            'malware_ransomware': [
                'malware', 'ransomware', 'ransom', 'rescate', 'encriptado', 'encrypted',
                'decrypt', 'desencriptar', 'virus', 'troyano', 'trojan', 'worm', 'gusano',
                'botnet', 'backdoor', 'payload'
            ],
            'phishing_social_engineering': [
                'phishing', 'suplantación', 'suplantacion', 'fake', 'falso',
                'scam', 'estafa', 'fraudulent', 'fraudulento', 'impersonation',
                'social engineering', 'ingeniería social', 'spam', 'spear phishing'
            ],
            'data_breach_leaks': [
                'breach', 'brecha', 'leak', 'filtración', 'filtracion',
                'exposed', 'expuesto', 'compromised', 'comprometido', 'stolen',
                'robo', 'datos', 'data', 'database', 'base de datos', 'dump'
            ],
            'hacking_pentesting': [
                'hacking', 'hacker', 'ethical hacking', 'pentest', 'penetration testing',
                'vulnerability', 'vulnerabilidad', 'exploit', 'zero-day', 'día cero',
                'bug bounty', 'bugbounty', 'red team', 'blue team', 'ctf', 'reverse engineering'
            ],
            'network_security': [
                'firewall', 'ips', 'ids', 'siem', 'network', 'red', 'packet',
                'traffic', 'tráfico', 'monitoring', 'monitoreo', 'vpn',
                'proxy', 'dns', 'ddos', 'mitm', 'man in the middle'
            ],
            'cloud_security': [
                'cloud', 'nube', 'aws', 'azure', 'gcp', 'kubernetes', 'docker',
                'container', 'contenedor', 'serverless', 'iaas', 'paas', 'saas',
                'cloud native', 'misconfiguration', 'misconfiguración'
            ],
            'identity_access': [
                'authentication', 'autenticación', 'mfa', '2fa', 'password',
                'contraseña', 'identity', 'identidad', 'access control',
                'control de acceso', 'privileged', 'privilegiado', 'zero trust'
            ],
            'threat_intelligence': [
                'threat', 'amenaza', 'intelligence', 'inteligencia', 'ioc',
                'indicator', 'indicador', 'apt', 'advanced persistent threat',
                'campaign', 'campaña', 'actor', 'nation state', 'estado nación'
            ],
            'compliance_privacy': [
                'gdpr', 'rgpd', 'compliance', 'cumplimiento', 'privacy',
                'privacidad', 'regulation', 'regulación', 'standard', 'estándar',
                'iso27001', 'pci', 'hipaa', 'audit', 'auditoría'
            ]
        }

        # Hashtags relevantes
        self.relevant_hashtags = [
            '#ciberseguridad', '#cybersecurity', '#hacking', '#hacker', '#infosec',
            '#ethicalhacking', '#cybercrime', '#malware', '#ransomware', '#datasecurity',
            '#security', '#technology', '#programming', '#linux', '#cloudsecurity',
            '#networksecurity', '#dataprotection', '#cyberattack', '#phishing', '#bugbounty'
        ]

    def _get_nlp_model(self, language: str):
        """Selecciona el modelo de NLP según el idioma."""
        return self.nlp_es if language.startswith('es') else self.nlp_en

    def _calculate_relevance(self, doc, category_keywords: list) -> int:
        """Calcula la puntuación de relevancia basada en palabras clave y hashtags."""
        text = doc.text.lower()
        
        # Contamos palabras clave en el texto
        keyword_matches = sum(1 for keyword in category_keywords if keyword in text)
        
        # Contamos hashtags relevantes
        hashtag_matches = sum(1 for hashtag in self.relevant_hashtags if hashtag.lower() in text)
        
        # Análisis de entidades nombradas
        named_entities = len([ent for ent in doc.ents if ent.label_ in ['ORG', 'PRODUCT', 'GPE', 'TECH']])
        
        # Calculamos la puntuación (máximo 100)
        base_score = min(keyword_matches * 15, 40)  # Máximo 40 puntos por palabras clave
        hashtag_score = min(hashtag_matches * 10, 30)  # Máximo 30 puntos por hashtags
        entity_score = min(named_entities * 10, 30)  # Máximo 30 puntos por entidades
        
        return min(base_score + hashtag_score + entity_score, 100)

    def analyze_tweet(self, content: str, language: str) -> Tuple[str, int]:
        """Analiza el contenido del tweet y determina su categoría y relevancia."""
        nlp = self._get_nlp_model(language)
        doc = nlp(content)
        
        best_category = None
        best_score = 0
        
        # Analizamos cada categoría
        for category, keywords in self.categories.items():
            relevance = self._calculate_relevance(doc, keywords)
            if relevance > best_score:
                best_score = relevance
                best_category = category
        
        # Si no encontramos una categoría clara o la relevancia es muy baja
        if best_score < 30:
            return None, 0
            
        return best_category, best_score

    def get_summary(self, content: str, language: str) -> str:
        """Genera un resumen del contenido."""
        nlp = self._get_nlp_model(language)
        doc = nlp(content)
        
        # Extraemos las entidades más relevantes
        entities = [ent.text for ent in doc.ents if ent.label_ in ['ORG', 'PRODUCT', 'GPE', 'TECH']]
        
        # Extraemos hashtags
        hashtags = [word for word in content.split() if word.startswith('#')]
        
        # Seleccionamos las oraciones más relevantes
        sentences = list(doc.sents)
        if not sentences:
            return content[:100] + "..."
            
        # Tomamos la primera oración como resumen
        summary = next(doc.sents).text
        
        # Añadimos entidades y hashtags si no están en el resumen
        if entities or hashtags:
            extra_info = []
            if entities:
                extra_info.append(f"Entidades: {', '.join(set(entities))}")
            if hashtags:
                extra_info.append(f"Tags: {', '.join(set(hashtags))}")
            
            extra_text = " | ".join(extra_info)
            if len(summary) + len(extra_text) + 5 <= 280:  # Límite de Twitter
                summary += f" [{extra_text}]"
                
        return summary 