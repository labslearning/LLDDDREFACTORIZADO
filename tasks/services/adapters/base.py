from abc import ABC, abstractmethod
import pandas as pd
from typing import BinaryIO, Dict, Any

class BaseDataAdapter(ABC):
    """
    CONTRATO DE INTERFAZ:
    Define la estructura obligatoria para cualquier lector de archivos.
    Garantiza que el sistema sea agnóstico al formato de entrada.
    """
    def __init__(self, file_obj: BinaryIO):
        self.file = file_obj
        try:
            self.filename = file_obj.name.lower()
        except AttributeError:
            self.filename = "unknown_stream"
        self.raw_data = None 

    @abstractmethod
    def detect(self) -> bool:
        """Devuelve True si este adaptador puede leer este tipo de archivo."""
        pass

    @abstractmethod
    def extract_raw(self) -> pd.DataFrame:
        """
        Debe devolver un DataFrame de Pandas con todos los datos como STRING.
        IMPORTANTE: dtype=str para evitar '007' -> 7.
        """
        pass

    @abstractmethod
    def infer_schema(self) -> Dict[str, Any]:
        """
        Analiza las columnas y sugiere qué son.
        """
        pass
