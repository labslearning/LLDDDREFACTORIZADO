from django.db.models import F
from tasks.models import ColumnMapping

class SchemaLearner:
    """
    🧠 HIPPOCAMPUS: GESTOR DE MEMORIA DE MAPEOS
    
    Responsable de recordar que 'Ape. Pat.' significa 'last_name' 
    para ahorrarle trabajo al usuario en el futuro.
    """

    @staticmethod
    def get_historical_suggestion(csv_header: str, model_type: str, institucion_id=None):
        """
        Consulta la base de conocimientos para ver si reconocemos esta columna.
        Prioriza la memoria específica de la institución, luego la global.
        """
        clean_header = csv_header.strip()

        # 1. Memoria Específica (Lo que este colegio ha hecho antes)
        if institucion_id:
            mapping = ColumnMapping.objects.filter(
                institucion_id=institucion_id,
                modelo_objetivo=model_type,
                nombre_columna_csv__iexact=clean_header
            ).order_by('-confianza', '-usado_veces').first()
            
            if mapping: return mapping.campo_sistema

        # 2. Memoria Global (Inteligencia Colectiva de todos los usuarios)
        global_mapping = ColumnMapping.objects.filter(
            modelo_objetivo=model_type,
            nombre_columna_csv__iexact=clean_header
        ).order_by('-confianza', '-usado_veces').first()

        return global_mapping.campo_sistema if global_mapping else None

    @staticmethod
    def learn(csv_header: str, system_field: str, model_type: str, institucion_id=None):
        """
        Refuerza el aprendizaje neuronal del sistema.
        Llamar a esto cuando el usuario confirma un mapeo exitoso.
        """
        clean_header = csv_header.strip()
        
        # Buscamos o creamos el recuerdo
        obj, created = ColumnMapping.objects.get_or_create(
            institucion_id=institucion_id,
            modelo_objetivo=model_type,
            nombre_columna_csv=clean_header,
            defaults={'campo_sistema': system_field, 'confianza': 1.0}
        )

        if not created:
            # Si el significado cambió, reiniciamos el aprendizaje
            if obj.campo_sistema != system_field:
                obj.campo_sistema = system_field
                obj.confianza = 1.0
                obj.usado_veces = 1 
            else:
                # Si confirmó lo que ya sabíamos, reforzamos la confianza
                obj.usado_veces = F('usado_veces') + 1
            
            obj.save()
