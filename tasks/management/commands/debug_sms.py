from django.core.management.base import BaseCommand
from django.conf import settings
from twilio.rest import Client
import time
import sys

class Command(BaseCommand):
    help = 'Envía un SMS y realiza un rastreo forense del estado de entrega'

    def add_arguments(self, parser):
        parser.add_argument('numero_destino', type=str, help='Número destino (+57...)')

    def handle(self, *args, **options):
        numero = options['numero_destino']
        
        # Limpieza básica para asegurar formato
        if len(numero) == 10 and not numero.startswith('+'):
            numero = f"+57{numero}"

        self.stdout.write(self.style.SUCCESS(f"\n🕵️ INICIANDO RASTREO FORENSE A: {numero}"))
        self.stdout.write("="*60)

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        # 1. ENVIAR
        try:
            msg = client.messages.create(
                body="LearningLabs: Tu codigo de verificacion es 8492. No respondas a este mensaje.",
                from_=settings.TWILIO_PHONE_NUMBER,
                to=numero
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ FALLO INMEDIATO: {e}"))
            return

        self.stdout.write(f"✅ Enviado a la red. SID: {msg.sid}")
        self.stdout.write("⏳ Esperando respuesta del Operador (Claro/Tigo/Movistar)...")

        # 2. BUCLE DE RASTREO (30 Segundos)
        estado_anterior = ""
        for i in range(15):  # 15 intentos de 2 segundos = 30 seg
            time.sleep(2)
            
            # Consultar a Twilio qué dice el operador
            actualizado = client.messages(msg.sid).fetch()
            estado = actualizado.status
            
            # Solo imprimir si cambió el estado
            if estado != estado_anterior:
                self.stdout.write(f"   ⏱️ T+{i*2}s: Estado -> {estado.upper()}")
                estado_anterior = estado

            # Si falló o se entregó, analizamos y salimos
            if estado in ['delivered', 'undelivered', 'failed']:
                self.stdout.write("="*60)
                
                if estado == 'delivered':
                    self.stdout.write(self.style.SUCCESS("🎉 EL OPERADOR CONFIRMÓ ENTREGA (Celular sonando...)"))
                
                else:
                    self.stdout.write(self.style.ERROR(f"💀 EL OPERADOR RECHAZÓ EL MENSAJE"))
                    self.stdout.write(f"🔴 Error Code: {actualizado.error_code}")
                    self.stdout.write(f"🔴 Error Msg:  {actualizado.error_message}")
                    
                    # Diagnóstico de códigos comunes en Colombia
                    code = actualizado.error_code
                    if code == 30008:
                        self.stdout.write(self.style.WARNING("\n💡 DIAGNÓSTICO: 'Unknown Error'"))
                        self.stdout.write("   Esto significa que el operador (Claro/Tigo) lo filtró como SPAM.")
                        self.stdout.write("   Solución: Intenta cambiar el texto del mensaje, hazlo más formal.")
                    elif code == 30006:
                        self.stdout.write(self.style.WARNING("\n💡 DIAGNÓSTICO: 'Landline'"))
                        self.stdout.write("   Estás intentando enviar SMS a un teléfono fijo.")
                    elif code == 30003:
                        self.stdout.write(self.style.WARNING("\n💡 DIAGNÓSTICO: 'Unreachable'"))
                        self.stdout.write("   El celular está apagado, sin señal o fuera de servicio.")
                return

        self.stdout.write(self.style.WARNING("\n⚠️ SE ACABÓ EL TIEMPO: El mensaje sigue en 'queued' o 'sent'."))
        self.stdout.write("   Esto suele pasar cuando la red está congestionada o el operador está analizando el contenido.")
