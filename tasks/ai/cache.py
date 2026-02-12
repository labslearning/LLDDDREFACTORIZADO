# tasks/ai/cache.py

import hashlib
import json
from django.utils import timezone
from datetime import timedelta
from tasks.models import AIUsageLog, PEIResumen
from .constants import MODEL_NAME

class PedagogicCache:
    """
    EL MEMORIOSO (Sistema de Caché Institucional).
    
    Principios de Diseño:
    1. Semántico: Importa el contexto exacto (notas, reportes), no solo el usuario.
    2. Sensible al PEI: Si el manual de convivencia cambia, el caché caduca.
    3. Trazable: Se basa en la huella digital (Hash) guardada en los Logs.
    """
    
    PROMPT_VERSION = "v1.0"  # Incrementa esto si cambias la lógica en prompts.py
    CACHE_TTL_HOURS = 12     # Tiempo de vida del caché

    def calculate_hash(self, contexto_json):
        """
        Genera el hash SHA256. 
        CORRECCIÓN: Aseguramos que solo se pasen strings al JSON para evitar errores de serialización.
        """
        # 1. Obtenemos el periodo o un string por defecto
        try:
            pei_activo = PEIResumen.objects.filter(activo=True).first()
            
            # IMPORTANTE: Aquí extraemos el hash o un string, NUNCA el objeto completo de la DB
            pei_version = "NO_PEI"
            if pei_activo:
                # Usamos el atributo 'resumen_hash' que es un string seguro para JSON
                pei_version = str(pei_activo.resumen_hash)
        except Exception:
            pei_version = "DB_ERROR"

        # 2. Construcción del payload para el hash
        payload = {
            "data": contexto_json,      
            "pei_ver": pei_version,
            "prompt_ver": self.PROMPT_VERSION, 
            "model": MODEL_NAME         
        }
        
        # 3. Serialización determinista (sort_keys=True es vital para la consistencia del hash)
        # ensure_ascii=False permite manejar tildes y caracteres especiales correctamente
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
        
        return hashlib.sha256(encoded).hexdigest()

    def get_cached_response(self, usuario, accion, contexto_dict):
        """
        Intenta recuperar una respuesta previa idéntica de la base de datos.
        
        Returns:
            dict | None: Datos de la respuesta si existe, o None si no.
        """
        # 1. Calcular la Huella Digital Única (Fingerprint)
        current_hash = self.calculate_hash(contexto_dict)
        
        # 2. Definir ventana de validez (Ej: 12 horas)
        fecha_limite = timezone.now() - timedelta(hours=self.CACHE_TTL_HOURS)
        
        # 3. Consultar la "Caja Negra" (AIUsageLog)
        # Buscamos logs exitosos recientes que tengan ESTE MISMO hash en su metadata técnica.
        try:
            log_previo = AIUsageLog.objects.filter(
                usuario=usuario,
                accion=accion,
                fecha__gte=fecha_limite,
                exitoso=True,
                metadata_tecnica__context_hash=current_hash 
            ).order_by('-fecha').first()
            
            if log_previo:
                content = log_previo.metadata_tecnica.get('response_content')
                if content:
                    # ¡Éxito! Recuperamos el contenido del log anterior
                    return {
                        "cached": True,
                        "content": content,
                        "hash": current_hash,
                        "fecha": log_previo.fecha,
                        "log_id": log_previo.id
                    }
        except Exception:
            # Si falla la base de datos por cualquier motivo, simplemente ignoramos el caché
            pass 
            
        # 4. Cache Miss (No encontramos nada válido)
        return None

# Instancia global para ser utilizada en el orquestador
ai_cache = PedagogicCache()