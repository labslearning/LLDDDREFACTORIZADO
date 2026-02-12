from django.core.management.base import BaseCommand
from django.conf import settings
from twilio.rest import Client
import time  # Importante para la espera
import sys

# Importamos la función de limpieza para probar que la lógica del sistema funciona
try:
    from tasks.utils import formatear_celular_colombia
except ImportError:
    # Fallback por si acaso no has guardado utils.py aún
    def formatear_celular_colombia(numero):
        return f"+57{numero}" if len(str(numero)) == 10 else numero

class Command(BaseCommand):
    help = 'Envía un SMS de diagnóstico verificando formato, conexión y ENTREGA REAL'

    def add_arguments(self, parser):
        parser.add_argument('numero_destino', type=str, help='Número destino (ej: 3132533008 o +573...)')

    def handle(self, *args, **options):
        raw_numero = options['numero_destino']

        # --- CABECERA DE DIAGNÓSTICO ---
        self.stdout.write(self.style.SUCCESS("\n" + "═"*60))
        self.stdout.write(self.style.SUCCESS("🛡️  NEMESIS SOFTWARE - DIAGNÓSTICO PROFUNDO SMS"))
        self.stdout.write(self.style.SUCCESS("═"*60))

        # 1. PRUEBA DE FORMATEO
        self.stdout.write(f"📥 Entrada cruda: {raw_numero}")
        
        numero_final = formatear_celular_colombia(raw_numero)
        
        if not numero_final:
            self.stdout.write(self.style.ERROR("❌ Error de Validación: El número no parece un celular colombiano válido."))
            self.stdout.write("   Asegúrate de que tenga 10 dígitos (ej: 3001234567).")
            return

        self.stdout.write(self.style.SUCCESS(f"✅ Formato E.164 aplicado: {numero_final}"))

        # 2. INPUT DEL MENSAJE
        try:
            mensaje_interactivo = input("\n📝 Escribe el mensaje de prueba [Enter para cancelar]: ")
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\n⛔ Operación cancelada."))
            return

        if not mensaje_interactivo.strip():
            self.stdout.write(self.style.WARNING("⚠️  No escribiste nada. Cancelando."))
            return

        # 3. CONEXIÓN Y ENVÍO
        try:
            self.stdout.write(f"\n📡 Enviando petición a Twilio...")
            
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            message = client.messages.create(
                body=mensaje_interactivo,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=numero_final
            )

            self.stdout.write(self.style.SUCCESS(f'✅ Petición aceptada por la API'))
            self.stdout.write(f"🆔 SID: {message.sid}")
            
            # 4. RASTREO DE ENTREGA (LA PARTE CLAVE)
            self.stdout.write("\n🕵️  Rastreando estado real de entrega (esperando 10s)...")
            
            estado_final = message.status
            error_code = None
            error_msg = None

            # Bucle de 5 intentos (esperar 2 segundos cada vez)
            for i in range(5):
                time.sleep(2) # Espera 2 segundos
                
                # Consultar estado actualizado
                updated_msg = client.messages(message.sid).fetch()
                estado_final = updated_msg.status
                
                self.stdout.write(f"   ⏱️  { (i+1)*2 }s: Estado actual -> {estado_final.upper()}")
                
                # Si llega a un estado terminal, paramos
                if estado_final in ['delivered', 'undelivered', 'failed']:
                    error_code = updated_msg.error_code
                    error_msg = updated_msg.error_message
                    break
            
            self.stdout.write("-" * 30)

            # 5. DIAGNÓSTICO FINAL
            if estado_final == 'delivered':
                 self.stdout.write(self.style.SUCCESS("✅ CONFIRMADO: El mensaje llegó al celular."))
                 precio = updated_msg.price if updated_msg.price else "N/A"
                 self.stdout.write(f"💰 Costo final: {precio} {updated_msg.price_unit}")

            elif estado_final == 'undelivered':
                 self.stdout.write(self.style.ERROR(f"❌ ERROR: El operador rechazó el mensaje."))
                 self.stdout.write(f"🛑 Código Twilio: {error_code}")
                 self.stdout.write(f"ℹ️  Razón: {error_msg}")
                 
                 if error_code == 30008:
                     self.stdout.write(self.style.WARNING("💡 CONSEJO: 'Unknown error'. Suele ser filtro anti-spam del operador. Intenta cambiar el texto."))

            elif estado_final == 'failed':
                 self.stdout.write(self.style.ERROR("❌ FALLO CRÍTICO: No salió de Twilio."))
                 self.stdout.write(f"🛑 Código: {error_code} - {error_msg}")
                 if error_code == 21608:
                     self.stdout.write(self.style.WARNING("💡 CAUSA: Cuenta en modo TRIAL. Solo puedes enviar a números verificados."))

            else:
                 self.stdout.write(self.style.WARNING("⚠️  Estado incierto: Sigue en proceso o el operador es lento."))
                 self.stdout.write("   Revisa el log de Twilio en la web más tarde.")

            self.stdout.write("\n" + "═"*60)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ ERROR DE EXCEPCIÓN: {str(e)}'))
            # Pistas rápidas
            error_str = str(e).lower()
            if "unverified" in error_str:
                self.stdout.write("💡 Es por la cuenta TRIAL. Verifica el número en Twilio Console.")
            elif "geo permission" in error_str:
                self.stdout.write("💡 Habilita COLOMBIA en Twilio Messaging Geo Permissions.")