# ===================================================================
# tasks/utils.py (SENTINEL 3.0: CORRECCIÓN DE FALSOS POSITIVOS Y LÓGICA ROBUSTA)
# ===================================================================
#desde aqui 
import threading
import logging
from django.conf import settings
from django.utils import timezone
from twilio.rest import Client

#Hasta aqui importaciones de sms 
import re
import secrets
import string
import unicodedata
import bleach
import textdistance
from unidecode import unidecode
from django.contrib.auth.models import User
from .models import Curso, Notificacion, Acudiente 
from typing import Optional
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# ===================================================================
# 1. UTILIDADES DE USUARIO Y NEGOCIO
# ===================================================================

def _slugify_simple(text: str) -> str:
    try:
        # Usa unidecode para manejar acentos antes de la normalización ASCII
        text = unidecode(text) 
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    except (TypeError, AttributeError):
        return ""
    return re.sub(r'[^a-z0-9]+', '', text.lower())

def generar_username_unico(nombre: str, apellido: str) -> str:
    base_username = f"{_slugify_simple(nombre[:1])}{_slugify_simple(apellido)}"
    if not base_username: base_username = "usuario"
    if not User.objects.filter(username=base_username).exists(): return base_username
    candidatos = User.objects.filter(username__regex=rf'^{re.escape(base_username)}\d*$').values_list('username', flat=True)
    sufijos = [int(u[len(base_username):]) for u in candidatos if u != base_username and u[len(base_username):].isdigit()]
    siguiente_sufijo = (max(sufijos) + 1) if sufijos else 2
    return f"{base_username}{siguiente_sufijo}"

def generar_contrasena_temporal(longitud: int = 12) -> str:
    alfabeto = string.ascii_letters + string.digits + "!@#$%^&*?"
    return ''.join(secrets.choice(alfabeto) for _ in range(longitud))

def asignar_curso_por_grado(grado: str, seccion: Optional[str] = None, anio_escolar: Optional[str] = None) -> Curso:
    qs = Curso.objects.filter(grado=grado, activo=True)
    if anio_escolar: qs = qs.filter(anio_escolar=anio_escolar)
    if seccion: qs = qs.filter(seccion__iexact=seccion)
    for curso in qs.order_by('seccion', 'nombre'):
        if not curso.esta_completo(): return curso
    fallback_qs = Curso.objects.filter(grado=grado, activo=True)
    if anio_escolar: fallback_qs = fallback_qs.filter(anio_escolar=anio_escolar)
    for curso in fallback_qs.order_by('seccion', 'nombre'):
         if not curso.esta_completo(): return curso
    raise ValueError(f"No hay cursos con cupo disponible para el grado '{grado}'.")

# ===================================================================
# 2. NOTIFICACIONES (INTACTAS)
# ===================================================================

def crear_notificacion(usuario_destino, titulo, mensaje, tipo, link=None):
    try:
        Notificacion.objects.create(usuario=usuario_destino, titulo=titulo, mensaje=mensaje, tipo=tipo, link_destino=link)
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{usuario_destino.id}",
                {'type': 'send_notification', 'titulo': titulo, 'mensaje': mensaje, 'link': link or '#', 'tipo_alerta': 'info'}
            )
    except Exception as e:
        print(f"Error log (Notificación): {e}")

def notificar_acudientes(estudiante, titulo, mensaje, tipo, link=None):
    vinculos = Acudiente.objects.filter(estudiante=estudiante)
    if not vinculos.exists(): return
    for vinculo in vinculos:
        mensaje_personalizado = f"Alumno {estudiante.get_full_name()}: {mensaje}"
        crear_notificacion(vinculo.acudiente, titulo, mensaje_personalizado, tipo, link)

# ===================================================================
# 3. SANITIZACIÓN HTML (INTACTA)
# ===================================================================

def _link_callback(attrs, new=False):
    attrs[(None, 'target')] = '_blank'
    attrs[(None, 'rel')] = 'noopener noreferrer'
    return attrs

def sanitizar_markdown(texto: str) -> str:
    if not texto: return ""
    tags_permitidos = ['b', 'i', 'u', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li', 'code', 'pre', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div']
    atributos_permitidos = {'a': ['href', 'title', 'target'], 'span': ['class'], '*': ['style']}
    estilos_permitidos = ['color', 'font-weight', 'text-align', 'text-decoration']
    cleaned_text = bleach.clean(texto, tags=tags_permitidos, attributes=atributos_permitidos, styles=estilos_permitidos, strip=True)
    linker = bleach.linkifier.Linker(callbacks=[_link_callback])
    return linker.linkify(cleaned_text)

# ===================================================================
# 4. EL CENTINELA 3.0: SEGURIDAD INTELIGENTE (CORREGIDO) 🛡️
# ===================================================================

# Lista curada de palabras ofensivas (la misma de tu versión anterior, pero la lógica será más estricta)
BAD_WORDS_STRICT = [
    # --- INSULTOS Y RAÍCES PRINCIPALES ---
    'estupido', 'estupida', 'idiota', 'imbecil', 'pendejo', 'pendeja', 'tarado', 'baboso', 
    'inutil', 'basura', 'escoria', 'maldito', 'maldita', 'malparido', 'gonorrea', 'pirobo', 
    'perra', 'zorra', 'puta', 'puto', 'guarro', 'cerdo', 'asqueroso', 'retrasado', 'mongolico',
    'autismo', 'sidoso', 'canceroso', 'mierda', 'cagar', 'cabron', 'maricon', 'marica', 'joder',
    
    # --- CONTENIDO SEXUAL ---
    'follar', 'coger', 'mamada', 'chupalo', 'pene', 'verga', 'picha', 'polla', 
    'vagina', 'concha', 'panocha', 'clitoris', 'vulva', 'tetas', 'senos', 'anal', 
    'semen', 'corrida', 'orgasmo', 'porno', 'pornografia', 'hentai', 'nude', 
    'desnudo', 'desnuda', 'excitado', 'caliente', 'penetrar', 'masturbarse', 'paja',
    'condon', 'virginidad', 'prostituta', 'prepago', 'sexo',
    
    # --- ACOSO / ODIO ---
    'travesti', 'negro de mierda', 'sudaca', 'indio', 'nazi', 'hitler', 
    'gordo', 'gorda', 'ballena', 'anorexico', 'bulimico', 'suicidate', 'matate', 
    'muerete', 'cortate', 'ahorcate', 'plomo', 'disparar', 'violar', 'abusador', 
    'marihuana', 'cocaina', 'heroina', 'drogas'
]

class Sentinel:
    @staticmethod
    def normalize_word(word: str) -> str:
        """
        Limpia una palabra individual manteniendo su esencia, maneja acentos y leetspeak.
        """
        # 1. Quitar acentos y a minúsculas usando unidecode (CRUCIAL para tildes y ñ)
        word = unidecode(word).lower()
        
        # 2. Mapa de Leetspeak simple
        leetspeak_map = {'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a', '$': 's', '!': 'i'}
        for symbol, letter in leetspeak_map.items():
            word = word.replace(symbol, letter)
            
        # 3. Dejar solo letras (elimina puntuación y símbolos pegados, pero no quita espacios)
        return re.sub(r'[^a-z]+', '', word)

    @staticmethod
    def is_toxic(text: str) -> tuple[bool, Optional[str]]:
        """
        Analiza el texto PALABRA POR PALABRA con lógica relajada para evitar falsos positivos.
        """
        if not text: 
            return False, None
        
        # 1. Dividir el texto en palabras reales (usamos regex para encontrar bloques de caracteres)
        words = re.findall(r'\b\S+\b', text) 
        
        for word in words:
            clean_word = Sentinel.normalize_word(word)
            
            # Si la palabra limpia es muy corta (menos de 3 letras), la ignoramos.
            if len(clean_word) < 3:
                continue

            for bad_word in BAD_WORDS_STRICT:
                
                # 2. Coincidencia Exacta (Máxima prioridad)
                if clean_word == bad_word:
                    return True, f"Palabra prohibida: {bad_word}"
                
                # 3. Detección de palabras compuestas (Ej: 'come+mierda')
                # Buscamos la palabra mala *dentro* de la palabra limpia
                if bad_word in clean_word:
                    # Criterio de longitud más estricto: la palabra mala debe ser de al menos 4 caracteres
                    # (Esto evita falsos positivos como 'aut' en 'autoridad' o 'put' en 'computador')
                    if len(bad_word) >= 4: 
                         return True, f"Palabra compuesta ofensiva detectada: {bad_word}"

                # 4. Lógica Difusa (Fuzzy) para errores ortográficos o evasión leves
                if abs(len(clean_word) - len(bad_word)) <= 2:
                    # Usamos un umbral MUY ALTO (95%)
                    similarity = textdistance.jaro_winkler.normalized_similarity(clean_word, bad_word)
                    if similarity > 0.95:  
                        return True, f"Palabra sospechosa similar a: {bad_word}"
        
        return False, None

# Helper para compatibilidad
def security_scan(text: str) -> bool:
    is_unsafe, reason = Sentinel.is_toxic(text)
    return is_unsafe

def validar_lenguaje_apropiado(texto: str) -> bool:
    is_unsafe, _ = Sentinel.is_toxic(texto)
    return not is_unsafe


#Implementacion de SMS 

# ===================================================================
# 5. INTEGRACIÓN SMS (THREADING + ANTI-SPAM) 📱
# ===================================================================

logger = logging.getLogger(__name__)

class SMSThread(threading.Thread):
    def __init__(self, numero, mensaje):
        self.numero = numero
        self.mensaje = mensaje
        threading.Thread.__init__(self)

    def run(self):
        try:
            if not getattr(settings, 'TWILIO_ACCOUNT_SID', None):
                return

            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=self.mensaje,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=self.numero
            )
            logger.info(f"✅ SMS enviado a {self.numero}")
        except Exception as e:
            logger.error(f"❌ Error enviando SMS: {e}")

def enviar_sms_twilio(numero_destino, mensaje_texto):
    """
    Formatea el número y lanza el envío en segundo plano.
    """
    if not numero_destino:
        return

    # Limpieza y formato Colombia (+57)
    num_limpio = ''.join(filter(str.isdigit, str(numero_destino)))

    if len(num_limpio) == 10 and num_limpio.startswith('3'):
        numero_final = f"+57{num_limpio}"
    elif not str(numero_destino).startswith('+'):
        numero_final = f"+{num_limpio}"
    else:
        numero_final = numero_destino

    # Disparar hilo (Fire and Forget)
    SMSThread(numero_final, mensaje_texto).start()

def verificar_y_alertar_acudiente(usuario):
    """
    Revisa si hay mensajes acumulados y envía SMS respetando COOLDOWN de 24h.
    """
    from .models import MensajeInterno, Notificacion  # Import local para evitar ciclos

    try:
        if not hasattr(usuario, 'perfil'):
            return

        perfil = usuario.perfil
        if not perfil.telefono_sms or not perfil.recibir_sms:
            return

        # === REGLA DE ORO: PROTECCIÓN DE BOLSILLO ===
        if perfil.ultimo_sms_enviado:
            horas_pasadas = (timezone.now() - perfil.ultimo_sms_enviado).total_seconds() / 3600
            if horas_pasadas < 24:
                return  # ⛔ Stop: Ya se le avisó hoy.

        # Verificar acumulados
        UMBRAL = 2
        mensajes = MensajeInterno.objects.filter(destinatario=usuario, leido=False).count()
        notificaciones = Notificacion.objects.filter(usuario=usuario, leida=False).count()

        texto_sms = ""

        if mensajes > UMBRAL:
            texto_sms = f"LearningLabs: Hola {usuario.first_name}, tienes {mensajes} mensajes sin leer. Ingresa para revisarlos."
        elif notificaciones > UMBRAL:
            texto_sms = f"LearningLabs: Hola {usuario.first_name}, tienes {notificaciones} novedades pendientes."

        if texto_sms:
            enviar_sms_twilio(perfil.telefono_sms, texto_sms)
            # Marcar que ya se envió hoy
            perfil.ultimo_sms_enviado = timezone.now()
            perfil.save(update_fields=['ultimo_sms_enviado'])

    except Exception as e:
        logger.error(f"Error en verificación SMS: {e}")