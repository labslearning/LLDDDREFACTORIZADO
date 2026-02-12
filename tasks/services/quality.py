import re
import logging

logger = logging.getLogger(__name__)

class DataGuard:
    """
    ��️ DATAGUARD: SISTEMA DE SANITIZACIÓN
    
    Su misión es limpiar la 'basura' que viene en los Excel (espacios, formatos raros)
    y convertirla en datos útiles para el sistema.
    """

    @staticmethod
    def clean_text(value) -> str:
        """Elimina espacios extra, saltos de línea y caracteres invisibles."""
        if value is None: return ""
        return str(value).strip()

    @staticmethod
    def clean_email(value) -> str:
        """Normaliza correos: minúsculas, sin espacios y validación básica."""
        if not value: return ""
        val = str(value).lower().strip()
        # Regex simple para detectar si parece un correo
        if re.match(r"[^@]+@[^@]+\.[^@]+", val):
            return val
        return ""

    @staticmethod
    def clean_grade(value) -> float:
        """
        TRANSFORMADOR DE NOTAS INTELIGENTE:
        Convierte '4,5', '4.5', '45', 'Básico' en un float seguro.
        """
        if value is None or value == "": return 0.0
        
        # 1. Escala Cualitativa (Personalizable por institución en el futuro)
        SCALES = {
            'BAJO': 2.0, 'BJ': 2.0,
            'BASICO': 3.5, 'BS': 3.5, 'BÁSICO': 3.5,
            'ALTO': 4.3, 'AL': 4.3,
            'SUPERIOR': 4.8, 'SP': 4.8
        }
        
        s_val = str(value).strip().upper()
        if s_val in SCALES:
            return SCALES[s_val]

        try:
            # 2. Normalización Decimal (Latinoamérica ',' vs USA '.')
            clean_val = s_val.replace(',', '.')
            f_val = float(clean_val)

            # 3. Corrección Heurística de Errores de Digitación
            # Escenario: Profesor digita '45' queriendo decir '4.5'
            # Asumimos escala 0-5. Si tu colegio es 0-10 o 0-100, ajusta esta lógica.
            if 5.0 < f_val <= 50.0:
                return f_val / 10.0
            
            return f_val
        except ValueError:
            # Si no es número ni texto conocido, devolvemos 0.0 (o podrías lanzar error)
            return 0.0
