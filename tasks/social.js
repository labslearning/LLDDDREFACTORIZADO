/* ===================================================================
 * social.js - Cerebro del Frontend Social de Labs Learning
 * Maneja WebSockets, Reacciones AJAX y Lógica de UI
 * =================================================================== */

document.addEventListener('DOMContentLoaded', function() {
    initWebSocket();
});

// ===================================================================
// 1. SEGURIDAD: OBTENER CSRF TOKEN (Para peticiones POST AJAX)
// ===================================================================
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
const csrftoken = getCookie('csrftoken');

// ===================================================================
// 2. TIEMPO REAL: WEBSOCKET DE NOTIFICACIONES
// ===================================================================
function initWebSocket() {
    // Detectar protocolo (ws o wss para producción con SSL)
    const ws_scheme = window.location.protocol === "https:" ? "wss" : "ws";
    const ws_path = ws_scheme + '://' + window.location.host + '/ws/notifications/';
    
    console.log("Conectando a WS de notificaciones:", ws_path);
    
    const notificationSocket = new WebSocket(ws_path);

    notificationSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        
        if (data.type === 'notification') {
            // 1. Mostrar Toast/Alerta Visual
            mostrarNotificacionVisual(data);
            
            // 2. Actualizar Contador de la Campanita (Navbar)
            actualizarBadgeNotificaciones();
        }
    };

    notificationSocket.onclose = function(e) {
        console.warn('Chat socket cerrado inesperadamente. Reintentando en 5s...');
        setTimeout(initWebSocket, 5000); // Reconexión automática
    };
}

function mostrarNotificacionVisual(data) {
    // Usamos una alerta simple o un Toast de Bootstrap si existe en el DOM
    // Aquí creamos un elemento flotante simple
    const toastHTML = `
        <div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index: 1100">
            <div class="toast show align-items-center text-white bg-primary border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <strong>${data.titulo}</strong><br>
                        ${data.mensaje}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close" onclick="this.parentElement.parentElement.remove()"></button>
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', toastHTML);
    
    // Auto-eliminar después de 5 segundos
    setTimeout(() => {
        const toasts = document.querySelectorAll('.toast-container');
        if(toasts.length > 0) toasts[0].remove();
    }, 5000);
}

function actualizarBadgeNotificaciones() {
    const badge = document.getElementById('notification-badge');
    if (badge) {
        let count = parseInt(badge.innerText || 0);
        badge.innerText = count + 1;
        badge.style.display = 'inline-block'; // Asegurar que se vea
    }
}

// ===================================================================
// 3. INTERACTIVIDAD SOCIAL (API AJAX)
// ===================================================================

/**
 * Dar Like/Love a un Post o Comentario
 * @param {number} id - ID del objeto
 * @param {string} tipo - 'post' o 'comment'
 * @param {HTMLElement} btn - El botón presionado
 */
async function toggleReaction(id, tipo, btn) {
    try {
        const response = await fetch('/api/social/reaction/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({
                'id': id,
                'type': tipo,
                'reaction': 'LIKE' // Por defecto LIKE, se puede expandir a LOVE
            })
        });

        const data = await response.json();

        if (data.success) {
            // Actualizar contador visualmente
            const counterSpan = document.getElementById(`reaction-count-${tipo}-${id}`);
            if (counterSpan) {
                counterSpan.innerText = data.total;
            }

            // Cambiar estilo del botón (Activo/Inactivo)
            if (data.action === 'added') {
                btn.classList.add('text-primary', 'fw-bold'); // Estilo activo
                btn.classList.remove('text-muted');
            } else {
                btn.classList.remove('text-primary', 'fw-bold'); // Estilo inactivo
                btn.classList.add('text-muted');
            }
        } else {
            console.error('Error en reacción:', data.error);
        }
    } catch (error) {
        console.error('Error de red:', error);
    }
}

/**
 * Seguir o Dejar de Seguir a un usuario
 * @param {number} userId - ID del usuario destino
 * @param {HTMLElement} btn - El botón presionado
 */
async function toggleFollow(userId, btn) {
    try {
        const response = await fetch('/api/social/follow/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({ 'user_id': userId })
        });

        const data = await response.json();

        if (data.success) {
            // Cambiar texto y estilo del botón
            if (data.action === 'followed') {
                btn.innerHTML = '<i class="fas fa-check me-2"></i>Siguiendo';
                btn.classList.replace('btn-primary', 'btn-outline-secondary');
            } else {
                btn.innerHTML = '<i class="fas fa-user-plus me-2"></i>Seguir';
                btn.classList.replace('btn-outline-secondary', 'btn-primary');
            }
            
            // Actualizar contador de seguidores si existe en la página
            const followerCount = document.getElementById('profile-followers-count');
            if (followerCount) {
                followerCount.innerText = data.followers_count;
            }
        }
    } catch (error) {
        console.error('Error al seguir usuario:', error);
    }
}

/**
 * Moderación: Eliminar contenido ofensivo (Solo Staff/Profesores)
 */
async function moderarContenido(id, tipo) {
    if (!confirm("¿Estás seguro de eliminar este contenido? Esta acción quedará registrada en auditoría.")) {
        return;
    }

    const motivo = prompt("Motivo de la eliminación (Opcional):", "Contenido inapropiado");

    try {
        const response = await fetch('/api/social/moderate/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({
                'id': id,
                'type': tipo,
                'motivo': motivo
            })
        });

        const data = await response.json();

        if (data.success) {
            alert("Contenido eliminado correctamente.");
            // Eliminar elemento del DOM
            const elemento = document.getElementById(`${tipo}-${id}`);
            if (elemento) {
                elemento.remove();
            } else {
                location.reload(); // Recargar si no se encuentra el ID fácil
            }
        } else {
            alert("Error al moderar: " + data.error);
        }
    } catch (error) {
        console.error('Error de moderación:', error);
    }
}
