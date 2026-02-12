import pandas as pd
from .base import BaseDataAdapter
import logging

logger = logging.getLogger(__name__)

class ExcelAdapter(BaseDataAdapter):
    
    def detect(self) -> bool:
        return self.filename.endswith(('.xls', '.xlsx', '.xlsm'))

    def extract_raw(self) -> pd.DataFrame:
        """
        Lee Excel forzando todo a String para integridad de datos.
        Soporta tanto formatos modernos (.xlsx) como legacy (.xls).
        """
        try:
            # FIX: Determinar motor dinámicamente. 
            # 'openpyxl' es solo para .xlsx. Para .xls dejamos que pandas use 'xlrd' u otro disponible.
            engine = 'openpyxl' if self.filename.endswith(('.xlsx', '.xlsm')) else None
            
            df = pd.read_excel(
                self.file, 
                dtype=str, 
                keep_default_na=False, 
                engine=engine 
            )
            
            # Limpieza básica: Eliminar espacios en blanco en headers
            df.columns = df.columns.astype(str).str.strip()
            
            # Eliminar filas totalmente vacías (basura común al final de los excel)
            df = df.dropna(how='all')
            
            self.raw_data = df
            return df

        except Exception as e:
            logger.error(f"Error crítico leyendo Excel: {str(e)}")
            # Mensaje amigable para el usuario final
            raise ValueError(f"No pudimos leer el archivo. Asegúrate de que no esté protegido con contraseña. Error técnico: {str(e)}")

    def infer_schema(self) -> dict:
        """
        Inteligencia Híbrida: Mira el HEADER y el CONTENIDO para adivinar.
        """
        if self.raw_data is None:
            self.extract_raw()
            
        suggestions = {}
        columns = self.raw_data.columns.tolist()
        
        # 1. Patrones de Header (Para datos personales)
        PATRONES = {
            'first_name': ['nombre', 'nombres', 'name', 'fname'],
            'last_name': ['apellido', 'apellidos', 'lastname', 'lname'],
            'email': ['correo', 'email', 'e-mail'],
            'document_number': ['cedula', 'documento', 'id', 'tarjeta', 'nuip', 'dni', 'codigo'],
        }

        for col in columns:
            col_lower = col.lower()
            found = False
            
            # A) Búsqueda por Nombre de Columna
            for system_field, keywords in PATRONES.items():
                if any(k in col_lower for k in keywords):
                    suggestions[col] = {
                        'tipo': 'POSIBLE_CAMPO_SISTEMA',
                        'campo_sugerido': system_field,
                        'confianza': 0.95
                    }
                    found = True
                    break
            
            # B) Búsqueda por Contenido (Sampling) - CRÍTICO PARA DETECTAR MATERIAS
            # Si el nombre no nos dice nada (ej: "Matematicas"), miramos si los datos son notas.
            if not found:
                try:
                    # Tomamos una muestra y convertimos a números
                    sample = pd.to_numeric(self.raw_data[col], errors='coerce').dropna()
                    if not sample.empty:
                        avg = sample.mean()
                        max_val = sample.max()
                        
                        # Si los datos son números entre 0.0 y 5.0, es muy probable que sea una materia
                        if 0 <= avg <= 5.0 and max_val <= 5.0:
                            suggestions[col] = {
                                'tipo': 'POSIBLE_MATERIA',
                                'campo_sugerido': f'MATERIA:{col}', # Usamos el nombre de la columna como nombre de materia
                                'confianza': 0.8
                            }
                            found = True
                except:
                    pass

            # C) Si todo falla
            if not found:
                suggestions[col] = {'tipo': 'DESCONOCIDO', 'confianza': 0.0}

        return suggestions
