from django.apps import AppConfig

class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tasks'

    #def ready(self):
        # Importar las señales cuando la app esté lista
        #import tasks.signals
    