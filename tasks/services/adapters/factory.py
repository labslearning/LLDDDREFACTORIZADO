import logging
from typing import Type, List
from django.core.files.uploadedfile import UploadedFile

# Importamos la interfaz base (El Contrato)
from .base import BaseDataAdapter

# Importamos la implementación concreta.
# NOTA: Importamos de '.excel' porque así se llama tu archivo (excel.py)
from .excel import ExcelAdapter 

logger = logging.getLogger(__name__)

class AdapterFactory:
    """
    🏭 FACTORY PATTERN: SELECTOR DE DRIVERS DE IMPORTACIÓN
    
    Responsabilidad única:
    Recibir un archivo binario desconocido y retornar la instancia del 
    adaptador específico (Driver) capaz de interpretarlo.
    
    Principio Open/Closed:
    Para agregar soporte a CSV o JSON, solo agregas la clase a la lista
    _REGISTERED_DRIVERS sin modificar la lógica de detección.
    """

    # Registro centralizado de drivers soportados.
    # El sistema probará uno por uno en este orden.
    _REGISTERED_DRIVERS: List[Type[BaseDataAdapter]] = [
        ExcelAdapter,
        # CsvAdapter,  <-- Futura expansión aquí
        # JsonAdapter,
    ]

    @classmethod
    def get_adapter(cls, file_obj: UploadedFile) -> BaseDataAdapter:
        """
        Analiza el archivo y devuelve el adaptador correcto inicializado.
        
        Args:
            file_obj (UploadedFile): El archivo subido por el usuario en Django.
            
        Returns:
            BaseDataAdapter: Una instancia lista para usar (ej. ExcelAdapter).
            
        Raises:
            ValueError: Si ningún driver registrado reconoce el formato del archivo.
        """
        filename = file_obj.name.lower() if file_obj.name else "desconocido"
        
        # 1. Iteración de Detección (Polimorfismo)
        for DriverClass in cls._REGISTERED_DRIVERS:
            # Instanciamos el driver pasando el archivo
            adapter = DriverClass(file_obj)
            
            # Preguntamos: "¿Eres capaz de leer este archivo?"
            if adapter.detect():
                logger.info(f"✅ Archivo '{filename}' aceptado por driver: {DriverClass.__name__}")
                return adapter

        # 2. Manejo de Error (Si llegamos aquí, nadie levantó la mano)
        logger.warning(f"⛔ Intento de subida fallido: Formato no soportado para '{filename}'")
        
        # Generamos dinámicamente la lista de formatos soportados para el usuario
        supported_formats = ", ".join(
            [d.__name__.replace('Adapter', '') for d in cls._REGISTERED_DRIVERS]
        )
        
        raise ValueError(
            f"El sistema no reconoce el formato del archivo '{filename}'. "
            f"Formatos soportados actualmente: [{supported_formats}]. "
            "Por favor, verifique la extensión y la integridad del archivo."
        )
