import os
import math
import random
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageDraw
import firebase_admin
from firebase_admin import credentials, firestore

# --- INICIALIZAR FIREBASE ---
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Conexión exitosa a Firebase Firestore")
except Exception as e:
    print(f"Error al conectar con Firebase: {e}")


# =====================================================================
#         PALETA (turquesa -> azul petróleo -> naranja)
# =====================================================================
TEAL_CLARO = (20, 165, 155)        
TEAL_MEDIO = (10, 122, 147)        
TEAL_PROFUNDO = (9, 111, 134)      
NARANJA = (232, 132, 26)           
HERRUMBRE = (200, 90, 44)          

COLOR_TARJETA = "#26C6DA"            
COLOR_TARJETA_HOVER = "#66CCCC"      
COLOR_BORDE_TARJETA = "#0A5F73"      
COLOR_BORDE_HOVER = "#F59A33"        
COLOR_TEXTO_TITULO = "#0A5F73"       
COLOR_TEXTO_SECUNDARIO = "#0A5F73"   
COLOR_TEXTO_CLARO = "#FFFFFF"        
COLOR_CREMA = "#FFE0B0"              

COLOR_BOTON = "#E8821A"              
COLOR_BOTON_HOVER = "#66CCCC"        
COLOR_BOTON_PRESS = "#66CCCC"

FUENTE_FAMILIA = "Century Gothic"


def set_status(texto, color=COLOR_TEXTO_CLARO):
    try:
        lienzo.itemconfig(item_status, text=texto, fill=color)
    except:
        pass


def abrir_app_principal(usuario, uid, nuevo=False):
    """Cierra el login y lanza la app de aprendizaje (le pasa usuario, id y si es cuenta nueva)"""
    ventana.destroy()
    try:
        carpeta = os.path.dirname(os.path.abspath(__file__))
        args = [sys.executable, os.path.join(carpeta, "app_senas_flotantes.py"), usuario, uid]
        if nuevo:
            args.append("nuevo")
        subprocess.Popen(args)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo abrir la aplicación principal:\n{e}")


def procesar_login():
    usuario = entry_usuario.get().strip()
    password = entry_password.get().strip()
    
    if not usuario or not password:
        set_status("⚠️ Por favor completa todos los campos de acceso", COLOR_CREMA)
        return

    set_status(f"Verificando credenciales para {usuario}...", COLOR_CREMA)

    def tarea_firebase():
        try:
            # Consultamos en la colección 'usuarios' donde el campo 'nombre' sea igual al ingresado
            query = db.collection("usuarios").where("nombre", "==", usuario).limit(1).get()
            
            documentos = list(query)
            if len(documentos) > 0:
                datos_usuario = documentos[0].to_dict()
                # Validamos con el campo 'contraseña' de tu estructura de Firebase
                if datos_usuario.get("contraseña") == password:
                    set_status(f"¡Bienvenido, {usuario}!", COLOR_CREMA)
                    ventana.after(500, lambda: abrir_app_principal(usuario, documentos[0].id))
                else:
                    ventana.after(0, lambda: set_status("⚠️ Contraseña incorrecta", COLOR_CREMA))
            else:
                ventana.after(0, lambda: set_status("⚠️ El usuario no existe en la base de datos", COLOR_CREMA))
        except Exception as e:
            ventana.after(0, lambda: set_status("⚠️ Error de conexión con Firebase", COLOR_CREMA))
            print(e)

    threading.Thread(target=tarea_firebase, daemon=True).start()


def procesar_registro():
    usuario = entry_reg_usuario.get().strip()
    password = entry_reg_password.get().strip()
    confirmar = entry_reg_confirmar.get().strip()
    correo = entry_reg_correo.get().strip()
    
    if not usuario or not password or not confirmar:
        set_status("⚠️ Por favor completa todos los campos de registro", COLOR_CREMA)
        return
        
    if password != confirmar:
        set_status("⚠️ Las contraseñas no coinciden", COLOR_CREMA)
        return

    set_status(f"Registrando a {usuario}...", COLOR_CREMA)

    def tarea_registro():
        try:
            # Verificar si el nombre de usuario ya existe
            query = db.collection("usuarios").where("nombre", "==", usuario).limit(1).get()
            if len(list(query)) > 0:
                ventana.after(0, lambda: set_status("⚠️ Este nombre de usuario ya está ocupado", COLOR_CREMA))
                return

            # Guardar con los campos exactos de tu Firebase
            _, ref_nuevo = db.collection("usuarios").add({
                "nombre": usuario,
                "contraseña": password,
                "correo": correo if correo else f"{usuario}@gmail.com",
                "fechaRegistro": firestore.SERVER_TIMESTAMP
            })

            # Crear su registro de progreso (mismo id que el usuario)
            db.collection("progreso_usuarios").document(ref_nuevo.id).set({"abecedario_nivel_1": 0})

            # Registro completado -> directo al menú de bienvenida
            ventana.after(0, lambda: abrir_app_principal(usuario, ref_nuevo.id, True))
        except Exception as e:
            ventana.after(0, lambda: set_status("⚠️ Error al registrar en Firebase", COLOR_CREMA))
            print(e)

    threading.Thread(target=tarea_registro, daemon=True).start()


def cambiar_vista(vista):
    if vista == "registro":
        lienzo.itemconfig(ventana_tarjeta_login, state="hidden")
        lienzo.itemconfig(ventana_inputs_login, state="hidden")
        lienzo.itemconfig(ventana_btn_ingresar, state="hidden")
        lienzo.itemconfig(ventana_link_reg, state="hidden")
        
        lienzo.itemconfig(ventana_tarjeta_reg, state="normal")
        lienzo.itemconfig(ventana_inputs_reg, state="normal")
        lienzo.itemconfig(ventana_btn_reg, state="normal")
        lienzo.itemconfig(ventana_link_login, state="normal")
        set_status("Estado: Completa tus datos para registrarte", COLOR_TEXTO_CLARO)
    else:
        lienzo.itemconfig(ventana_tarjeta_reg, state="hidden")
        lienzo.itemconfig(ventana_inputs_reg, state="hidden")
        lienzo.itemconfig(ventana_btn_reg, state="hidden")
        lienzo.itemconfig(ventana_link_login, state="hidden")
        
        lienzo.itemconfig(ventana_tarjeta_login, state="normal")
        lienzo.itemconfig(ventana_inputs_login, state="normal")
        lienzo.itemconfig(ventana_btn_ingresar, state="normal")
        lienzo.itemconfig(ventana_link_reg, state="normal")
        set_status("Estado: Introduce tus credenciales", COLOR_TEXTO_CLARO)


# --- Configuración principal de la ventana ---
ventana = tk.Tk()
ventana.title("Lenguaje de Señas - Acceso y Registro")

try:
    ventana.state('zoomed')
except Exception:
    ventana.attributes('-fullscreen', True)

ventana.bind("<Escape>", lambda event: ventana.attributes('-fullscreen', False))
ventana.configure(bg="#0A7A93")

lienzo = tk.Canvas(ventana, bg="#0A7A93", highlightthickness=0, bd=0)
lienzo.pack(fill="both", expand=True)


# --- Fondo degradado ---
def mezcla(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def generar_degradado(ancho, alto):
    gw, gh = 96, 60
    pequena = Image.new("RGB", (gw, gh))
    px = pequena.load()
    for j in range(gh):
        v = j / (gh - 1)
        for i in range(gw):
            u = i / (gw - 1)
            t = u * 0.35 + v * 0.65
            if t < 0.5:
                base = mezcla(TEAL_CLARO, TEAL_MEDIO, t / 0.5)
            else:
                base = mezcla(TEAL_MEDIO, TEAL_PROFUNDO, (t - 0.5) / 0.5)
            dx = (1 - u) / 0.75
            dy = (1 - v) / 0.60
            w = max(0.0, 1.0 - math.hypot(dx, dy)) ** 1.3
            naranja = mezcla(HERRUMBRE, NARANJA, w * 1.4)
            px[i, j] = mezcla(base, naranja, w * 1.25)
    return pequena.resize((max(1, ancho), max(1, alto)), Image.Resampling.BICUBIC)


fondo_tk = None
item_fondo = lienzo.create_image(0, 0, anchor="nw", tags="bg")

item_titulo = lienzo.create_text(
    0, 0, text="Lenguaje de Señas - App", fill=COLOR_TEXTO_CLARO,
    font=(FUENTE_FAMILIA, 28, "bold"), tags="texto"
)
item_subtitulo = lienzo.create_text(
    0, 0, text="Aprende, practica y conéctate con la seña", fill=COLOR_CREMA,
    font=(FUENTE_FAMILIA, 12, "bold"), tags="texto"
)
item_status = lienzo.create_text(
    0, 0, text="Estado: Conectado a Firebase Firestore",
    fill=COLOR_TEXTO_CLARO, font=(FUENTE_FAMILIA, 10, "bold"), tags="texto"
)


def crear_icono(tipo, tam=22, color=(255, 255, 255, 255)):
    s = tam * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if tipo == "user":
        cx, cy = s * 0.5, s * 0.38
        r = s * 0.22
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
        d.rounded_rectangle((s * 0.2, s * 0.68, s * 0.8, s * 0.95), radius=s * 0.15, fill=color)
    elif tipo == "add":
        d.rounded_rectangle((s * 0.25, s * 0.25, s * 0.75, s * 0.85), radius=s * 0.1, fill=color)
        d.rectangle((s * 0.45, s * 0.4, s * 0.55, s * 0.7), fill=(10, 122, 147, 255))
        d.rectangle((s * 0.35, s * 0.5, s * 0.65, s * 0.6), fill=(10, 122, 147, 255))
    return img.resize((tam, tam), Image.Resampling.LANCZOS)


class BotonRedondeado(tk.Canvas):
    def __init__(self, parent, texto, comando, icono=None, ancho=220, alto=44,
                 color=COLOR_BOTON, color_hover=COLOR_BOTON_HOVER, color_press=COLOR_BOTON_PRESS,
                 color_borde="#FFC27A", color_sombra="#E6D5BF", color_brillo="#FFD9A3",
                 bg_padre=COLOR_TARJETA):
        super().__init__(parent, width=ancho, height=alto, bg=bg_padre,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.ancho, self.alto = ancho, alto
        self.comando = comando
        self.color, self.color_hover, self.color_press = color, color_hover, color_press
        self.icono_tk = ImageTk.PhotoImage(icono) if icono is not None else None

        fuente = tkfont.Font(family=FUENTE_FAMILIA, size=10, weight="bold")
        ancho_texto = fuente.measure(texto)
        ancho_icono = (self.icono_tk.width() + 10) if self.icono_tk else 0
        x_inicio = (ancho - (ancho_icono + ancho_texto)) / 2

        self._rect(2, 4, ancho - 2, alto - 1, 18, fill=color_sombra, outline="")
        self.cuerpo = self._rect(2, 2, ancho - 2, alto - 4, 18, fill=color, outline=color_borde, width=1)
        self.create_line(22, 5, ancho - 22, 5, fill=color_brillo, width=1)

        if self.icono_tk:
            self.create_image(x_inicio, (alto - 2) / 2, image=self.icono_tk, anchor="w")
        self.create_text(x_inicio + ancho_icono, (alto - 2) / 2, text=texto, anchor="w",
                         fill="white", font=fuente)

        self.bind("<Enter>", lambda e: self.itemconfig(self.cuerpo, fill=self.color_hover))
        self.bind("<Leave>", lambda e: self.itemconfig(self.cuerpo, fill=self.color))
        self.bind("<ButtonPress-1>", lambda e: self.itemconfig(self.cuerpo, fill=self.color_press))
        self.bind("<ButtonRelease-1>", self._soltar)

    def _rect(self, x1, y1, x2, y2, r, **kw):
        puntos = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
                  x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(puntos, smooth=True, **kw)

    def _soltar(self, e):
        dentro = 0 <= e.x <= self.ancho and 0 <= e.y <= self.alto
        self.itemconfig(self.cuerpo, fill=self.color_hover if dentro else self.color)
        if dentro and self.comando:
            self.comando()


# =====================================================================
#   TARJETAS CANVAS (LOGIN Y REGISTRO)
# =====================================================================
ANCHO_TARJETA = 360
ALTO_TARJETA = 440

class TarjetaBaseCanvas(tk.Canvas):
    def __init__(self, parent, titulo, ancho=ANCHO_TARJETA, alto=ALTO_TARJETA):
        super().__init__(parent, width=ancho, height=alto, bg="#0A7A93", highlightthickness=0, bd=0)
        self.ancho = ancho
        self.alto = alto
        self.titulo_texto = titulo
        self.bg_actual = COLOR_TARJETA
        self.borde_actual = COLOR_BORDE_TARJETA
        self.dibujar()

    def dibujar(self):
        self.delete("all")
        radio = 30  
        x1, y1, x2, y2 = 2, 2, self.ancho - 2, self.alto - 2
        puntos = [
            x1 + radio, y1,  x2 - radio, y1,  
            x2, y1,  x2, y1 + radio,  
            x2, y2 - radio,  x2, y2,  
            x2 - radio, y2,  x1 + radio, y2,  
            x1, y2,  x1, y2 - radio,  
            x1, y1 + radio,  x1, y1
        ]
        self.create_polygon(puntos, smooth=True, fill=self.bg_actual, outline=self.borde_actual, width=2)
        self.create_text(self.ancho / 2, 25, text=self.titulo_texto, font=(FUENTE_FAMILIA, 16, "bold"), fill=COLOR_TEXTO_TITULO, anchor="n")


# --- Tarjeta de Login ---
tarjeta_login = TarjetaBaseCanvas(lienzo, "Iniciar Sesión")
ventana_tarjeta_login = lienzo.create_window(0, 0, window=tarjeta_login, anchor="center")

frame_login = tk.Frame(lienzo, bg=COLOR_TARJETA, highlightthickness=0)
estilo_entry = {"font": (FUENTE_FAMILIA, 10), "bg": "#FFFFFF", "fg": "#0A5F73", "bd": 2, "relief": "flat"}

tk.Label(frame_login, text="Usuario", font=(FUENTE_FAMILIA, 9, "bold"), fg=COLOR_TEXTO_SECUNDARIO, bg=COLOR_TARJETA).pack(anchor="nw", pady=(0, 2))
entry_usuario = tk.Entry(frame_login, **estilo_entry)
entry_usuario.pack(fill="x", pady=(0, 10), ipady=3, ipadx=5)

tk.Label(frame_login, text="Contraseña", font=(FUENTE_FAMILIA, 9, "bold"), fg=COLOR_TEXTO_SECUNDARIO, bg=COLOR_TARJETA).pack(anchor="nw", pady=(0, 2))
entry_password = tk.Entry(frame_login, show="*", **estilo_entry)
entry_password.pack(fill="x", pady=(0, 5), ipady=3, ipadx=5)

ventana_inputs_login = lienzo.create_window(0, 0, window=frame_login, anchor="center", width=270)

btn_ingresar = BotonRedondeado(lienzo, "Acceder", procesar_login, icono=crear_icono("user", 18), ancho=270, alto=40, bg_padre=COLOR_TARJETA)
ventana_btn_ingresar = lienzo.create_window(0, 0, window=btn_ingresar, anchor="center")

link_reg = tk.Label(lienzo, text="¿No te has registrado? Regístrate aquí", font=(FUENTE_FAMILIA, 9, "underline"), fg="#FFFFFF", bg=COLOR_TARJETA, cursor="hand2")
link_reg.bind("<Button-1>", lambda e: cambiar_vista("registro"))
ventana_link_reg = lienzo.create_window(0, 0, window=link_reg, anchor="center")


# --- Tarjeta de Registro ---
tarjeta_registro = TarjetaBaseCanvas(lienzo, "Crear Cuenta")
ventana_tarjeta_reg = lienzo.create_window(0, 0, window=tarjeta_registro, anchor="center")

frame_registro = tk.Frame(lienzo, bg=COLOR_TARJETA, highlightthickness=0)

tk.Label(frame_registro, text="Nombre de Usuario", font=(FUENTE_FAMILIA, 9, "bold"), fg=COLOR_TEXTO_SECUNDARIO, bg=COLOR_TARJETA).pack(anchor="nw", pady=(0, 1))
entry_reg_usuario = tk.Entry(frame_registro, **estilo_entry)
entry_reg_usuario.pack(fill="x", pady=(0, 6), ipady=2, ipadx=5)

tk.Label(frame_registro, text="Correo Electrónico", font=(FUENTE_FAMILIA, 9, "bold"), fg=COLOR_TEXTO_SECUNDARIO, bg=COLOR_TARJETA).pack(anchor="nw", pady=(0, 1))
entry_reg_correo = tk.Entry(frame_registro, **estilo_entry)
entry_reg_correo.pack(fill="x", pady=(0, 6), ipady=2, ipadx=5)

tk.Label(frame_registro, text="Contraseña", font=(FUENTE_FAMILIA, 9, "bold"), fg=COLOR_TEXTO_SECUNDARIO, bg=COLOR_TARJETA).pack(anchor="nw", pady=(0, 1))
entry_reg_password = tk.Entry(frame_registro, show="*", **estilo_entry)
entry_reg_password.pack(fill="x", pady=(0, 6), ipady=2, ipadx=5)

tk.Label(frame_registro, text="Confirmar Contraseña", font=(FUENTE_FAMILIA, 9, "bold"), fg=COLOR_TEXTO_SECUNDARIO, bg=COLOR_TARJETA).pack(anchor="nw", pady=(0, 1))
entry_reg_confirmar = tk.Entry(frame_registro, show="*", **estilo_entry)
entry_reg_confirmar.pack(fill="x", pady=(0, 4), ipady=2, ipadx=5)

ventana_inputs_reg = lienzo.create_window(0, 0, window=frame_registro, anchor="center", width=270)

btn_registrar = BotonRedondeado(lienzo, "Registrarse", procesar_registro, icono=crear_icono("add", 18), ancho=270, alto=38, bg_padre=COLOR_TARJETA)
ventana_btn_reg = lienzo.create_window(0, 0, window=btn_registrar, anchor="center")

link_login = tk.Label(lienzo, text="¿Ya tienes cuenta? Inicia sesión", font=(FUENTE_FAMILIA, 9, "underline"), fg="#FFFFFF", bg=COLOR_TARJETA, cursor="hand2")
link_login.bind("<Button-1>", lambda e: cambiar_vista("login"))
ventana_link_login = lienzo.create_window(0, 0, window=link_login, anchor="center")

cambiar_vista("login")


# =====================================================================
#   ELEMENTOS FLOTANTES CON EMOJIS
# =====================================================================
EMOJIS_SENAS = ["🤟", "✌️", "☝️", "🖐️", "👌", "👏", "👍", "👋"]
CANTIDAD_FLOTANTES = 45
FPS_MS = 33

class SenaFlotante:
    def __init__(self, canvas, ancho, alto):
        self.canvas = canvas
        self.reiniciar(ancho, alto, inicial=True)
        self.emoji = random.choice(EMOJIS_SENAS)
        self.tam = random.choice([26, 32, 40, 48])
        self.item = canvas.create_text(
            self.x, self.y, text=self.emoji, fill="white",
            font=("Segoe UI Emoji", self.tam), tags="sena"
        )

    def reiniciar(self, ancho, alto, inicial=False):
        self.x0 = random.uniform(0, ancho)
        self.y = random.uniform(0, alto) if inicial else alto + random.uniform(20, 120)
        self.vel = random.uniform(0.4, 1.3)
        self.amp = random.uniform(15, 45)
        self.freq = random.uniform(0.015, 0.04)
        self.fase = random.uniform(0, math.tau)
        self.t = random.uniform(0, 1000)
        self.x = self.x0
        self.emoji = random.choice(EMOJIS_SENAS)

    def actualizar(self, ancho, alto):
        self.t += 1
        self.y -= self.vel
        self.x = self.x0 + self.amp * math.sin(self.t * self.freq + self.fase)

        if self.y < -80:
            self.reiniciar(ancho, alto)
            self.canvas.itemconfig(self.item, text=self.emoji)

        self.canvas.coords(self.item, self.x, self.y)


senas = []
ultimo_tamano = (0, 0)


def distribuir(ancho, alto):
    cx = ancho / 2
    cy = alto / 2 + 15
    
    lienzo.coords(ventana_tarjeta_login, cx, cy)
    lienzo.coords(ventana_inputs_login, cx, cy - 25)
    lienzo.coords(ventana_btn_ingresar, cx, cy + 95)
    lienzo.coords(ventana_link_reg, cx, cy + 155)

    lienzo.coords(ventana_tarjeta_reg, cx, cy)
    lienzo.coords(ventana_inputs_reg, cx, cy - 15)
    lienzo.coords(ventana_btn_reg, cx, cy + 120)
    lienzo.coords(ventana_link_login, cx, cy + 172)

    y_titulo = max(50, cy - ALTO_TARJETA / 2 - 85)
    lienzo.coords(item_titulo, cx, y_titulo)
    lienzo.coords(item_subtitulo, cx, y_titulo + 40)
    lienzo.coords(item_status, cx, alto - 35)


def al_redimensionar(event):
    global fondo_tk, ultimo_tamano
    if (event.width, event.height) == ultimo_tamano:
        return
    ultimo_tamano = (event.width, event.height)
    fondo_tk = ImageTk.PhotoImage(generar_degradado(event.width, event.height))
    lienzo.itemconfig(item_fondo, image=fondo_tk)
    distribuir(event.width, event.height)


def animar():
    ancho = lienzo.winfo_width()
    alto = lienzo.winfo_height()
    if ancho > 50 and alto > 50:
        if not senas:
            for _ in range(CANTIDAD_FLOTANTES):
                senas.append(SenaFlotante(lienzo, ancho, alto))
            lienzo.tag_lower("bg")
            lienzo.tag_raise("texto")
        for s in senas:
            s.actualizar(ancho, alto)
    ventana.after(FPS_MS, animar)


lienzo.bind("<Configure>", al_redimensionar)
ventana.after(200, animar)

ventana.mainloop()